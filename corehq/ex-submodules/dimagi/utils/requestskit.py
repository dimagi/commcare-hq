from __future__ import print_function
import urlparse


def get_auth(url):
    u = urlparse.urlsplit(url)
    return (u.username, u.password) if u.username else None
