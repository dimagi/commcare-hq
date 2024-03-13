import ast
import copy
import dataclasses
import operator
from datetime import date, datetime
from decimal import Decimal

from corehq.util import eval_lazy
from simpleeval import (
    DEFAULT_OPERATORS,
    FeatureNotAvailable,
    InvalidExpression,
    DISALLOW_FUNCTIONS,
    FunctionNotDefined,
    EvalWithCompoundTypes,
)

from .functions import FUNCTIONS, CONTEXT_PARAM_NAME, NEEDS_CONTEXT_PARAM_NAME
from ...specs import EvaluationContext, FactoryContext


def safe_pow_fn(a, b):
    raise InvalidExpression


SAFE_TYPES = {float, Decimal, date, datetime, type(None), bool, int, str, dict, list}

SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS[ast.Pow] = safe_pow_fn  # don't allow power operations
SAFE_OPERATORS[ast.Not] = operator.not_


class CommCareEval(EvalWithCompoundTypes):
    """Disallow method calls. No real reason for this except that it gives
    users less options to do crazy things that might get them / us into
    hard to back out of situations."""

    def set_context(self, context):
        self._context = context.scope(self)

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
        if getattr(func, NEEDS_CONTEXT_PARAM_NAME, False):
            kwargs[CONTEXT_PARAM_NAME] = self._context

        return func(
            *(self._eval(a) for a in node.args),
            **kwargs
        )


def eval_statements(statement, variable_context, execution_context=None):
    """Evaluates math statements and returns the value

    args
        statement: a simple python-like math statement
        variable_context: a dict with variable names as key and assigned values as dict values
    """
    execution_context = execution_context or EvalExecutionContext.empty()
    var_types = set(type(eval_lazy(value)) for value in variable_context.values())
    if not var_types.issubset(SAFE_TYPES):
        raise InvalidExpression('Context contains disallowed types')

    evaluator = CommCareEval(operators=SAFE_OPERATORS, names=variable_context, functions=FUNCTIONS)
    evaluator.set_context(execution_context)
    return evaluator.eval(statement)


@dataclasses.dataclass(frozen=True)
class EvalExecutionContext:
    evaluation_context: EvaluationContext
    factory_context: FactoryContext
    evaluator: CommCareEval = None
    
    @classmethod
    def empty(cls):
        return EvalExecutionContext(EvaluationContext.empty(), FactoryContext.empty())

    def scope(self, evaluator):
        """Scope this context to a specific evaluator."""
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
