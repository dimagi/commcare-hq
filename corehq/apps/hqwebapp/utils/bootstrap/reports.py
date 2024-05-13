from corehq.apps.hqwebapp.utils.bootstrap.paths import is_bootstrap3_path

REPORT_TEMPLATE_PROPERTIES = [
    ('template_base', 'base_template'),
    ('template_async_base', 'base_template_async'),
    ('template_report', 'report_template_path'),
    ('template_report_partial', 'report_partial_path'),
    ('template_filters', 'base_template_filters'),
]
COMMON_REPORT_TEMPLATES = [
    "reports/async/bootstrap3/default.html",
    "reports/standard/bootstrap3/base_template.html",
    "reports/bootstrap3/tabular.html",
]
MIGRATED_FILTER_TEMPLATES = [
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
    for report_property, related_variable in REPORT_TEMPLATE_PROPERTIES:
        property_issues = show_report_property_issues(report_instance, report_property)
        variable_issues = show_report_class_variable_issues(report_instance, report_property)
        has_issues = has_issues or property_issues or variable_issues

    if not has_issues:
        print(f"\n{Color.GREEN}{Color.BOLD}Did not find any template "
              f"reference issues!{Color.ENDC}\n\n")

    show_report_filters_templates(report_instance)


def show_report_property_issues(report_instance, report_property):
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
    print(f"\n{Color.CYAN}{Color.BOLD}Next, make sure these templates for "
          f"the report's filters are fully migrated:{Color.ENDC}\n\n")
    has_pending_migrations = False
    for report_filter in report_instance.filter_classes:
        if report_filter not in MIGRATED_FILTER_TEMPLATES:
            print(f"{Color.BOLD}{report_filter.template}{Color.ENDC} ({_name(report_filter)})")
            has_pending_migrations = True

    if not has_pending_migrations:
        print(f"{Color.GREEN}{Color.BOLD}No migrations needed!{Color.ENDC}\n\n")
    print("\n\n")
