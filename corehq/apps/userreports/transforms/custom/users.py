from corehq.apps.users.util import (
    cached_owner_id_to_display,
    cached_user_id_to_username,
)

# these are just aliased here to make it clear what is supported
get_user_display = cached_user_id_to_username
get_owner_display = cached_owner_id_to_display


def get_user_without_domain_display(user_id):
    full_username = cached_user_id_to_username(user_id)
    if full_username:
        return full_username.split('@')[0]
    return full_username
