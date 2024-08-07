import re


def get_email_domain_from_username(username):
    """
    A quick utility for getting an Email Domain from a username
    (the last part of the email after the '@' sign)
    :param username: String
    :return: Domain name string. `None` if there is no domain name (or username is otherwise invalid).
    """
    split_username = username.split('@')
    if len(split_username) != 2:
        # Not a real email address with an expected email domain.
        return
    if not re.match(r"^[a-z0-9!#$%&'*+=?^_‘{|}~-]+(?:\.[a-z0-9!#$%&'*+=?^_‘{|}~-]+)*$", split_username[0]):
        # not a real email address as the username contains invalid characters
        return
    return split_username[-1]


def convert_emails_to_lowercase(emails):
    # Convert each email in the list to lowercase
    lowercase_emails = [email.lower() for email in emails]
    return lowercase_emails
