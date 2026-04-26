import time
from clipress import classifier


def test_detects_list_shape():
    output = "\n".join([f"file_{i}.txt" for i in range(30)])
    shape, conf = classifier.detect(output)
    assert shape == "list"
    assert conf >= 0.5


def test_detects_progress_shape():
    output = (
        "Downloading... 10%\nDownloading... 20%\nDownloading... 50%\nFetching layer..."
    )
    shape, conf = classifier.detect(output)
    assert shape == "progress"
    assert conf >= 0.5


def test_detects_test_shape_pytest():
    output = (
        "test_foo.py PASSED\ntest_bar.py FAILED\n===== 1 failed, 1 passed in 0.1s ====="
    )
    shape, conf = classifier.detect(output)
    assert shape == "test"
    assert conf >= 0.5


def test_detects_test_shape_jest():
    output = (
        "FAIL src/App.test.js\n  ● App › renders\n    expect(received).toBe(expected)"
    )
    shape, conf = classifier.detect(output)
    assert shape == "test"
    assert conf >= 0.5


def test_detects_diff_shape():
    output = "--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,3 @@\n-old line\n+new line"
    shape, conf = classifier.detect(output)
    assert shape == "diff"
    assert conf >= 0.5


def test_detects_table_shape():
    output = (
        "CONTAINER ID   IMAGE     COMMAND\n"
        + "-" * 30
        + "\n12345          ubuntu    bash\n67890          alpine    sh"
    )
    shape, conf = classifier.detect(output)
    assert shape == "table"
    assert conf >= 0.5


def test_detects_keyvalue_shape():
    output = "Name: App\nStatus: Running\nUptime: 2 days\nVersion: 1.0"
    shape, conf = classifier.detect(output)
    assert shape == "keyvalue"
    assert conf >= 0.5


def test_detects_error_shape():
    output = 'Traceback (most recent call last):\n  File "script.py", line 10, in <module>\n    main()\nValueError: invalid'
    shape, conf = classifier.detect(output)
    assert shape == "error"
    assert conf >= 0.5


def test_falls_back_to_generic():
    output = "Just some random text\nWith no discernible pattern\nThat shouldn't match anything."
    shape, conf = classifier.detect(output)
    assert shape == "generic"
    assert conf == 0.0


def test_completes_in_under_20ms():
    large_output = "\n".join([f"file_{i}.txt" for i in range(1000)])
    start = time.perf_counter()
    classifier.detect(large_output)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.020


def test_classify_git_log():
    output = (
        "abc1234 feat: add compression\n"
        "def5678 fix: handle edge cases\n"
        "ghi9012 docs: update README\n"
        "jkl3456 test: add unit tests\n" * 10
    )
    shape, conf = classifier.detect(output)
    assert shape == "list"
    assert conf >= 0.5


def test_classify_docker_build():
    output = (
        "Step 1/10 : FROM node:18\n"
        " ---> abc1234\n"
        "Step 2/10 : RUN npm install\n"
        " ---> Running in def5678\n"
        "Step 3/10 : COPY . .\n"
        " ---> Using cache\n"
        "Step 4/10 : EXPOSE 3000\n"
        " ---> Running in ghi9012\n"
        "Successfully built xyz7890\n"
    )
    shape, conf = classifier.detect(output)
    assert shape == "progress"
    assert conf >= 0.5


def test_classify_traceback():
    output = (
        'Traceback (most recent call last):\n'
        '  File "app.py", line 42, in main\n'
        '    result = process_data(data)\n'
        '  File "utils.py", line 15, in process_data\n'
        '    return transform(x)\n'
        'ValueError: invalid literal for int(): "abc"\n'
    )
    shape, conf = classifier.detect(output)
    assert shape == "error"
    assert conf >= 0.5


def test_classify_kubectl_get_pods():
    output = (
        "NAME                    READY   STATUS    RESTARTS   AGE\n"
        "---" + "-" * 50 + "\n"
        "nginx-deployment-1      1/1     Running   0          2d\n"
        "nginx-deployment-2      1/1     Running   1          5d\n"
        "redis-cache-0           1/1     Running   0          10d\n"
        "redis-cache-1           1/1     Running   0          10d\n"
    )
    shape, conf = classifier.detect(output)
    assert shape == "table"
    assert conf >= 0.5
