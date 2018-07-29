from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

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
                "Entery anything else to exit.\n"
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
