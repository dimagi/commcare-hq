from __future__ import absolute_import, unicode_literals

from django.utils import html


def link_format(text, url):
    return '<a href=%s target="_blank">%s</a>' % (url, text)


def make_url(report_class, domain, string_params, args):
    try:
        return html.escape(
            report_class.get_url(
                domain=domain
            ) + string_params % args
        )
    except KeyError:
        return None
