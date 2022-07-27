#!/usr/bin/env python
"""A utility that outputs package information _like_ `pip list ...`, but for
yarn packages.

TODO:
- dynamically calculate column widths rather than using hard-coded widths

Examples:

$ ./yarn-list.py
Package                              Version
colorama                             0.4.3
...

$ ./yarn-list.py --outdated
Package                              Version     Latest
colorama                             0.4.3       0.4.4
...
"""
import argparse
import json
import sys
from subprocess import DEVNULL, check_output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        default=False,
        action="store_true",
        help="output in JSON",
    )
    parser.add_argument(
        "--outdated",
        default=False,
        action="store_true",
        help="list outdated packages",
    )
    opts = parser.parse_args()
    packages = package_list(opts.outdated)
    if opts.json:
        json.dump(packages, sys.stdout)
    else:
        print_table(packages, opts.outdated)


def package_list(outdated):
    yarn = Yarn()
    all_packages = yarn.list()
    if not outdated:
        return all_packages
    outdated_packages = []
    for package in all_packages:
        latest_version = yarn.latest_version(package["name"])
        if package["version"] != latest_version:
            package["latest_version"] = latest_version if latest_version else "exotic"
            outdated_packages.append(package)
    return outdated_packages


def print_table(packages, show_latest=False):

    def print_line(package):
        line = f"{package['name']:36} {package['version']:8}"
        if show_latest:
            line = f"{line} {package['latest_version']}"
        print(line.rstrip())

    print_line({
        "name": "Package",
        "version": "Version",
        "latest_version": "Latest",
    })
    for package in packages:
        print_line(package)


class Yarn:

    def __init__(self):
        yarn_version = check_output(["yarn", "--version"], text=True).strip()
        if not yarn_version.startswith("1."):
            raise Crash(f"Yarn Classic (v1.x) is required, found {yarn_version}")

    def command(self, sub_args):
        # discard first and last lines (yarn version and timing info)
        # confirmed safe on subcommands:
        # - info
        # - list
        return check_output(["yarn"] + sub_args, stderr=DEVNULL, text=True).splitlines()[1:-1]

    def list(self):
        lines = self.command(["list", "--depth", "0"])
        packages = []
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
            # example:
            # ├─ @ungap/promise-all-settled@1.1.2
            # ├─ abbrev@1.1.1
            name, x, version = line.split(None, 2)[1].rpartition("@")
            packages.append({"name": name, "version": version})
        return packages

    def latest_version(self, name):
        lines = self.command(["info", name, "dist-tags.latest"])
        if not lines:
            return None
        assert len(lines) == 1, f"{name}: invalid latest: {lines!r}"
        return lines[0].strip()


class Crash(Exception):
    pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(2)
    except BrokenPipeError:
        # Don't print a traceback (or exit with an error) when tools like 'head'
        # or 'grep' close the stream early.
        pass
    except Crash as exc:
        print(f"ERROR: {exc!s}", file=sys.stderr)
        sys.exit(1)
