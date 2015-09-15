#!/usr/bin/python
"""
Convert profile file such as that produced by `dimagi.utils.decorators.profile`
to a human-readable text file.

Pulled from https://gist.github.com/czue/4947238
"""

import hotshot.stats
import pstats
import sys

DEFAULT_LIMIT = 200


def profile(filename, limit=DEFAULT_LIMIT):
    outfile = filename + ".txt"
    with open(outfile, 'w') as f:
        print "loading profile stats for %s" % filename
        if filename.endswith('.agg.prof'):
            stats = pstats.Stats(filename, stream=f)
        else:
            stats = hotshot.stats.load(filename)
            stats.stream = f

        # normal stats
        stats.sort_stats('cumulative', 'calls').print_stats(limit)
        stats.print_callers(limit)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "please pass in a filename."
        sys.exit()
    filename = sys.argv[1]
    limit = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LIMIT
    profile(filename, limit)
