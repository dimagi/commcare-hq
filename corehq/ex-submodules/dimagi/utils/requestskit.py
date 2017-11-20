from __future__ import print_function
from __future__ import absolute_import
import urlparse


def get_auth(url):
    u = urlparse.urlsplit(url)
    return (u.username, u.password) if u.username else None
