#!/usr/bin/python

import sys
import os


def get_stats(path, build_slug):
    perfpath = os.path.join(path, '{}-performance.txt'.format(build_slug))
    with open(perfpath, 'r') as f:
        lines = f.read().splitlines()
        stats = [line.split(',') for line in lines]
        return {line[0]: {'mem': int(line[1]), 'time': float(line[2])} for line in stats}


def avg(vals):
        return float(sum(vals))/len(vals)


def get_templates(col_widths):
    header_template = ''.join('{{:<{}}}'.format(width) for width in col_widths)

    col_1 = '{{:<{}}}'.format(col_widths[0])
    col_n = ''.join('{{:<{},.2f}}'.format(width) for width in col_widths[1:])
    row_template = col_1 + col_n
    
    return header_template, row_template


def compare_stats(stats1, stats2):
    """
    Compare performance stats output by the 'build_apps' command.
    """
    col_widths = (60, 15, 15)
    header_template, row_template = get_templates(col_widths)
    print(header_template.format('App', 'Mem diff %', 'Time diff %'))

    def print_sep():
        print(header_template.format(*['-' * (width - 1) for width in col_widths]))

    print_sep()

    def get_stats_diff(slug, stat):
        stats_item1 = stats1[slug]
        if slug not in stats2:
            return 100

        stats_item2 = stats2[slug]
        diff = stats_item1[stat] - stats_item2[stat]
        return 100.0 * diff / stats_item1[stat]

    def get_all_diffs(name):
        return [get_stats_diff(slug, name) for slug in stats1]

    all_mem = get_all_diffs('mem')
    all_time = get_all_diffs('time')
    for slug, mem, time in zip(stats1.keys(), all_mem, all_time):
        print(row_template.format(slug, mem, time))

    print_sep()
    print(row_template.format('Average', avg(all_mem), avg(all_time)))


if __name__ == '__main__':
    path, build_slug1, build_slug2 = sys.argv[1:]
    stats1 = get_stats(path, build_slug1)
    stats2 = get_stats(path, build_slug2)
    compare_stats(stats1, stats2)
