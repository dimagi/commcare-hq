#!/usr/bin/env python
"""A convenience utility for calculating how far "behind" HQ is on outdated
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
...
21.0.0   contextlib2              21.6.0       0.6.0.post1


$ yarn outdated --json | ./scripts/outdated-dependency-metrics.py yarn
WARNING: skipping exotic package: knockout-validation
...
Behind   Package                      Latest       Version
0.0.1    bootstrap-timepicker         0.5.2        0.5.1
...
12.0.0   sinon                        14.0.0       2.3.2

Enjoy!
"""
import argparse
import json
import sys


def main():
    stream_parsers = {
        "pip": parse_pip,
        "yarn": parse_yarn,
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
    parser.add_argument(
        "--no-labels",
        dest="labels",
        default=True,
        action="store_false",
        help="do not print data labels in the output",
    )

    opts = parser.parse_args()
    package_list(opts.in_file, stream_parsers[opts.format], opts.labels)


def package_list(stream, stream_parser, labels=True):

    def print_line(behind, name, current, latest):
        print(f"{behind:8s} {name:28s} {current:12s} {latest}")

    records = sorted(stream_parser(stream))
    try:
        if labels:
            print_line("Behind", "Package", "Latest", "Version")
        for delta, name, current, latest in records:
            if delta is None:
                behind = "n/a"
            else:
                behind = ".".join(str(v) for v in delta)
            print_line(behind, name, current, latest)
    except IOError:
        pass


def parse_pip(stream):
    for pkg in json.load(stream):
        latest = pkg["latest_version"]
        current = pkg["version"]
        yield behind(latest, current), pkg["name"], latest, current


def parse_yarn(stream):
    def fail():
        raise ValueError(f"invalid yarn package data: {lines}")
    lines = [line for line in stream.readlines() if line.rstrip()]
    if len(lines) == 1:
        blob = lines[0]
    elif len(lines) == 2:
        for_humans = json.loads(lines[0])
        if for_humans["type"] != "info":
            fail()
        blob = lines[1]
    else:
        fail()
    payload = json.loads(blob)
    if payload["type"] != "table":
        fail()
    head = payload["data"]["head"]
    body = payload["data"]["body"]
    for record in body:
        pkg = dict(zip(head, record))
        name = pkg["Package"]
        latest = pkg["Latest"]
        current = pkg["Current"]
        if latest == "exotic":
            delta = None
        else:
            delta = behind(latest, current)
        yield delta, name, latest, current


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
