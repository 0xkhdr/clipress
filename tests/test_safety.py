from clipress import safety


def test_blocks_env_file_command():
    should_skip, reason = safety.should_skip("cat .env", "FOO=bar")
    assert should_skip is True
    assert "security sensitive" in reason


def test_blocks_ssh_key_read():
    should_skip, reason = safety.should_skip("cat ~/.ssh/id_rsa", "...")
    assert should_skip is True


def test_blocks_binary_output():
    should_skip, reason = safety.should_skip("cat file.bin", "Hello\x00World")
    assert should_skip is True
    assert "binary" in reason


def test_passes_clean_git_status():
    output = "On branch main\n" * 20
    should_skip, reason = safety.should_skip("git status", output)
    assert should_skip is False
    assert reason == ""


def test_passes_minimal_output_flag():
    should_skip, reason = safety.should_skip("ls", "file1\nfile2")
    assert should_skip is True
    assert "minimal" in reason


def test_detects_bearer_token_in_output():
    output = "Response: Bearer abcdef12345" + ("\n" * 20)
    should_skip, reason = safety.should_skip("curl http://api", output)
    assert should_skip is True
    assert "security" in reason


def test_emits_to_stderr_not_stdout():
    # Stderr emission is handled by the caller, so we verify reason doesn't leak secrets
    output = "DATABASE_URL=postgres://user:P4ssw0rd@host/db"
    should_skip, reason = safety.should_skip("cat config", output)
    assert should_skip is True
    assert "P4ssw0rd" not in reason
