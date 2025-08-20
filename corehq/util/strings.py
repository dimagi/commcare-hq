def get_masked_string(value, mask_character='*', reveal_length=3):
    if len(value) <= reveal_length:
        return value

    return value[:reveal_length] + mask_character * (len(value) - reveal_length)
