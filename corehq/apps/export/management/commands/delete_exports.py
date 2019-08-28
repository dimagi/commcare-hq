
from six.moves import input

from django.core.management.base import BaseCommand

from corehq.apps.export.models import ExportInstance
from dimagi.utils.couch.database import iter_bulk_delete


class Command(BaseCommand):
    help = "Delete exports in a domain"

    def add_arguments(self, parser):

        parser.add_argument(
            'domain',
            help="The domain to delete exports in"
        )
        parser.add_argument(
            '--days_inactive',
            default=0,
            help="Only delete exports that have been inactive for this many days"
        )

    def handle(self, domain, **options):
        db = ExportInstance.get_db()
        exports = db.view(
            'export_instances_by_domain/view',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=False,
        ).all()
        if not exports:
            print("No exports to delete here, exiting.")
            return

        if options['days_inactive'] > 0:
            import datetime
            inactive_since = datetime.datetime.today() - datetime.timedelta(days=int(options['days_inactive']))
            inactive_exports = []
            for export in exports:
                e = ExportInstance.get(export['id'])
                if e.last_accessed and e.last_accessed <= inactive_since:
                    inactive_exports.append(export)
            if not inactive_exports:
                print("No exports have been inactive for more than {days_inactive} days, exiting.".format(
                    days_inactive=options['days_inactive'])
                )
                return
            confirm = input(
                "There are {total_exports} exports in {domain}. Are you sure you want to delete "
                "{total_inactive_exports} that are older than {days_inactive} days [y/N]?".format(
                    total_exports=len(exports),
                    total_inactive_exports=len(inactive_exports),
                    domain=domain,
                    days_inactive=int(options['days_inactive'])
                )
            )
            if confirm.lower() == 'y':
                exports = inactive_exports
            else:
                return

        filter_exports = lambda _type: [row for row in exports if _type in row['key']]
        form_exports = filter_exports('FormExportInstance')
        case_exports = filter_exports('CaseExportInstance')

        confirm = input(
            "There are {f_count} form exports, and {c_count} case exports. "
            "Are you sure you want to delete all these exports [y/N]?\n".format(
                f_count=len(form_exports),
                c_count=len(case_exports)
            )
        )
        to_delete = []
        if confirm.lower() == 'y':
            _type = input(
                "Enter 'case' to delete all case exports, "
                "'form to delete all form exports, "
                "'all' to delete both form and case exports. "
                "Enter anything else to exit.\n"
            )
            if _type == 'form':
                to_delete = form_exports
                print("Deleting form exports")
            elif _type == 'case':
                to_delete = case_exports
                print("Deleting case exports")
            elif _type == 'all':
                to_delete = form_exports + case_exports
                print("Deleting all exports")
            else:
                print("Not deleting anything, exiting!")
                return
            total_count = iter_bulk_delete(db, [doc['id'] for doc in to_delete])
            print("Deleted total of {} exports succesfully!".format(total_count))
