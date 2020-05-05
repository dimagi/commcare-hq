import operator


def identity(value):
    return value


class TinyPanda:

    def __init__(self, data, op=identity):
        self.data = data
        self.op = op

    def apply(self, func):
        rep = "%s({0})" % func.__name__
        return self(Operator(func, rep))

    def __call__(self, op):
        if not isinstance(op, Operator):
            raise ValueError(f"expected operator, got {op!r}")
        if self.op is identity:
            return type(self)(self.data, op)
        return type(self)(self.data, op.apply(self.op))

    def __repr__(self):
        num = len(self.data)
        if num > 2:
            data = f"{repr(self.data[:2])[:-1]}, ... {num - 2} more]"
        else:
            data = repr(self.data)
        if self.op is identity:
            return data
        return f"[{self.op} for v in {data}]"

    def __getitem__(self, key):
        if isinstance(key, TinyPanda):
            return type(self)([v for v in self if key.op(v)])
        return self(Operator(operator.getitem, "{0}[{1}]", key))

    def get(self, key):
        def get(item):
            return item.get(key)
        return self(Operator(get, f"{{0}}.get({key!r})"))

    def __eq__(self, other):
        return self(Operator(operator.eq, "==", other))

    def __ne__(self, other):
        return self(Operator(operator.ne, "!=", other))

    def __gt__(self, other):
        return self(Operator(operator.gt, ">", other))

    def __ge__(self, other):
        return self(Operator(operator.ge, ">=", other))

    def __lt__(self, other):
        return self(Operator(operator.lt, "<", other))

    def __le__(self, other):
        return self(Operator(operator.le, "<=", other))

    def __and__(self, other):
        def and_(value):
            return self.op(value) and other.op(value)
        rep_a = self.op._repr("{0}")
        rep_b = other.op._repr("{0}")
        return type(self)(self.data, Operator(and_, f"{rep_a} and {rep_b}"))

    def __sub__(self, other):
        other = {id(b) for b in other}
        return type(self)([a for a in self if id(a) not in other])

    def __iter__(self):
        return (self.op(v) for v in self.data)

    def __len__(self):
        return len(self.data)

    def sum(self):
        return sum(self)


NOTSET = object()


class Operator:

    def __init__(self, func, rep, rhs=NOTSET):
        if "{0}" not in rep:
            assert rhs is not NOTSET, repr(rep)
            rep = "{0} %s {1}" % rep
        self.func = func
        self.rep = rep
        self.rhs = rhs

    def apply(self, op):
        if self.rhs is NOTSET:
            def apply(value):
                return self.func(op(value))
        else:
            def apply(value):
                return self.func(op(value), self.rhs)
        return Operator(apply, self._repr(op._repr("{0}")))

    def _repr(self, value):
        if self.rhs is NOTSET:
            return self.rep.format(value)
        return self.rep.format(value, repr(self.rhs))

    def __repr__(self):
        return self._repr("v")

    def __call__(self, value):
        try:
            if self.rhs is NOTSET:
                return self.func(value)
            return self.func(value, self.rhs)
        except Exception as err:
            rep = self._repr(repr(value))
            raise OperatorError(f"{rep} -> {type(err).__name__}: {err}")


class OperatorError(Exception):
    pass
