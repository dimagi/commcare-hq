#!/usr/bin/python

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import sys
import os
from six.moves import zip


def get_stats(path, build_slug):
    perfpath = os.path.join(path, '{}-performance.txt'.format(build_slug))
    with open(perfpath, 'r') as f:
        lines = f.read().splitlines()
        stats = [line.split(',') for line in lines]
        return {line[0]: {'mem': int(line[1]), 'time': float(line[2])} for line in stats}


def avg(vals):
    return float(sum(vals)) / len(vals)


def avg_dict(data):
    def vals_by_key(key, vals):
        return [item[key] for item in vals]

    return {key: avg(vals_by_key(key, data)) for key in ['%', 'numerator', 'denominator']}


def get_templates(col_widths):
    header_template = ''.join('{{:<{}}}'.format(width) for width in col_widths)

    col_1 = '{{:<{}}}'.format(col_widths[0])
    col_n = ''.join('{{:<{}}}'.format(width) for width in col_widths[1:])
    row_template = col_1 + col_n
    
    return header_template, row_template


def compare_stats(stats1, stats2):
    """
    Compare performance stats output by the 'build_apps' command.
    """
    col_widths = (60, 30, 30)
    header_template, row_template = get_templates(col_widths)
    mem_cell_template = '{%:<7,.2%} ({numerator:.0f} / {denominator:.0f})'
    time_cell_template = '{%:<7,.2%} ({numerator:.2f} / {denominator:.2f})'
    print(header_template.format('App', 'Mem diff %', 'Time diff %'))

    def print_sep():
        print(header_template.format(*['-' * (width - 1) for width in col_widths]))

    print_sep()

    def get_stats_diff(slug, stat):
        stats_item1 = stats1[slug]
        if slug not in stats2:
            return 100

        stats_item2 = stats2[slug]
        diff = stats_item2[stat] - stats_item1[stat]
        percent = float(diff) / stats_item1[stat]
        return {
            '%': percent,
            'numerator': diff,
            'denominator': stats_item1[stat]
        }

    def get_all_diffs(name):
        return [get_stats_diff(slug, name) for slug in stats1]

    all_mem = get_all_diffs('mem')
    all_time = get_all_diffs('time')
    for slug, mem, time in zip(stats1, all_mem, all_time):
        print(row_template.format(
            slug,
            mem_cell_template.format(**mem),
            time_cell_template.format(**time)
        ))

    print_sep()
    print(row_template.format(
        'Average',
        mem_cell_template.format(**avg_dict(all_mem)),
        time_cell_template.format(**avg_dict(all_time)),
    ))


if __name__ == '__main__':
    path, build_slug1, build_slug2 = sys.argv[1:]
    stats1 = get_stats(path, build_slug1)
    stats2 = get_stats(path, build_slug2)
    compare_stats(stats1, stats2)
