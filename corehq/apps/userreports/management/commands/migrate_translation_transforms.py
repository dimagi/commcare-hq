from __future__ import print_function

from django.core.management.base import BaseCommand
from corehq.apps.userreports.models import ReportConfiguration
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar


def reformat_translations(old_translations):
    if not isinstance(old_translations, dict):
        return old_translations
    new_translations = {}
    for k, translations in old_translations.items():
        if isinstance(translations, basestring):
            new_translations[k] = translations
        else:
            new_translations[k] = dict(translations)
    return new_translations


class Command(BaseCommand):
    help = ("Migrate existing translation transforms to flag as mobile-only "
            "and update mapping format")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help=("Don't actually perform the update, just list the reports "
                  "that would be affected"),
        )

    def handle(self, dry_run=False, **options):
        self.dry_run = dry_run
        self.reports_using_transform = set()
        report_ids = get_doc_ids_by_class(ReportConfiguration)
        res = iter_update(
            db=ReportConfiguration.get_db(),
            fn=self.migrate_report,
            ids=with_progress_bar(report_ids),
            verbose=True,
        )
        print("Found {} reports using the transform:".format(len(self.reports_using_transform)))
        print("\n".join(self.reports_using_transform))
        print("Updated the following reports:")
        print("\n".join(res.updated_ids))

    def migrate_report(self, report_config):
        rc = ReportConfiguration.wrap(report_config)
        for column in rc.report_columns:
            if column.transform and column.transform['type'] == 'translation':
                column.transform['mobile_or_web'] = 'mobile'
                column.transform['translations'] = reformat_translations(column.transform['translations'])
                self.reports_using_transform.add(rc._id)
        if not self.dry_run:
            return DocUpdate(rc.to_json())
