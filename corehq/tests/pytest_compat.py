import sys


def _install_pytest_compat():
    assert 'pytest' not in sys.modules, "Already installed or a real pytest is present"
    sys.modules['pytest'] = sys.modules[__name__]


class Marker:

    def __getattr__(self, name):
        def set_attribute(test_obj):
            setattr(test_obj, name, True)
            return test_obj
        return set_attribute


mark = Marker()

_install_pytest_compat()
