from functools import wraps


def override_fixture(old_fixture):
    """Override a pytest magic fixture with an unmagic fixture"""
    def apply(new_fixture):
        @wraps(new_fixture)
        def fixture(*a, **k):
            yield from new_fixture(*a, **k)
        old_fixture.__pytest_wrapped__.obj = fixture
        return new_fixture
    return apply
