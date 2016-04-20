import hashlib


def truncate_value(value, max_length=63, from_left=True):
    """
    Truncate a value (typically a column name) to a certain number of characters,
    using a hash to ensure uniqueness.
    """
    hash_length = 8
    truncated_length = max_length - hash_length - 1
    if from_left:
        truncated_value = value[-truncated_length:]
    else:
        truncated_value = value[:truncated_length]

    if len(value) > max_length:
        short_hash = hashlib.sha1(value).hexdigest()[:hash_length]
        return '{}_{}'.format(truncated_value, short_hash)
    return value


def get_table_name(domain, table_id):
    def _hash(domain, table_id):
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(domain).hexdigest(), table_id)).hexdigest()[:8]

    return truncate_value(
        'config_report_{}_{}_{}'.format(domain, table_id, _hash(domain, table_id)),
        from_left=False
    )


def get_column_name(path):
    """
    :param path: xpath from form or case
    :return: column name for postgres

    Postgres only allows columns up to 63 characters
    Anyone viewing the table directly will want to know the last parts of the path, not the first parts e.g.
    this: 'my_long_choice_list_option_1_ABCDEFGH', 'my_long_choice_list_option_2_ABCD1234'
    not: 'question_group_1_my_long_choice_ABCDEFGH', 'question_group_1_my_long_choice_ABCD1234'
    """
    parts = path.split("/")

    def _hash(parts):
        front = "/".join(parts[:-1])
        end = parts[-1]
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(front).hexdigest(), end)).hexdigest()[:8]

    new_parts = path[-54:].split("/")
    return "_".join(new_parts + [_hash(parts)])
