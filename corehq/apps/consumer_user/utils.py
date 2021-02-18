CONCATENATED_STRING = ':beneficiary'


def hash_username_from_email(email):
    return '%s%s' % (email, CONCATENATED_STRING)


def get_email_from_hashed_username(username):
    if username.endswith(CONCATENATED_STRING):
        return username[:-len(CONCATENATED_STRING)]
    return username
