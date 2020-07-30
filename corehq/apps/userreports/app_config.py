import copy

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import import_string


class UserReports(AppConfig):
    name = 'corehq.apps.userreports'

    def ready(self):
        register_filters()
        register_expressions()
        register_filter_values()


def register_filters():
    from corehq.apps.userreports.extension_points import custom_ucr_report_filters
    from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory

    for type_name, path_to_func in custom_ucr_report_filters():
        ReportFilterFactory.constructor_map[type_name] = import_string(path_to_func)


def register_expressions():
    from corehq.apps.userreports.extension_points import custom_ucr_expressions
    from corehq.apps.userreports.expressions.factory import ExpressionFactory

    expressions = copy.copy(settings.CUSTOM_UCR_EXPRESSIONS)
    expressions.extend(custom_ucr_expressions())

    for type_name, factory_function_path in expressions:
        ExpressionFactory.register(type_name, import_string(factory_function_path))


def register_filter_values():
    from corehq.apps.userreports.reports.filters.specs import FilterValueFactory
    from corehq.apps.userreports.extension_points import custom_ucr_report_filter_values
    for type_name, path_to_class in custom_ucr_report_filter_values():
        FilterValueFactory.class_map[type_name] = import_string(path_to_class)
