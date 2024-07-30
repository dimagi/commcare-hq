import inspect
from io import StringIO
from unittest.mock import patch

from testil import Regex, eq

from .. import profile


def test_profile_decorator():
    output = StringIO()
    args = []

    @profile
    def func(arg):
        args.append(arg)

    sys_stderr = inspect.signature(profile).parameters["stream"].default
    with patch.object(sys_stderr, "write", output.write):
        func(1)
    eq(args, [1])
    eq(output.getvalue(), Regex(r"test_decorators.py:\d+\(func\)"))


def test_profile_decorator_with_options():
    output = StringIO()
    args = []

    @profile(stream=output)
    def func(arg):
        args.append(arg)

    func(1)
    eq(args, [1])
    eq(output.getvalue(), Regex(r"test_decorators.py:\d+\(func\)"))


def test_profile_contextmanager():
    output = StringIO()
    args = []

    def func(arg):
        with profile(stream=output):
            args.append(arg)

    func(1)
    eq(args, [1])
    eq(output.getvalue(), Regex(r"\{method 'append' of 'list' objects\}"))
