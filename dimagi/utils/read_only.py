from inspect import isgenerator


class ReadOnlyObject(object):
    """
    >>> from couchdbkit import *
    >>>
    >>>
    >>> class Thing(Document):
    ...     words = StringListProperty()
    ...     @property
    ...     def calc(self):
    ...         for i, word in enumerate(self.words):
    ...             print i
    ...             yield word + '!'
    ...
    >>> thing = Thing(words=['danny', 'is', 'so', 'clever'])
    >>> thing = ReadOnlyObject(thing)
    >>> thing.words
    ['danny', 'is', 'so', 'clever']
    >>> thing.words
    ['danny', 'is', 'so', 'clever']
    >>> thing.words is thing.words
    True
    >>> thing.calc
    0
    1
    2
    3
    ['danny!', 'is!', 'so!', 'clever!']
    >>> thing.calc
    ['danny!', 'is!', 'so!', 'clever!']
    >>> thing.calc is thing.calc
    True
    """

    def __init__(self, obj):
        self._obj = obj

    def __getitem__(self, item):
        return self._obj[item]

    def __getattr__(self, item):
        value = getattr(self._obj, item)
        if isgenerator(value):
            # generator **functions** will be returned as is,
            # but if it's i.e. a @property, then you don't want to memoize
            # a generator
            value = list(value)

        setattr(self, item, value)
        return value
