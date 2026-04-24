from clipress.strategies.progress_strategy import ProgressStrategy


def test_progress_strategy_final_line():
    strategy = ProgressStrategy()
    output = (
        "Downloading... 10%\nDownloading... 50%\n10 MB/s ETA 1m\nDownload complete."
    )
    compressed = strategy.compress(output, {"keep": "final_line"}, {})
    assert "Download complete." in compressed
    assert "10%" not in compressed
    assert "ETA" not in compressed


def test_progress_strategy_errors_and_final():
    strategy = ProgressStrategy()
    output = "Step 1\nStep 2\nError: connection lost\nRetrying...\nSuccess"
    compressed = strategy.compress(output, {"keep": "errors_and_final"}, {})
    assert "Error: connection lost" in compressed
    assert "Success" in compressed
    assert "Step 1" not in compressed


def test_progress_strategy_contract():
    strategy = ProgressStrategy()
    output = "Step 1\nStep 2\nSuccess"
    contract = {"always_keep": ["Step 1"]}
    compressed = strategy.compress(output, {"keep": "final_line"}, contract)
    assert "Step 1" in compressed
    assert "Success" in compressed


def test_progress_strategy_keep_all():
    """keep='all' retains all non-stripped lines plus errors and final."""
    strategy = ProgressStrategy()
    output = "Starting build\nCompiling module A\nCompiling module B\n100%\nBuild done"
    compressed = strategy.compress(output, {"keep": "all", "strip_percentage": True}, {})
    assert "Starting build" in compressed
    assert "Compiling module A" in compressed
    assert "Build done" in compressed
    assert "100%" not in compressed
