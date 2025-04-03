from django.core.management import BaseCommand

from corehq.apps.hqwebapp.utils.bootstrap.paths import get_bootstrap5_path
from corehq.apps.hqwebapp.utils.bootstrap.git import apply_commit, get_commit_string
from corehq.apps.hqwebapp.utils.bootstrap.reports.progress import (
    get_migrated_reports,
    get_migrated_filters,
    mark_filter_as_complete,
    mark_report_as_complete,
    get_migrated_filter_templates,
    mark_filter_template_as_complete,
)
from corehq.apps.hqwebapp.utils.bootstrap.reports.stats import (
    get_report_class,
    get_bootstrap5_reports,
)
from corehq.apps.hqwebapp.utils.management_commands import get_confirmation


class Command(BaseCommand):
    help = "This command helps mark reports and associated filters (and their templates) as migrated."

    def add_arguments(self, parser):
        parser.add_argument('report_class_name')

    def handle(self, report_class_name, **options):
        self.stdout.write("\n\n")
        report_class = get_report_class(report_class_name)
        if report_class is None:
            self.stdout.write(self.style.ERROR(
                f"Could not find report {report_class_name}. Are you sure it exists?"
            ))
            return

        migrated_reports = get_migrated_reports()
        if not self.is_safe_to_migrate_report(report_class_name, migrated_reports):
            self.stdout.write(self.style.ERROR(
                f"\nAborting migration of {report_class_name}...\n\n"
            ))
            return

        if report_class_name in migrated_reports:
            self.stdout.write(self.style.WARNING(
                f"The report {report_class_name} has already been marked as migrated."
            ))
            confirm = get_confirmation("Re-run report migration checks?", default='y')
        else:
            confirm = get_confirmation(f"Proceed with marking {report_class_name} as migrated?", default='y')

        if not confirm:
            return

        if report_class.debug_bootstrap5:
            self.stdout.write(self.style.ERROR(
                f"Could not complete migration of {report_class.__name__} because "
                f"`debug_bootstrap5` is still set to `True`.\n"
                f"Please remove this property to continue."
            ))
            return

        self.migrate_report_and_filters(report_class)
        self.stdout.write("\n\n")

    def is_safe_to_migrate_report(self, report_class_name, migrated_reports):
        """
        Sometimes a report will be migrated that's then inherited by downstream reports.
        This check ensures that this is not overlooked when marking a report as migrated,
        and it's why we keep the list of intentionally migrated reports separated from
        a dynamically generated one from `get_bootstrap5_reports()`.

        Either those reports must be migrated first OR they should have `use_bootstrap5 = False`,
        to override the setting of the inherited report.
        """
        bootstrap5_reports = set(get_bootstrap5_reports())
        intentionally_migrated_reports = set([report_class_name] + migrated_reports)
        overlooked_reports = bootstrap5_reports.difference(intentionally_migrated_reports)
        if not overlooked_reports:
            return True
        self.stdout.write(self.style.ERROR(
            f"It is not safe to migrate {report_class_name}!"
        ))
        self.stdout.write("There are other reports that inherit from this report.")
        self.stdout.write("You can either migrate these reports first OR "
                          "set use_bootstrap = False on them to continue migrating this report.\n\n")
        self.stdout.write("\t" + "\n\t".join(overlooked_reports))
        return False

    def migrate_report_and_filters(self, report_class):
        from corehq.apps.reports.generic import get_filter_class
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nMigrating {report_class.__name__}..."))
        migrated_filters = get_migrated_filters()
        migrated_filter_templates = get_migrated_filter_templates()
        for field in report_class.fields:
            if field not in migrated_filters:
                filter_class = get_filter_class(field)
                if not self.is_filter_migrated_prompts(field, filter_class, migrated_filter_templates):
                    return

        confirm_columns = get_confirmation(
            f"Did you pass the value for use_bootstrap5 from the {report_class.__name__} to all "
            f"`DataTablesColumn` instances related to that report?"
        )
        if not confirm_columns:
            self.stdout.write(self.style.ERROR(
                f"Cannot mark {report_class.__name__} as complete until `DataTablesColumn` "
                f"instances are updated."
            ))
            return

        confirm_sorting = get_confirmation(
            f"Did you check to see if {report_class.__name__} sorting works as expected?"
        )
        if not confirm_sorting:
            self.stdout.write(self.style.ERROR(
                f"Cannot mark {report_class.__name__} as complete until sorting is verified."
            ))
            return

        self.stdout.write(
            self.style.SUCCESS(f"All done! {report_class.__name__} has been migrated to Bootstrap5!")
        )
        mark_report_as_complete(report_class.__name__)
        self.suggest_commit_message(f"Completed report: {report_class.__name__}.")

    def is_filter_migrated_prompts(self, field, filter_class, migrated_filter_templates):
        if filter_class is None:
            self.stdout.write(self.style.ERROR(
                f"The filter {field} could not be found. Check report for errors.\n\n"
                f"Did this field not show up? Check feature flags for report.\n"
            ))
            return False
        self.stdout.write(self.style.MIGRATE_LABEL(f"\nChecking report filter: {filter_class.__name__}"))
        confirm = get_confirmation(
            "Did you test the filter to make sure it loads on the page without error and modifies "
            "the report as expected?", default='y'
        )
        if not confirm:
            self.stdout.write(self.style.ERROR(
                f"The filter {field} is not fully migrated yet."
            ))
            return False
        mark_filter_as_complete(field)

        template = get_bootstrap5_path(filter_class.template)
        if template not in migrated_filter_templates:
            confirm = get_confirmation(
                f"Did you migrate its template ({template})?", default='y'
            )
            if not confirm:
                self.stdout.write(self.style.ERROR(
                    f"The filter {field} template {template} is not fully migrated yet."
                ))
                return False
        migrated_filter_templates.append(template)
        mark_filter_template_as_complete(template)
        return True

    def suggest_commit_message(self, message, show_apply_commit=False):
        self.stdout.write("\nNow would be a good time to review changes with git and commit.")
        if show_apply_commit:
            confirm = get_confirmation("\nAutomatically commit these changes?", default='y')
            if confirm:
                apply_commit(message)
                return
        commit_string = get_commit_string(message)
        self.stdout.write("\n\nSuggested command:\n")
        self.stdout.write(self.style.MIGRATE_HEADING(commit_string))
        self.stdout.write("\n")
