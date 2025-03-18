import hashlib


def get_hash(msg):
    return hashlib.md5(msg.encode('utf-8')).hexdigest()[:8]
