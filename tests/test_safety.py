import os
import pytest
from clipress import safety

@pytest.fixture
def workspace(tmp_path):
    return str(tmp_path)

@pytest.fixture
def config():
    return {"engine": {"min_lines_to_compress": 15}, "safety": {"binary_non_ascii_ratio": 0.3}}

def test_blocks_env_file_command(workspace, config):
    should_skip, reason = safety.should_skip("cat .env", "FOO=bar\n" * 20, workspace, config)
    assert should_skip is True
    assert "security sensitive" in reason

def test_blocks_ssh_key_read(workspace, config):
    should_skip, reason = safety.should_skip("cat ~/.ssh/id_rsa", "..." + "\n" * 20, workspace, config)
    assert should_skip is True

def test_blocks_binary_output(workspace, config):
    should_skip, reason = safety.should_skip("cat file.bin", "Hello\x00World" + "\n" * 20, workspace, config)
    assert should_skip is True
    assert "binary" in reason

def test_passes_clean_git_status(workspace, config):
    output = "On branch main\n" * 20
    should_skip, reason = safety.should_skip("git status", output, workspace, config)
    assert should_skip is False
    assert reason == ""

def test_passes_minimal_output_flag(workspace, config):
    should_skip, reason = safety.should_skip("ls", "file1\nfile2", workspace, config)
    assert should_skip is True
    assert "minimal" in reason

def test_detects_bearer_token_in_output(workspace, config):
    output = "Response: Bearer abcdef12345" + ("\n" * 20)
    should_skip, reason = safety.should_skip("curl http://api", output, workspace, config)
    assert should_skip is True
    assert "security" in reason

def test_emits_to_stderr_not_stdout(workspace, config):
    output = "DATABASE_URL=postgres://user:password@host/db" + ("\n" * 20)
    should_skip, reason = safety.should_skip("cat config", output, workspace, config)
    assert should_skip is True
    assert "password" not in reason

def test_respects_user_blocklist(workspace, config):
    comp_dir = os.path.join(workspace, ".clipress")
    os.makedirs(comp_dir, exist_ok=True)
    with open(os.path.join(comp_dir, ".clipress-ignore"), "w") as f:
        f.write("blocked_cmd\n# comment\n")
    
    output = "line\n" * 20
    should_skip, reason = safety.should_skip("blocked_cmd --flag", output, workspace, config)
    assert should_skip is True
    assert "blocklist" in reason

def test_error_pass_through_when_configured(workspace, config):
    config["engine"]["pass_through_on_error"] = True
    output = "Traceback (most recent call last):\n  File \"test.py\", line 1\n    raise Exception()\nException: Failed\n" * 10
    should_skip, reason = safety.should_skip("failing_cmd", output, workspace, config)
    assert should_skip is True
    assert "error output pass-through" in reason

def test_error_pass_through_off(workspace, config):
    config["engine"]["pass_through_on_error"] = False
    output = "Traceback (most recent call last):\n  File \"test.py\", line 1\n    raise Exception()\nException: Failed\n" * 10
    should_skip, reason = safety.should_skip("failing_cmd", output, workspace, config)
    assert should_skip is False


def test_blocks_binary_beyond_512_bytes(workspace, config):
    """GAP-3: Binary detection must catch non-printable bytes beyond the old 512-byte limit."""
    # First 512 chars are clean text, binary starts at byte 513
    clean_prefix = "a" * 513
    binary_suffix = "\x00" * 50  # null bytes well past the old threshold
    output = clean_prefix + binary_suffix
    should_skip, reason = safety.should_skip("cat file.bin", output, workspace, config)
    assert should_skip is True
    assert "binary" in reason


def test_blocks_printenv_command(workspace, config):
    """GAP-4: printenv, env, declare, set must be blocked regardless of output content."""
    output = "PATH=/usr/bin:/bin\nHOME=/root\n" * 20
    for cmd in ["printenv", "env", "declare -p", "set"]:
        should_skip_result, reason = safety.should_skip(cmd, output, workspace, config)
        assert should_skip_result is True, f"{cmd!r} should be blocked"
        assert "security" in reason


def test_user_security_patterns_are_applied(workspace, config):
    """Custom patterns in config.safety.security_patterns must block matching output."""
    config = {**config, "safety": {**config["safety"], "security_patterns": [r"PROPRIETARY_TOKEN"]}}
    output = ("x\n" * 20) + "PROPRIETARY_TOKEN=abc123\n" + ("x\n" * 10)
    should_skip, reason = safety.should_skip("my_cmd", output, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_invalid_user_security_pattern_is_ignored(workspace, config):
    """A malformed regex in user config must not crash the safety gate."""
    config = {**config, "safety": {**config["safety"], "security_patterns": [r"(unclosed"]}}
    output = "hello\n" * 30
    should_skip, reason = safety.should_skip("ls", output, workspace, config)
    assert should_skip is False


def test_generic_secret_word_boundary(workspace, config):
    """Word-boundary tightening: 'secretary' must not trip the default 'secret' pattern."""
    output = "Meeting with the secretary at 3pm\n" * 20
    should_skip, reason = safety.should_skip("cat notes.txt", output, workspace, config)
    assert should_skip is False, (
        "the built-in 'secret' pattern should not match 'secretary' after word-boundary fix"
    )


def test_blocks_ssh_dir_path(workspace, config):
    """Extended security: .ssh/ paths must be blocked in command or output."""
    should_skip, reason = safety.should_skip("cat ~/.ssh/config", "Host github.com\n" * 20, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_echo_shell_variable(workspace, config):
    """Extended security: echo $VAR must be blocked."""
    should_skip, reason = safety.should_skip("echo $SECRET", "secret_value_123\n" * 20, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_history_command(workspace, config):
    """Extended security: history command must be blocked."""
    should_skip, reason = safety.should_skip("history", "1 git log\n2 ls\n" * 20, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_pem_footer_in_output(workspace, config):
    """PEM footer (-----END) must be detected in output."""
    output = "-----END RSA PRIVATE KEY-----\n" * 5 + "other content\n" * 20
    should_skip, reason = safety.should_skip("cat key.pem", output, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_p12_certificate_file(workspace, config):
    """PKCS#12 (.p12) files must be blocked."""
    should_skip, reason = safety.should_skip("cat cert.p12", "binary data\n" * 20, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_pfx_certificate_file(workspace, config):
    """PFX certificate files must be blocked."""
    should_skip, reason = safety.should_skip("cat bundle.pfx", "binary data\n" * 20, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_git_credential_command(workspace, config):
    """git credential operations must be blocked."""
    output = "username=user\npassword=hunter2\n" * 20
    should_skip, reason = safety.should_skip("git credential fill", output, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_etc_shadow_path(workspace, config):
    """Access to /etc/shadow must be blocked."""
    output = "root:x:0:0:root:/root:/bin/bash\n" * 20
    should_skip, reason = safety.should_skip("cat /etc/shadow", output, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_blocks_etc_passwd_path(workspace, config):
    """/etc/passwd access must be blocked."""
    output = "root:x:0:0:root:/root:/bin/bash\n" * 20
    should_skip, reason = safety.should_skip("cat /etc/passwd", output, workspace, config)
    assert should_skip is True
    assert "security" in reason


def test_user_pattern_cache_key_is_stable(workspace, config):
    """Pattern cache must use tuple key (not id()) for stable caching across list lifetimes."""
    patterns = ["CUSTOM_TOKEN_ABC"]
    compiled1 = safety._compile_user_patterns(patterns)
    # Build a second list with same strings — must hit the same cache entry
    compiled2 = safety._compile_user_patterns(list(patterns))
    assert compiled1 is compiled2, "Cache should return the same compiled list for identical patterns"
