#!/usr/bin/env python
"""A convenience utility for calculating how far "behind" HQ is on outdated pip
dependencies.

TODO:
- dynamically calculate column widths rather than using hard-coded widths
- make it more robust (currently will crash if versions aren't SemVer compliant,
  does PyPi allow this?)
- extend if you wish!

USAGE:

$ pip list --format json --outdated | ./scripts/outdated-dependency-metrics.py pip
Behind   Package                  Latest       Version
0.0.1    colorama                 0.4.4        0.4.3
0.0.1    django-appconf           1.0.5        1.0.4
...
0.4.0    Sphinx                   4.5.0        4.1.2
...
21.0.0   contextlib2              21.6.0       0.6.0.post1

# quiet down, pip!
$ pip list --format json --outdated 2>/dev/null | ./scripts/outdated-dependency-metrics.py pip
...

Enjoy!
"""
import argparse
import json
import sys


def main():
    stream_parsers = {
        "pip": parse_pip,
    }

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "format",
        choices=list(stream_parsers),
        help="package information format (choices=%(choices)s)",
    )
    parser.add_argument(
        "in_file",
        metavar="FILE",
        nargs="?",
        type=argparse.FileType(mode="r"),
        default=sys.stdin,
        help="read package (JSON) information from %(metavar)s, specify a dash "
             "(-) to read from STDIN (the default).",
    )
    opts = parser.parse_args()
    package_list(opts.in_file, stream_parsers[opts.format])


def package_list(stream, stream_parser):
    records = sorted(stream_parser(stream))
    try:
        print_line("Behind", "Package", "Latest", "Version")
        for delta, name, current, latest in records:
            print_line(".".join(str(v) for v in delta), name, current, latest)
    except IOError:
        pass


def parse_pip(stream):
    for pkg in json.load(stream):
        latest = pkg["latest_version"]
        current = pkg["version"]
        yield behind(latest, current), pkg["name"], latest, current


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
    main()
