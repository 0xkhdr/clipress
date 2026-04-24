import os
import re

files = [
    "clipress/classifier.py",
    "clipress/strategies/base.py",
    "clipress/strategies/error_strategy.py",
    "clipress/strategies/keyvalue_strategy.py",
    "clipress/strategies/list_strategy.py",
    "clipress/strategies/progress_strategy.py",
    "clipress/strategies/table_strategy.py",
    "clipress/strategies/test_strategy.py",
]

for fpath in files:
    with open(fpath, "r") as f:
        content = f.read()
    
    # Replace `for l in` with `for ln in`
    content = re.sub(r'\bfor l in ', 'for ln in ', content)
    # Replace `len(l)` with `len(ln)`
    content = re.sub(r'len\(l\)', 'len(ln)', content)
    # Replace `if l.` with `if ln.`
    content = re.sub(r'if l\.', 'if ln.', content)
    # Replace `l = ` with `ln = `
    content = re.sub(r'\bl = ', 'ln = ', content)
    # Replace `(l)` with `(ln)`
    content = re.sub(r'\(l\)', '(ln)', content)
    # Replace `l == ` with `ln == `
    content = re.sub(r'\bl == ', 'ln == ', content)
    # Replace `l != ` with `ln != `
    content = re.sub(r'\bl != ', 'ln != ', content)
    # Replace `l in ` with `ln in `
    content = re.sub(r'\bl in ', 'ln in ', content)
    # Replace `, l:` with `, ln:`
    content = re.sub(r', l:', ', ln:', content)
    # Replace `l, ` with `ln, `
    content = re.sub(r'\bl, ', 'ln, ', content)
    # Replace `in l:` with `in ln:`
    content = re.sub(r'\bin l:', 'in ln:', content)
    # Replace `in l)` with `in ln)`
    content = re.sub(r'\bin l\)', 'in ln)', content)
    # Replace `append(l)` with `append(ln)`
    content = re.sub(r'append\(l\)', 'append(ln)', content)
    # Replace `(l, ` with `(ln, `
    content = re.sub(r'\(l, ', '(ln, ', content)
    # Replace ` l:` with ` ln:`
    content = re.sub(r'\bl:', 'ln:', content)

    # Some manual cleanup for engine.py and table_strategy.py
    
    with open(fpath, "w") as f:
        f.write(content)

