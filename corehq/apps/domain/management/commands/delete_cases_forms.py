import csv
import uuid

from collections import defaultdict
from datetime import datetime
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from casexml.apps.case.xform import get_case_ids_from_form
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.apps.users.tasks import _remove_indices_from_deleted_cases_task


class Command(BaseCommand):
    help = "Soft delete cases and the forms that touch only those cases"

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_filepath',
            help='CSV containing list of (case_id, domain) rows'
        )
        parser.add_argument(
            'csv_output_file',
            help='The results will be written to this file, dry run or not.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Dry Run but dont actually delete',
        )

    def handle(self, csv_filepath, csv_output_file, **options):
        self.dry_run = options.get('dry_run')
        self.csv_output_file = csv_output_file

        case_ids_by_domain = defaultdict(list)
        with open(csv_filepath) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',', skipinitialspace=True)
            for row in csv_reader:
                if row == ['case_id', 'domain']:
                    continue
                case_ids_by_domain[row[1]].append(row[0])
        for domain, case_ids in case_ids_by_domain.items():
            print("Processing for domain. Case ID count", len(case_ids))
            self.delete(domain, case_ids)

    def delete(self, domain, case_ids):
        deletion_id = uuid.uuid4().hex
        deletion_date = datetime.utcnow()

        form_ids = set()
        for case_id in case_ids:
            form_ids.update(CaseAccessors(domain).get_case_xform_ids(case_id))

        i = 0
        for case_id_list in chunked(case_ids, 50):
            self.soft_delete_cases(domain, case_id_list, deletion_id, deletion_date)
            if not self.dry_run:
                i = i + len(case_id_list)
                print("Deleted", i, "cases out of", len(case_ids))

        self.field_names = ['domain', 'case_id', 'form_id_deleted',
            'form_id_skipped', 'other_cases_affected_by_form']
        with open(self.csv_output_file, 'a', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file, self.field_names)
            csv_writer.writerow(self.field_names)

        i = 0
        for form_id_list in chunked(form_ids, 50):
            self.soft_delete_forms(
                domain, form_id_list, deletion_id, deletion_date, set(case_ids)
            )
            if not self.dry_run:
                i = i + len(case_id_list)
                print("Processing", i, "forms out of", len(case_ids))
        print("Finished Processing, you can check the results in the output file.")

    def soft_delete_cases(self, domain, case_ids, deletion_id, deletion_date):
        if self.dry_run:
            return
        from corehq.apps.sms.tasks import delete_phone_numbers_for_owners
        from corehq.messaging.scheduling.tasks import delete_schedule_instances_for_cases
        CaseAccessors(domain).soft_delete_cases(list(case_ids), deletion_date, deletion_id)
        _remove_indices_from_deleted_cases_task(domain, case_ids)
        delete_phone_numbers_for_owners(case_ids)
        delete_schedule_instances_for_cases(domain, case_ids)

    def soft_delete_forms(self, domain, form_id_list, deletion_id, deletion_date, deleted_cases):
        deleted_cases = deleted_cases or set()

        skipped_forms = []
        to_delete = []
        for form in FormAccessors(domain).iter_forms(form_id_list):
            if form.domain != domain:
                continue
            form_case_ids = set(get_case_ids_from_form(form))
            if form_case_ids.issubset(set(deleted_cases)):
                # if the form touches only the deleted cases, then delete them
                already_deleted = form_case_ids & set(deleted_cases)
                to_delete.append((form.form_id, already_deleted))
            else:
                already_deleted = form_case_ids & set(deleted_cases)
                other_cases_ids = form_case_ids - set(deleted_cases)
                skipped_forms.append((form.form_id, already_deleted, other_cases_ids))

        with open(self.csv_output_file, 'a', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file, self.field_names)
            for (form_id, deleted_case_ids, other_cases_ids) in skipped_forms:
                for case_id in deleted_case_ids:
                    csv_writer.writerow([domain, case_id, None, form_id, other_cases_ids])
            for (form_id, deleted_case_ids) in to_delete:
                for case_id in deleted_case_ids:
                    csv_writer.writerow([domain, case_id, form_id, None, None])

        if self.dry_run:
            return
        else:
            form_ids = set([x[0] for x in to_delete])
            print("Deleting", len(form_ids), "forms")
            FormAccessors(domain).soft_delete_forms(list(form_ids), deletion_date, deletion_id)
