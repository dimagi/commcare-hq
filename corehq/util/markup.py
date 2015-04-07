# coding: utf-8
import re
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe


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
