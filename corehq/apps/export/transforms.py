from corehq.apps.users.util import cached_user_id_to_username


def user_id_to_username(user_id, doc):
    return cached_user_id_to_username(user_id)
