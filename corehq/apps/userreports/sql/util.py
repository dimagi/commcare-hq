from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib


def get_column_name(path, suffix=None):
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
        front = front.encode('unicode-escape')
        end = end.encode('unicode-escape')
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(front).hexdigest(), end)).hexdigest()[:8]

    new_parts = path.split("/")
    full_name = "_".join(filter(None, new_parts + [_hash(parts), suffix]))
    return full_name[-63:]
