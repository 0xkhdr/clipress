import re

_PCT_PATTERN = re.compile(r"\d+%")
_FRAC_PATTERN = re.compile(r"\d+/\d+")
_PROGRESS_WORDS = re.compile(r"downloading|fetching|step|layer", re.IGNORECASE)
_TEST_WORDS = re.compile(r"PASSED|FAILED|ERROR|ok|FAIL")
_DIFF_PLUS_MINUS = re.compile(r"^[+-](?![+-])")
_KEY_VALUE1 = re.compile(r"^\w[\w\s]+:\s+\S")
_KEY_VALUE2 = re.compile(r"^\w[\w\s]+=\s*\S")
_TABLE_SEP = re.compile(r"^[-\s|+]+$")
_TABLE_COLUMNS = re.compile(r"\s{2,}|\t|\|")


def detect(output: str) -> tuple[str, float]:
    """
    Analyzes output and returns (shape_name, confidence).
    """
    if not output:
        return "generic", 0.0

    # Line sampling based - max 200 lines
    lines = output.splitlines()[:200]
    num_lines = len(lines)

    if num_lines == 0:
        return "generic", 0.0

    scores = {
        "list": 0.0,
        "progress": 0.0,
        "test": 0.0,
        "diff": 0.0,
        "table": 0.0,
        "keyvalue": 0.0,
        "error": 0.0,
    }

    # Pre-calculate common metrics
    num_colon_patterns = 0
    num_plus_minus = 0
    num_pct_frac = 0
    num_progress_words = 0
    num_test_words = 0
    num_test_name_hits = 0
    num_at_at = 0
    num_diff_markers = 0
    num_kv1 = 0
    num_kv2 = 0
    num_error_frames = 0

    has_traceback = False
    has_exception = False

    for line in lines:
        if ":" in line:
            num_colon_patterns += 1
        if _DIFF_PLUS_MINUS.match(line):
            num_plus_minus += 1
        if _PCT_PATTERN.search(line) or _FRAC_PATTERN.search(line):
            num_pct_frac += 1
        if _PROGRESS_WORDS.search(line):
            num_progress_words += 1
        if _TEST_WORDS.search(line):
            num_test_words += 1
        if "test" in line.lower():
            num_test_name_hits += 1
        if "@@" in line:
            num_at_at += 1
        if "---" in line or "+++" in line:
            num_diff_markers += 1
        if _KEY_VALUE1.match(line):
            num_kv1 += 1
        if _KEY_VALUE2.match(line):
            num_kv2 += 1
        if "Traceback" in line:
            has_traceback = True
        if "Exception" in line:
            has_exception = True
        if "at line" in line or 'File "' in line:
            num_error_frames += 1

    # list
    if num_lines > 20:
        scores["list"] += 0.3
    # check similar length
    if num_lines >= 5:
        lengths = [len(ln) for ln in lines]
        avg_len = sum(lengths) / num_lines
        similar_len = sum(1 for ln in lengths if abs(ln - avg_len) <= 20)
        if similar_len / num_lines > 0.8:
            scores["list"] += 0.3
        if num_colon_patterns / num_lines < 0.2:
            scores["list"] += 0.2
        if num_plus_minus == 0:
            scores["list"] += 0.2
    elif num_lines > 0:
        # Give a small boost for list-like small outputs, but keep under 0.5 for generic
        if num_colon_patterns == 0 and num_plus_minus == 0:
            scores["list"] += 0.2

    # progress
    if num_pct_frac > 0:
        scores["progress"] += 0.4
    if num_progress_words > 0:
        scores["progress"] += 0.3
    if num_lines > 10 and num_pct_frac > num_lines * 0.5:
        scores["progress"] += 0.3
    if num_lines <= 10 and num_pct_frac > 0 and num_progress_words > 0:
        # Boost small progress outputs to break ties with list
        scores["progress"] += 0.1

    # test
    if num_test_words > 0:
        scores["test"] += 0.5
    if num_test_name_hits / num_lines > 0.2:
        scores["test"] += 0.3
    if any("=====" in ln or "====" in ln for ln in lines[-5:]):  # simple summary check
        scores["test"] += 0.2

    # diff
    if num_plus_minus / num_lines > 0.1:
        scores["diff"] += 0.6
    if num_at_at > 0:
        scores["diff"] += 0.3
    if num_diff_markers > 0:
        scores["diff"] += 0.1

    # table
    if num_lines >= 2 and _TABLE_SEP.match(lines[1]):
        scores["table"] += 0.5
    # columns align check
    if num_lines >= 3:
        # Check if rows have similar number of columns separated by 2+ spaces or tabs/pipes
        col_counts = [len(_TABLE_COLUMNS.split(ln)) for ln in lines[:10] if ln.strip()]
        if (
            len(col_counts) >= 3
            and len(set(col_counts[-3:])) == 1
            and col_counts[-1] > 1
        ):
            scores["table"] += 0.3
    if lines and lines[0].isupper():
        scores["table"] += 0.2

    # keyvalue
    if num_lines > 0:
        kv1_ratio = num_kv1 / num_lines
        kv2_ratio = num_kv2 / num_lines
        if kv1_ratio > 0.6:
            scores["keyvalue"] += 0.5
        if kv2_ratio > 0.6:
            scores["keyvalue"] += 0.3
        if scores["progress"] < 0.2 and scores["test"] < 0.2:
            scores["keyvalue"] += 0.2

    # error
    if has_traceback or has_exception:
        scores["error"] += 0.5
    if num_error_frames > 0:
        scores["error"] += 0.3
    # Check for indented lines after an error frame
    if num_error_frames > 0:
        for i in range(num_lines - 1):
            if ('File "' in lines[i] or "at line" in lines[i]) and lines[
                i + 1
            ].startswith("    "):
                scores["error"] += 0.2
                break

    # Cap scores at 1.0
    for k in scores:
        scores[k] = min(1.0, scores[k])

    best_shape = max(scores.items(), key=lambda x: x[1])

    if best_shape[1] < 0.5:
        return "generic", 0.0

    return best_shape[0], round(best_shape[1], 2)
