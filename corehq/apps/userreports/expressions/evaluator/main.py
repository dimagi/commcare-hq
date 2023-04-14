import ast
import copy
import dataclasses
import operator
from datetime import date, datetime
from decimal import Decimal

from simpleeval import (
    DEFAULT_OPERATORS,
    FeatureNotAvailable,
    InvalidExpression,
    DISALLOW_FUNCTIONS,
    FunctionNotDefined,
    EvalWithCompoundTypes,
)

from .functions import FUNCTIONS
from ...specs import EvaluationContext, FactoryContext


def safe_pow_fn(a, b):
    raise InvalidExpression


SAFE_TYPES = {float, Decimal, date, datetime, type(None), bool, int, str, dict, list}

SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS[ast.Pow] = safe_pow_fn  # don't allow power operations
SAFE_OPERATORS[ast.Not] = operator.not_


class EvalNoMethods(EvalWithCompoundTypes):
    """Disallow method calls. No real reason for this except that it gives
    users less options to do crazy things that might get them / us into
    hard to back out of situations."""

    def set_context(self, context):
        self._context = context

    def _eval_call(self, node):
        if isinstance(node.func, ast.Attribute):
            raise FeatureNotAvailable("Method calls not allowed.")

        try:
            func = self.functions[node.func.id]
        except KeyError:
            raise FunctionNotDefined(node.func.id, self.expr)
        except AttributeError as e:
            raise FeatureNotAvailable('Lambda Functions not implemented')

        if func in DISALLOW_FUNCTIONS:
            raise FeatureNotAvailable('This function is forbidden')

        if "_bound_context" in node.keywords:
            raise FeatureNotAvailable("Use of reserved keyword is not allowed")

        kwargs = dict(self._eval(k) for k in node.keywords)
        if getattr(func, 'bind_context', False):
            kwargs["_bound_context"] = self._context

        return func(
            *(self._eval(a) for a in node.args),
            **kwargs
        )


def eval_statements(statement, variable_context, eval_context=None):
    """Evaluates math statements and returns the value

    args
        statement: a simple python-like math statement
        variable_context: a dict with variable names as key and assigned values as dict values
    """
    eval_context = eval_context or EvalContext(EvaluationContext.empty(), FactoryContext.empty())
    var_types = set(type(value) for value in variable_context.values())
    if not var_types.issubset(SAFE_TYPES):
        raise InvalidExpression('Context contains disallowed types')

    evaluator = EvalNoMethods(operators=SAFE_OPERATORS, names=variable_context, functions=FUNCTIONS)
    evaluator.set_context(eval_context.for_eval(evaluator))
    return evaluator.eval(statement)


@dataclasses.dataclass(frozen=True)
class EvalContext:
    evaluation_context: EvaluationContext
    factory_context: FactoryContext
    evaluator: EvalNoMethods = None

    def for_eval(self, evaluator):
        return dataclasses.replace(self, evaluator=evaluator)

    @property
    def names(self):
        return self.evaluator.names if self.evaluator else {}

    @property
    def root_context(self):
        return self.evaluation_context.root_doc

    def eval_spec(self, spec, item):
        expr = self.factory_context.expression_from_spec(spec)
        return expr(item, self.evaluation_context)
