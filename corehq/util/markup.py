# coding: utf-8
from __future__ import absolute_import
import re
from abc import abstractmethod, ABCMeta

import six
import sys
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

from dimagi.utils.decorators.memoized import memoized

url_re = re.compile(
    r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""
)


def mark_up_urls(text):
    """
    >>> mark_up_urls("Please see http://google.com for more info.")
    u'Please see <a href="http://google.com">http://google.com</a> for more info.'
    >>> mark_up_urls("http://commcarehq.org redirects to https://commcarehq.org.")
    u'<a href="http://commcarehq.org">http://commcarehq.org</a> redirects to <a href="https://commcarehq.org">https://commcarehq.org</a>.'

    """
    def wrap_url(url):
        return format_html('<a href="{url}">{url}</a>', url=url)

    def parts():
        for chunk in url_re.split(text):
            if not chunk:
                continue
            elif url_re.match(chunk):
                yield wrap_url(chunk)
            else:
                yield escape(chunk)

    return mark_safe(''.join(parts()))


def _shell_color_template(color_code):
    def inner(text):
        return "\033[%sm%s\033[0m" % (color_code, text)
    return inner

shell_red = _shell_color_template('31')
shell_green = _shell_color_template('32')


class SimpleTableWriter(object):
    """Helper class for writing tables to the console
    """
    def __init__(self, output=None, row_formatter=None):
        self.output = output or sys.stdout
        self.row_formatter = row_formatter or CSVRowFormatter()

    def write_table(self, headers, rows):
        self.write_headers(headers)
        self.write_rows(rows)

    def write_headers(self, headers):
        self.output.write(self.row_formatter.format_headers(headers))

    def write_rows(self, rows):
        for row in rows:
            self.output.write(self.row_formatter.format_row(row))


class RowFormatter(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_template(self, num_cols):
        raise NotImplementedError

    def format_headers(self, headers):
        return self.format_row(headers)

    def format_row(self, row):
        return self.get_template(len(row)).format(*row)


class CSVRowFormatter(RowFormatter):
    """Format rows as CSV"""

    def get_template(self, num_cols):
        return ','.join(['{}'] * num_cols)


class TableRowFormatter(RowFormatter):
    """Format rows as a table with optional row highlighting"""
    def __init__(self, col_widths=None, row_color_getter=None):
        self.col_widths = col_widths
        self.row_color_getter = row_color_getter

    @memoized
    def get_template(self, num_cols):
        if self.col_widths:
            assert len(self.col_widths) == num_cols
        else:
            self.col_widths = [20] * num_cols

        return ' | '.join(['{{:<{}}}'.format(width) for width in self.col_widths])

    def format_headers(self, headers):
        template = self.get_template(len(headers))
        return '{}\n{}'.format(
            template.format(*headers),
            template.format(*['-' * width for width in self.col_widths]),
        )

    def format_row(self, row):
        template = self.get_template(len(row))
        color = self.row_color_getter(row) if self.row_color_getter else None
        return self._highlight(color, template).format(*row)

    def _highlight(self, color, template):
        if not color:
            return template
        if color == 'red':
            return shell_red(template)
        if color == 'green':
            return shell_green(template)

        raise Exception('Unknown color: {}'.format(color))
