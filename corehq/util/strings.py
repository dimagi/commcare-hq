def get_masked_string(value, mask_character='*', reveal_length=3, reverse_reveal=False):
    """Mask all but ``reveal_length`` characters of ``value`` with
    ``mask_character``.

    :param reverse_reveal: reveals characters at the end of the string instead
    of the start.
    """
    mask_length = max(len(value) - reveal_length, 0)
    masking = mask_character * mask_length
    if reverse_reveal:
        return masking + value[mask_length:]
    return value[:reveal_length] + masking


def get_masked_email(email, mask_character='*', reveal_length=1):
    """Mask all but ``reveal_length`` characters of a valid email's local
    portion with ``mask_character``.
    """
    email_parts = email.rsplit('@', 1)
    email_parts[0] = get_masked_string(
        email_parts[0],
        mask_character=mask_character,
        reveal_length=reveal_length,
    )
    return '@'.join(email_parts)
