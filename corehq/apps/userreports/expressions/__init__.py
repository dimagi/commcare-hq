from django.conf import settings
from django.utils.module_loading import import_string
from corehq.apps.userreports.expressions.factory import ExpressionFactory


def get_custom_ucr_expressions():
    custom_ucr_expressions = settings.CUSTOM_UCR_EXPRESSIONS

    for expression_list in settings.CUSTOM_UCR_EXPRESSION_LISTS:
        custom_ucr_expressions += import_string(expression_list)

    return custom_ucr_expressions

# Bootstrap plugin expressions
for type_name, factory_function_path in get_custom_ucr_expressions():
    ExpressionFactory.register(type_name, import_string(factory_function_path))
