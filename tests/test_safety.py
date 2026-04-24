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
    comp_dir = os.path.join(workspace, ".compressor")
    os.makedirs(comp_dir, exist_ok=True)
    with open(os.path.join(comp_dir, ".compressor-ignore"), "w") as f:
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


def test_config_security_patterns_applied(workspace, config):
    """Patterns from config.safety.security_patterns must block output, not just the hardcoded list."""
    config["safety"]["security_patterns"] = [r"MY_CUSTOM_SECRET"]
    output = "line\n" * 20 + "MY_CUSTOM_SECRET=hunter2\n"
    should_skip_result, reason = safety.should_skip("printout", output, workspace, config)
    assert should_skip_result is True
    assert "security" in reason


def test_config_security_patterns_command(workspace, config):
    """Custom patterns should also match against the command string."""
    config["safety"]["security_patterns"] = [r"super_secret_tool"]
    output = "normal output\n" * 20
    should_skip_result, reason = safety.should_skip("super_secret_tool --run", output, workspace, config)
    assert should_skip_result is True
    assert "security" in reason
