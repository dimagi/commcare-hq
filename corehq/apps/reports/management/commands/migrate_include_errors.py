from optparse import make_option
from django.core.management import BaseCommand
from dimagi.utils.couch.database import iter_docs
from corehq.apps.reports.models import FormExportSchema


class Command(BaseCommand):
    help = "Set all custom exports' include_errors to False to prepare for fix"
    args = ""
    label = ""

    option_list = BaseCommand.option_list + (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Run without saving any documents',
        ),
    )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        db = FormExportSchema.get_db()
        custom_export_ids = db.view(
            'couchexport/saved_export_schemas',
            reduce=False,
            wrapper=lambda x: x['id'],
        )
        for custom_export_doc in iter_docs(db, custom_export_ids, 100):
            if custom_export_doc.get('include_errors', False):
                self.stderr.write('Migrating {0}'.format(custom_export_doc['_id']))
                if not dry_run:
                    custom_export_doc['include_errors'] = False
                    db.save_doc(custom_export_doc)
                    self.stderr.write(' ...done\n')
                else:
                    self.stderr.write('\n')