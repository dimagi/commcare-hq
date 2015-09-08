from django.conf import settings
from django.utils.module_loading import import_string
from corehq.apps.userreports.expressions.factory import ExpressionFactory

# Bootstrap plugin expressions
for type_name, factory_function_path in settings.CUSTOM_UCR_EXPRESSIONS:
    ExpressionFactory.register(type_name, import_string(factory_function_path))
