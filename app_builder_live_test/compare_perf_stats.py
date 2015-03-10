#!/usr/bin/python

import sys
import os


def get_stats(path, build_slug):
    perfpath = os.path.join(path, '{}-performance.txt'.format(build_slug))
    with open(perfpath, 'r') as f:
        lines = f.read().splitlines()
        stats = [line.split(',') for line in lines]
        return {line[0]: {'mem': int(line[1]), 'time': float(line[2])} for line in stats}


def compare_stats(stats1, stats2):
    """
    Compare performance stats output by the 'build_apps' command.
    """
    col_widths = (60, 15, 15)
    header_template = ''.join('{{:<{}}}'.format(width) for width in col_widths)
    print(header_template.format('App', 'Mem diff %', 'Time diff %'))
    print(header_template.format(*['-' * (width - 1) for width in col_widths]))

    col_1 = '{{:<{}}}'.format(col_widths[0])
    col_n = ''.join('{{:<{},.2f}}'.format(width) for width in col_widths[1:])
    row_template = col_1 + col_n

    def get_stats_diff(slug, stat):
        stats_item1 = stats1[slug]
        if slug not in stats2:
            return 100

        stats_item2 = stats2[slug]
        diff = stats_item1[stat] - stats_item2[stat]
        return 100.0 * diff / stats_item1[stat]

    for slug in stats1:
        print(row_template.format(
            slug,
            get_stats_diff(slug, 'mem'),
            get_stats_diff(slug, 'time')
        ))

if __name__ == '__main__':
    path, build_slug1, build_slug2 = sys.argv[1:]
    stats1 = get_stats(path, build_slug1)
    stats2 = get_stats(path, build_slug2)
    compare_stats(stats1, stats2)
