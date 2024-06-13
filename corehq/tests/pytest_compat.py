import sys
from functools import wraps


def _install_pytest_compat():
    assert 'pytest' not in sys.modules, "Already installed or a real pytest is present"
    sys.modules['pytest'] = sys.modules[__name__]


class Marker:

    def __getattr__(self, name):
        def set_attribute(test_obj):
            setattr(test_obj, name, True)
            return test_obj
        return set_attribute

    def parametrize(self, arg_names, args_tuples):
        def parametrize(func):
            @wraps(func)
            def test():
                test_tuple = (func,)
                test = (func,)
                for args in args_tuples:
                    if "," not in arg_names and (
                        not isinstance(args, tuple)
                        or len(args) != 1
                    ):
                        args = (args,)
                    elif isinstance(args, list) and len(args) == arg_names.count(",") + 1:
                        args = tuple(args)
                    try:
                        test_tuple = test + args
                    except TypeError:
                        raise TypeError(f"could not construct test tuple for {func} with args {args!r}")
                    yield test_tuple
            return test
        return parametrize


mark = Marker()

_install_pytest_compat()
