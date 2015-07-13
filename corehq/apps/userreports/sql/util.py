import hashlib


def truncate_value(value, max_length=63):
    """
    Truncate a value (typically a column name) to a certain number of characters,
    using a hash to ensure uniqueness.
    """
    if len(value) > max_length:
        short_hash = hashlib.sha1(value).hexdigest()[:8]
        return '{}_{}'.format(value[-54:], short_hash)
    return value

