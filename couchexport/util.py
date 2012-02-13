import functools

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
        f = FilterFunction()
        f &= self
        f &= other
        return f

    def __call__(self, doc):
        if self.functions:
            return intersect_filters(*[functools.partial(f, **kwargs) for (f, kwargs) in self.functions])(doc)
        else:
            return True
