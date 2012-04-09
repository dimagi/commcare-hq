import functools
from inspect import isfunction
import json
from couchdbkit.ext.django.schema import StringProperty
from dimagi.utils.modules import to_function
from dimagi.utils.web import json_handler

def intersect_filters(*args):
    filters = [fn for fn in args if fn]
    if filters:
        def filter(doc):
            for fn in filters:
                if not fn(doc):
                    return False
            return True
    else:
        filter = None
    return filter

class FilterFunction(object):
    def __init__(self, function=None, **kwargs):
        self.functions = []
        if function:
            self.add(function, **kwargs)

    def add(self, function, **kwargs):
        self.functions.append((function, kwargs))

    def __iand__(self, other):
        self.functions.extend(other.functions)
        return self

    def __and__(self, other):
        if other is None:
            other = FilterFunction()
        if isfunction(other):
            other = FilterFunction(other)
        f = FilterFunction()
        f &= self
        f &= other
        return f

    def __call__(self, doc):
        if self.functions:
            return intersect_filters(*[functools.partial(f, **kwargs) for (f, kwargs) in self.functions])(doc)
        else:
            return True

    def dumps(self):
        functions = []
        for f, kwargs in self.functions:
            for key in kwargs:
                try:
                    kwargs[key] = kwargs[key].to_dict()
                except (AttributeError, TypeError):
                    pass
            functions.append({
                'function': '%s.%s' % (f.__module__, f.__name__),
                'kwargs': kwargs
            })
        return json.dumps(functions, default=json_handler)

    @classmethod
    def loads(cls, data):
        functions = json.loads(data)
        self = cls()
        for o in functions:
            f, kwargs = o['function'], o['kwargs']
            f = to_function(f)
            self.add(f, **kwargs)
        return self

class FilterFunctionProperty(object):

    def __init__(self, target):
        self.target = target

    def __get__(self, parent, parent_cls):
        data = getattr(parent, self.target)
        if not data:
            return FilterFunction()
        try:
            return FilterFunction.loads(data)
        except ValueError:
            return FilterFunction(to_function(data))

    def __set__(self, parent, function):
        if isfunction(function):
            function = FilterFunction(function)
        setattr(parent, self.target, function.dumps())
