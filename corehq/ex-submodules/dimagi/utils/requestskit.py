import six.moves.urllib.parse


def get_auth(url):
    u = six.moves.urllib.parse.urlsplit(url)
    return (u.username, u.password) if u.username else None
