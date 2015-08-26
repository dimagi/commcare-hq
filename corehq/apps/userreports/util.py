import collections


def localize(value, lang):
    """
    Localize the given value.

    This function is intended to be used within UCR to localize user supplied
    translations.

    :param value: A dict-like object or string
    :param lang: A language code.
    """
    if isinstance(value, collections.Mapping) and len(value):
        return (
            value.get(lang, None) or
            value.get(default_language(), None) or
            value[sorted(value.keys())[0]]
        )
    return value


def default_language():
    return "en"
