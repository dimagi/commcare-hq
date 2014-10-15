class Corpus(object):
    """
    creates an object to be used with CorpusMeta to add many similar tests
    that assert the output of a function
    matches a given list of inputs and outputs

    >>> import unittest
    >>> def my_fn(n):
    ...     assert n >= 0
    ...     if n == 0:
    ...         return 1
    >>> class MyFnTest(unittest.TestCase):
    ...     __metaclass__ = CorpusMeta
    ...     my_corpus = Corpus(my_fn, {
    ...         'zero_gives_one': (0, 1),
    ...         'negative': (-1, Raise(AssertionError)),
    ...         'other': (5, None),
    ...     })

    MyFnTest will end up with functions:

        test_my_corpus__zero_gives_one
        test_my_corpus__negative
        test_my_corpus__other

    testing those conditions

    Args:
        fn (function): function to test
        corpus (dict of string => (value or Call, value or CallResult)):
            dict of short test name to input/output case

    Returns:
        A class (subclassing object) with one method per item in corpus.

    """
    def __init__(self, fn, corpus):
        self.fn = fn
        self.corpus = corpus

    def get_test_functions(self):
        dct = {}
        fn = self.fn

        def _func_name(fn):
            try:
                return fn.func_name
            except AttributeError:
                return fn.__name__

        def _make_test(input_call, call_result):
            def _test(self):
                call_result.check(self, input_call, fn)

            _test.__doc__ = ('call {}{!r}, expected outcome is {!r}'
                             .format(_func_name(fn), input_call, call_result))
            return _test

        for name, (input_call, call_result) in self.corpus.items():
            if not isinstance(input_call, Call):
                input_call = Call(input_call)
            if not isinstance(call_result, CallResult):
                call_result = Return(call_result)
            dct[name] = _make_test(input_call, call_result)

        return dct


class CorpusMeta(type):
    def __new__(mcs, cls_name, bases, dct):
        corpuses = []
        for key, value in dct.items():
            if isinstance(value, Corpus):
                del dct[key]
                corpuses.append((key, value))

        for corpus_name, corpus in corpuses:
            if not corpus_name.startswith('test'):
                corpus_name = 'test_{}'.format(corpus_name)
            for slug, test_function in corpus.get_test_functions().items():
                dct['{}__{}'.format(corpus_name, slug)] = test_function

        return super(CorpusMeta, mcs).__new__(mcs, cls_name, bases, dct)


class Call(object):
    """
    Call objects have the following property:

    Call(*args, **kwargs)(fn) == fn(*args, **kwargs)

    In other words, Call objects can be used
    to store the 'call context', e.g. args and kwargs,
    deferring the actual call.

    This can be useful for calling the same function in a bunch of ways:

    >>> hypotenuse = lambda x, y: (x**2 + y**2) ** .5
    >>> calls = [Call(1, 1), Call(3, 4), Call(4, 3), Call(6, 8)]
    >>> [call(hypotenuse) for call in calls]
    [1.4142135623730951, 5.0, 5.0, 10.0]

    Call was designed for use as Corpus input

    """
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, fn):
        return fn(*self.args, **self.kwargs)

    def __repr__(self):
        return u'({})'.format(', '.join(
            [repr(arg) for arg in self.args]
            + ['{}={}'.format(key, repr(value))
               for key, value in self.kwargs.items()]
        ))


class CallResult(object):
    """
    Abstract base class

    Designed for use as Corpus output
    """

    def __init__(self, value):
        self.value = value

    def check(self, test_instance, input_call, fn):
        raise NotImplementedError()

    def __repr__(self):
        return u'{}({!r})'.format(self.__class__.__name__, self.value)


class Return(CallResult):
    """
    Can be used with Corpus as follows

    class MyTest(unittest.TestCase):
        ...
        test_hypotenuse = Corpus(hypotenuse, {
            '3_4_5': (Call(3, 4), Return(5.0)),
        })

    """
    def check(self, test_instance, input_call, fn):
        test_instance.assertEqual(input_call(fn), self.value)


class Raise(CallResult):
    """
    Can be used with Corpus as follows

    class MyTest(unittest.TestCase):
        ...
        test_hypotenuse = Corpus(hypotenuse, {
            '3_4_5': (Call('3', 4), Raises(TypeError)),
        })

    """

    def __init__(self, value):
        super(Raise, self).__init__(value)
        assert issubclass(value, Exception)

    def check(self, test_instance, input_call, fn):
        with test_instance.assertRaises(self.value):
            input_call(fn)

    def __repr__(self):
        return u'{}({})'.format(self.__class__.__name__, self.value.__name__)
