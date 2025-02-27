from functools import wraps


def override_fixture(old_fixture):
    """Override a pytest magic fixture with an unmagic fixture

    The overriding fixture function will be assigned a 'super'
    attribute that references the overridden fixture function.
    """
    def apply(new_fixture):
        @wraps(new_fixture)
        def fixture(*a, **k):
            yield from new_fixture(*a, **k)
        new_fixture.super = old_fixture.__pytest_wrapped__.obj
        old_fixture.__pytest_wrapped__.obj = fixture
        return new_fixture
    return apply
