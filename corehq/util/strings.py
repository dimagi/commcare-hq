def get_masked_string(value, mask_character=None, reveal_length=3):
    if mask_character is None:
        mask_character = '*'

    if len(value) <= reveal_length:
        return value

    return value[:reveal_length] + mask_character * (len(value) - reveal_length)
