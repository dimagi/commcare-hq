import csv
from casexml.apps.case.xform import get_case_updates
from datetime import datetime
from django.core.management.base import BaseCommand

from corehq.apps.es import FormES
from corehq.form_processor.models.cases import CommCareCase, XFormInstance
from corehq.util.argparse_types import date_type
from dimagi.utils.chunked import chunked


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--domains', nargs="*"
        )
        parser.add_argument('--start', type=date_type, help='Start date (inclusive)')
        parser.add_argument('--end', type=date_type, help='End date (inclusive)')

    def handle(self, **options):
        filename = "deleted_cases_pull_{}.csv".format(datetime.utcnow().strftime("%Y-%m-%d_%H.%M.%S"))
        domains = options['domains']

        print(f"Outputting to: {filename}...")
        with open(filename, 'w', encoding='utf-8') as csv_file:
            field_names = ['domain', 'case_id', 'case_type', 'date_of_deletion', 'deletion_type']
            csv_writer = csv.DictWriter(csv_file, field_names)
            csv_writer.writeheader()
            for domain in domains:
                deleted_case_ids = CommCareCase.objects.get_deleted_case_ids_in_domain(domain)
                for ids_chunk in chunked(deleted_case_ids, 500):
                    for case in CommCareCase.objects.get_cases(list(ids_chunk)):
                        # Should be true if a case was deleted because an associated mobile worker was removed.
                        if case.deleted_on:
                            row = {
                                'domain': domain,
                                'case_id': case.case_id,
                                'case_type': case.type,
                                'date_of_deletion': case.server_modified_on,
                                'deletion_type': 'Mobile worker deleted'
                            }
                        # Otherwise, case was deleted due to form achival, and we can get the case type through a
                        # more lengthy process.
                        else:
                            # Getting the form that created the case via ES fails sometimes.
                            case_type = _find_case_type_using_ES(domain, case.case_id)
                            if not case_type:
                                # If it does, try to get the case type via case transactions.
                                case_type = _find_case_type_from_transactions(case)
                            if not case_type:
                                print(f"Could not find case type for case {case.case_id}")
                                case_type = None
                            row = {
                                'domain': domain,
                                'case_id': case.case_id,
                                'case_type': case_type,
                                'date_of_deletion': case.modified_on,
                                'deletion_type': 'Forms archived' if case_type else 'Unknown'
                            }
                        csv_writer.writerow(row)
            print(f"Result saved to {filename}")


def _get_case_type_if_form_creates_case(form, case_id):
    updates = get_case_updates(form)
    for update in updates:
        if update.creates_case() and update.id == case_id:
            return update.get_create_action().type


def _find_case_type_using_ES(domain, case_id):
    forms_that_touched_case = (
        FormES()
        .domain(domain)
        .updating_cases([case_id])
        .sort('received_on', desc=False)
        .run()
        .raw['hits']['hits']
    )
    for form in forms_that_touched_case:
        case_type = _get_case_type_if_form_creates_case(form, case_id)
        if case_type:
            return case_type


def _find_case_type_from_transactions(case):
    for transaction in case.transactions:
        if transaction.details.get('archived', False):
            form = XFormInstance.get_obj_by_id(transaction.details['form_id'])
            case_type = _get_case_type_if_form_creates_case(form, case.case_id)
            if case_type:
                return case_type
