import re


def clean_fixture_field_name(field_name):
    """Effectively slugifies a fixture's field name so that we don't send
    bad XML back from the phone. Ideally, the fixture name should be
    verified as a good slug before using it.
    """
    pattern = '([/\\<> ])'
    return re.sub(pattern, '_', field_name)
