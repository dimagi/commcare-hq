from corehq.apps.hqwebapp.utils.bootstrap.paths import is_bootstrap3_path, get_bootstrap5_path
from corehq.apps.hqwebapp.utils.bootstrap.reports.progress import (
    get_migrated_filters,
    get_migrated_filter_templates,
)
from corehq.apps.reports.datatables import DataTablesColumnGroup

REPORT_TEMPLATE_PROPERTIES = [
    ('template_base', 'base_template'),
    ('template_async_base', 'base_template_async'),
    ('template_report', 'report_template_path'),
    ('template_report_partial', 'report_partial_path'),
    ('template_filters', 'base_template_filters'),
    (None, 'override_template'),  # override_template is another alternate for template_report
]
COMMON_REPORT_TEMPLATES = [
    "reports/async/bootstrap3/default.html",
    "reports/bootstrap3/base_template.html",
    "reports/standard/bootstrap3/base_template.html",
    "reports/bootstrap3/tabular.html",
]


class Color:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


def _name(instance):
    return instance.__class__.__name__


def reports_bootstrap5_template_debugger(report_instance):
    has_issues = False
    print(f"\n\n{Color.CYAN}{Color.BOLD}DEBUGGING Bootstrap 5 in "
          f"{_name(report_instance)} Report{Color.ENDC}\n")

    print(f"{Color.BOLD}Checking for report template issues...{Color.ENDC}")
    for class_property, class_variable in REPORT_TEMPLATE_PROPERTIES:
        property_issues = show_report_property_issues(report_instance, class_property)
        variable_issues = show_report_class_variable_issues(report_instance, class_variable)
        has_issues = has_issues or property_issues or variable_issues

    if not has_issues:
        print(f"\n{Color.GREEN}{Color.BOLD}Did not find any issues!{Color.ENDC}\n")

    show_report_filters_templates(report_instance)
    show_report_column_issues(report_instance)
    print("\n\nWhen migration is complete, remember to run:\n")
    print(f"{Color.BOLD}manage.py complete_bootstrap5_report {_name(report_instance)}{Color.ENDC}\n\n\n\n")


def show_report_property_issues(report_instance, report_property):
    if report_property is None:
        return False
    report_property_value = getattr(report_instance, report_property)
    if is_bootstrap3_path(report_property_value):
        print(f"\n{Color.WARNING}{Color.BOLD}def {report_property}"
              f"\nreturns {report_property_value}{Color.ENDC}")
        print(f"\nCheck if any overrides of {Color.BOLD}{report_property}{Color.ENDC} "
              f"in {Color.BOLD}{_name(report_instance)}{Color.ENDC} return a bootstrap3 template.\n\n")
        return True
    return False


def show_report_class_variable_issues(report_instance, related_variable):
    related_variable_value = getattr(report_instance, related_variable)
    if (is_bootstrap3_path(related_variable_value)
            and related_variable_value not in COMMON_REPORT_TEMPLATES):
        print(f"\n{Color.WARNING}{Color.BOLD}{related_variable} "
              f"= {related_variable_value}{Color.ENDC}")
        print(f"\nEnsure that {Color.BOLD}{_name(report_instance)}.{related_variable}{Color.ENDC} "
              f"is not assigned to a bootstrap3 template.\n\n")
        return True
    return False


def show_report_filters_templates(report_instance):
    from corehq.apps.reports.generic import get_filter_class
    print(f"\n{Color.BOLD}Checking for un-migrated report filters and templates:{Color.ENDC}\n")
    has_pending_migrations = False
    migrated_filters = get_migrated_filters()
    migrated_filter_templates = get_migrated_filter_templates()
    for field in report_instance.fields:
        if field not in migrated_filters:
            filter_class = get_filter_class(field)
            filter_template = get_bootstrap5_path(filter_class.template)
            print(f"{Color.WARNING}{Color.BOLD}{filter_class.__name__}{Color.ENDC}")
            if filter_template not in migrated_filter_templates:
                print(f"\t{filter_template}\n")
            has_pending_migrations = True

    if not has_pending_migrations:
        print(f"{Color.GREEN}{Color.BOLD}No migrations needed!{Color.ENDC}\n")
    print("\n\n")


def show_report_column_issues(report_instance):
    for column in report_instance.headers:
        if isinstance(column, DataTablesColumnGroup):
            for sub_column in column:
                _print_column_warnings(sub_column)
        else:
            _print_column_warnings(column)


def _print_column_warnings(column):
    if not column.use_bootstrap5:
        print(f"{Color.WARNING}{Color.BOLD}The DataTablesColumn for '{column.html}' does "
              f"not have bootstrap5 enabled. Pass `use_bootstrap5=self.use_bootstrap5` "
              f"when creating.{Color.ENDC}")
