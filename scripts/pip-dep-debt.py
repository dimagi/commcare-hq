#!/usr/bin/env python
"""A convenience utility for calculating how far "behind" HQ is on outdated pip
dependencies.

TODO:
- use argparse
    - for usage/epilog/help/etc
    - accept files other than a STDIN pipe
- dynamically calculate column widths rather than using hard-coded widths
- make it more robust (currently will crash if versions aren't SemVer compliant,
  does PyPi allow this?)
- extend if you wish!

USAGE:

$ pip list --format json --outdated | ./scripts/pip-dep-debt.py
Behind   Package                  Latest       Version
0.0.1    colorama                 0.4.4        0.4.3
0.0.1    django-appconf           1.0.5        1.0.4
...
0.4.0    Sphinx                   4.5.0        4.1.2
...
21.0.0   contextlib2              21.6.0       0.6.0.post1

# quiet down, pip!
$ pip list --format json --outdated 2>/dev/null | ./scripts/pip-dep-debt.py
...

Enjoy!
"""
import json
import sys


def main(stream):
    records = []
    for pkg in json.load(stream):
        latest = pkg["latest_version"]
        current = pkg["version"]
        records.append((behind(latest, current), pkg["name"], latest, current))
    try:
        print_line("Behind", "Package", "Latest", "Version")
        for delta, name, current, latest in sorted(records):
            print_line(".".join(str(v) for v in delta), name, current, latest)
    except IOError:
        pass


def print_line(delta, name, current, latest):
    print(f"{delta:8s} {name:24s} {current:12s} {latest}")


def behind(latest, current):
    delta = [0, 0, 0]
    for index, (lat, cur) in enumerate(zip(vsplit(latest), vsplit(current))):
        if lat != cur:
            delta[index] = lat - cur
            break
    return delta


def vsplit(version):
    padded = f"{version}.0.0"  # append extra zeros for versions like '1' or '2.0'
    return [int(n) for n in padded.split(".")[:3]]


if __name__ == "__main__":
    main(sys.stdin)
