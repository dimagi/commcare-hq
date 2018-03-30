from __future__ import absolute_import

from operator import gt

from jsonpath_rw import JSONPath, Fields


class Cmp(JSONPath):
    """
    A JSONPath expression that supports value comparison

    >>> jsonpath = Cmp(Fields('spam'), gt, 0)
    >>> matches = jsonpath.find({"spam": 10, "baked beans": 1})
    >>> matches[0].value
    10

    """
    def __init__(self, jsonpath, operator, operand):
        if not hasattr(operator, '__call__'):
            raise ValueError('operator must be callable')
        self.jsonpath = jsonpath
        self.op = operator
        self.operand = operand

    def find(self, data):
        return [match for match in self.jsonpath.find(data) if self.op(match.value, self.operand)]

    def __str__(self):
        return '{jsonpath} {op} {operand}'.format(
            jsonpath=self.jsonpath, op=self.op.__name__, operand=repr(self.operand)
        )

    def __eq__(self, other):
        return (
            isinstance(other, Cmp) and
            other.jsonpath == self.jsonpath and
            other.op == self.op and
            other.operand == self.operand
        )
