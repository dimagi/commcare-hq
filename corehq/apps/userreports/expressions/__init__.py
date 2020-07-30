import copy

from django.conf import settings
from django.utils.module_loading import import_string

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.extension_points import custom_ucr_expressions


def get_custom_ucr_expressions():
    expressions = copy.copy(settings.CUSTOM_UCR_EXPRESSIONS)
    expressions.extend(custom_ucr_expressions())
    return expressions


# Bootstrap plugin expressions
for type_name, factory_function_path in get_custom_ucr_expressions():
    ExpressionFactory.register(type_name, import_string(factory_function_path))
