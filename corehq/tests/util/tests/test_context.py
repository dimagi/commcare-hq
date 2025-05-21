from itertools import count

from ..context import testcontextmanager


def test_multi_use_testcontextmanager():
    context, calls = make_context()

    @context
    def test(num):
        calls.append(num)

    with context():
        calls.append(0)
    with context():
        calls.append(1)
    test(2)

    assert calls == [10, 0, 10, 11, 1, 11, 12, 2, 12]


def test_nested_testcontextmanager():
    context, calls = make_context()

    @context
    def test(num):
        calls.append(num)

    with context():
        calls.append(0)
        with context():
            calls.append(1)
            test(2)

    assert calls == [10, 0, 11, 1, 12, 2, 12, 11, 10]


def make_context():
    @testcontextmanager
    def context():
        num = next(seq)
        calls.append(num)
        yield
        calls.append(num)

    seq = iter(count(10))
    calls = []
    return context, calls
