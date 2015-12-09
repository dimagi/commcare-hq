import re

BAD_SLUG_PATTERN = r"([/\\<>\s])"


def clean_fixture_field_name(field_name):
    """Effectively slugifies a fixture's field name so that we don't send
    bad XML back from the phone. Ideally, the fixture name should be
    verified as a good slug before using it.
    """
    subbed_string = re.sub(BAD_SLUG_PATTERN, '_', field_name)
    if subbed_string.startswith('xml'):
        subbed_string = subbed_string.replace('xml', '_', 1)
    return subbed_string


def is_field_name_invalid(field_name):
    return bool(re.search(BAD_SLUG_PATTERN, field_name))
