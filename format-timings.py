"""
Run this with
  ./manage.py noop > import-timings.txt
  < import-timings.txt grep -v corehq.util.log.HqAdminEmailHandler | sed 's|/Users/droberts/dimagi/commcare-hq/|./|' | python format-timings.py
"""
import sys

def parse_stdin():
    for line in sys.stdin.readlines():
        filename, time = line.strip().split()
        yield filename, float(time)


start = None
stack = []
for filename, time in parse_stdin():
    if start is None:
        start = time
    indent_adjustment = 0
    if stack and stack[-1] == filename:
        stack.pop()
    else:
        stack.append(filename)
        indent_adjustment = 1

    print " " * (len(stack) - indent_adjustment) + filename, time - start
