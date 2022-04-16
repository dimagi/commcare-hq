#!/usr/bin/env python
"""Strip unwanted packages out of pip-compiled requirements txt files.

TODO:
- support packages with multiple via's
- accept purge package details via --package argument instead of global dict
"""
import argparse
import sys
from collections import deque


PACKAGES_TO_PURGE = {
    # package, via
    "appnope": "ipython",
}


def main(files, packages=PACKAGES_TO_PURGE):
    for file in files:
        # Ideally these things are less than GiB's in size, because we're gonna
        # have a few copies in memory :)
        lines = list(file)
        purged = list(purge_packages(lines, packages))
        if file.fileno() == 0:  # stdin
            # always write these lines to stdout, regardless of purge
            rewrite_lines(sys.stdout, purged)
        elif lines != purged:
            file.close()
            with open(file.name, "w") as outfile:
                rewrite_lines(outfile, purged)


def purge_packages(lines, packages):
    """Iterates over a collection of requirements `lines`, yielding all lines
    except those matching `packages`.

    :param lines: iterable of requirement file lines
    :param packages: dictionary of packages to purge

    To run tests:
    $ ./scripts/purge-platform-pkgs.py --test

    >>> unwanted = {'dep': 'parent'}
    >>> list(purge_packages([], unwanted))
    []
    >>> list(purge_packages(['django==3.2.1', ' # via -r base.in'], unwanted))
    ['django==3.2.1', ' # via -r base.in']
    >>> list(purge_packages(['dep==1.2.3', ' # via parent'], unwanted))
    []
    >>> list(purge_packages(['dep==1.2.3', ' # via parent-sub'], unwanted))
    ['dep==1.2.3', ' # via parent-sub']
    >>> list(purge_packages(['dep==1.2.3', ' # via django'], unwanted))
    ['dep==1.2.3', ' # via django']
    >>> list(purge_packages(['django', ' # via -r base.in', 'dep==1.2.3', ' # via parent'], unwanted))
    ['django', ' # via -r base.in']
    >>> list(purge_packages(['dep==1.2.3', ' # via parent', 'django', ' # via -r base.in'], unwanted))
    ['django', ' # via -r base.in']
    """
    stack = deque(lines)
    while stack:
        line = stack.popleft()
        name, delim, tail = line.partition("=")
        if delim and name in packages and stack:
            next_line = stack.popleft()  # pop the "via" line
            if next_line.strip() == f"# via {packages[name]}":
                continue  # skip both lines
            stack.insert(0, next_line)  # nope, put it back
        yield line


def rewrite_lines(file, lines):
    sys.stderr.write(f"re-writing {file.name!r}\n")
    file.writelines(lines)


if __name__ == "__main__":
    if "--test" in sys.argv:
        # pre-argparse because that requires at least one valid file arg
        import doctest
        doctest.testmod()
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("files", metavar="FILE", nargs="+", type=argparse.FileType("r"),
            help="purge packages from compiled python requirements %(metavar)s(s)")
        main(parser.parse_args().files)
