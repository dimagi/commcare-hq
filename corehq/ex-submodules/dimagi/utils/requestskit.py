import urllib.parse


def get_auth(url):
    u = urllib.parse.urlsplit(url)
    return (u.username, u.password) if u.username else None
