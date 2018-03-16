from __future__ import absolute_import

from jsonpath_rw import JSONPath


class WhereCmp(JSONPath):
    """
    WhereCmp is similar to Where, but allows value comparison instead of just
    checking for existence.
    """
    def __init__(self, left, right, operator, operand):
        if not hasattr(operator, '__call__'):
            raise ValueError('operator must be callable')
        self.left = left
        self.right = right
        self.op = operator
        self.operand = operand

    def find(self, data):
        return [subdata for subdata in self.left.find(data)
                if any(self.op(match.value, self.operand) for match in self.right.find(subdata))]

    def __str__(self):
        return '({left} where {right} {op} {operand})'.format(
            left=self.left, right=self.right, op=self.op.__name__, operand=repr(self.operand)
        )

    def __eq__(self, other):
        return (
                isinstance(other, WhereCmp) and
                other.left == self.left and
                other.right == self.right and
                other.op == self.op and
                other.operand == self.operand
        )
