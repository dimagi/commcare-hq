from __future__ import absolute_import

from django.conf import settings
from django.utils.module_loading import import_string

from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.apps.userreports.reports.filters.specs import ReportFilter

for type_name, path_to_class in settings.CUSTOM_UCR_REPORT_FILTER_VALUES:
    ReportFilter._class_map[type_name] = import_string(path_to_class)

for type_name, path_to_func in settings.CUSTOM_UCR_REPORT_FILTERS:
    ReportFilterFactory.constructor_map[type_name] = import_string(path_to_func)
