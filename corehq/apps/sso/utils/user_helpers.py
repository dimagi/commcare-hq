def get_email_domain_from_username(username):
    """
    A quick utility for getting an Email Domain from a username
    (the last part of the email after the '@' sign)
    :param username: String
    :return: Domain name string. `None` if there is no domain name.
    """
    split_username = username.split('@')
    if len(split_username) < 2:
        # Not a real email address with an expected email domain.
        return None
    # we take the last split because `@` is technically an allowed character if
    # inside a quoted string.
    # See https://en.wikipedia.org/wiki/Email_address#Local-part
    return split_username[-1]
