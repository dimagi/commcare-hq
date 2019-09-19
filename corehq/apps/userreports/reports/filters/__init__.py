from django.conf import settings
from django.utils.module_loading import import_string

from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory

for type_name, path_to_func in settings.CUSTOM_UCR_REPORT_FILTERS:
    ReportFilterFactory.constructor_map[type_name] = import_string(path_to_func)
