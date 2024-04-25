from django.core.management import BaseCommand

from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    flag_bootstrap3_references_in_template,
    flag_bootstrap3_references_in_javascript, get_spec,
)
from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    get_all_template_paths_for_app,
    get_all_javascript_paths_for_app,
    get_short_path,
)
from corehq.apps.hqwebapp.utils.bootstrap.status import (
    get_apps_completed_or_in_progress,
    get_completed_templates_for_app,
    get_completed_javascript_for_app,
)
from corehq.apps.hqwebapp.utils.management_commands import get_break_line


IGNORED_FILES = [
    "hqwebapp/js/resource_versions.js",
    "hqwebapp/base.html",
    "hqwebapp/base_mobile.html",
    "hqwebapp/crispy/checkbox_widget.html",
    "hqwebapp/crispy/form_actions.html",
    "hqwebapp/crispy/text_field.html",
    "hqwebapp/crispy/accordion_group.html",
    "hqwebapp/crispy/static_field.html",
    "hqwebapp/crispy/radioselect.html",
    "hqwebapp/crispy/multi_field.html",
    "hqwebapp/crispy/field_with_help_bubble.html",
    "hqwebapp/crispy/field_with_addons.html",
    "hqwebapp/includes/inactivity_modal_data.html",
    "hqwebapp/includes/core_libraries.html",
    "hqwebapp/includes/ui_element_js.html",
    "hqwebapp/partials/requirejs.html",
    # todo, update these files:
    "hqwebapp/iframe_domain_login.html",
    "hqwebapp/bulk_upload.html",
    "hqwebapp/crispy/single_crispy_form.html",
    "hqwebapp/spec/mocha.html",
    "hqwebapp/js/maintenance_alerts.js",
    "hqwebapp/spec/widgets_spec.js",
]


def _is_split_path(path):
    path = str(path)
    return "/bootstrap3/" in path or "/bootstrap5/" in path


def _is_relevant_path(path, completed_paths):
    return not (_is_split_path(path) or str(path) in completed_paths)


def _get_bootstrap3_flags_from_file(file_path, is_template):
    flagged_lines = []
    with open(file_path, 'r') as current_file:
        lines = current_file.readlines()
        for line_number, line in enumerate(lines):
            if is_template:
                flags = flag_bootstrap3_references_in_template(
                    line, get_spec('bootstrap_3_to_5')
                )
            else:
                flags = flag_bootstrap3_references_in_javascript(line)
            if flags:
                flagged_lines.append([
                    line_number, flags
                ])
    return flagged_lines


def _get_flagged_files(app_name, paths, is_template):
    flagged_files = []
    for path in paths:
        short_path = get_short_path(app_name, path, is_template)
        if short_path in IGNORED_FILES:
            continue
        flagged_lines = _get_bootstrap3_flags_from_file(path, is_template)
        if flagged_lines:
            flagged_files.append([
                short_path,
                flagged_lines,
            ])
    return flagged_files


def _get_flagged_templates(app_name):
    completed_templates = [str(t) for t in get_completed_templates_for_app(app_name)]
    template_paths = [path for path in get_all_template_paths_for_app(app_name)
                      if _is_relevant_path(path, completed_templates)]
    flagged_templates = _get_flagged_files(app_name, template_paths, is_template=True)
    return flagged_templates


def _get_flagged_javascript(app_name):
    completed_javascript = [str(j) for j in get_completed_javascript_for_app(app_name)]
    javascript_paths = [path for path in get_all_javascript_paths_for_app(app_name)
                        if _is_relevant_path(path, completed_javascript)]
    flagged_javascript = _get_flagged_files(app_name, javascript_paths, is_template=False)
    return flagged_javascript


def get_app_issues():
    apps_completed_or_in_progress = get_apps_completed_or_in_progress()
    app_issues = []
    for app_name in apps_completed_or_in_progress:
        flagged_templates = _get_flagged_templates(app_name)
        flagged_javascript = _get_flagged_javascript(app_name)

        issues = {}
        if flagged_templates:
            issues['templates'] = flagged_templates
        if flagged_javascript:
            issues['javascript'] = flagged_javascript
        if issues:
            app_issues.append([
                app_name,
                issues
            ])
    return app_issues


class Command(BaseCommand):
    help = """
    This command lists any issues with apps that break Bootstrap 3 to 5 Migration expectations.
    """

    def handle(self, *args, **options):
        app_issues = get_app_issues()
        if not app_issues:
            self.stdout.write(self.style.SUCCESS(
                "\n\nThere are no issues.\n"
            ))
            return

        for summary in app_issues:
            app_name = summary[0]
            self.stdout.write(self.style.WARNING(
                self.format_header(f"Issues with '{app_name}'")
            ))
            template_issues = summary[1].get('templates', [])
            if template_issues:
                self.stdout.write(self.style.MIGRATE_LABEL(
                    "Issues with templates:\n"
                ))
                self.show_app_issue_summary(app_name, template_issues, is_template=True)
            javascript_issues = summary[1].get('javascript', [])
            if javascript_issues:
                self.stdout.write(self.style.MIGRATE_LABEL(
                    "Issues with javascript:"
                ))
                self.show_app_issue_summary(app_name, javascript_issues, is_template=False)

    def show_app_issue_summary(self, app_name, issues, is_template):
        argument = "--template-name" if is_template else "--js-name"
        for issue in issues:
            path = issue[0]
            self.stdout.write(self.style.WARNING(
                path
            ))
            for line_number, flags in issue[1]:
                self.stdout.write(f"\nline {line_number}:")
                flag_list = "\t".join(flags)
                self.stdout.write(f"\t{flag_list}")
            self.stdout.write("\nto fix this, run:")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"./manage.py migrate_app_to_bootstrap5 {app_name} {argument} {path}\n"
            ))
            self.enter_to_continue()

    @staticmethod
    def format_header(header_text, break_length=80):
        break_line = get_break_line("*", break_length)
        return f'\n{break_line}\n\n{header_text}\n\n{break_line}\n\n'

    @staticmethod
    def enter_to_continue():
        input("\nENTER to continue...")
