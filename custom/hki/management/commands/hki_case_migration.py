from django.core.management import BaseCommand

from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.locations.models import SQLLocation
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.models import CommCareCaseSQL
from corehq.util.log import with_progress_bar

from dimagi.utils.chunked import chunked


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'log_file',
            help="File path for log file",
        )

    def handle(self, log_file, **options):
        self.domain = 'hki-nepal-suaahara-2'
        loc_mapping = {}
        locs = SQLLocation.objects.filter(domain=self.domain, level=4)
        for loc in locs:
            loc_mapping[loc.site_code] = loc.location_id

        failed_updates = []
        household_cases = CaseES().domain(self.domain).case_type('household').count()
        member_cases = CaseES().domain(self.domain).case_type('household_member').count()
        total_cases = household_cases + member_cases
        with open(log_file, "w", encoding='utf-8') as fh:
            fh.write('--------Successful Form Ids----------')
            for cases in chunked(with_progress_bar(self._get_cases_to_process(), total_cases), 100):
                cases_to_update = self._process_cases(cases, failed_updates, loc_mapping)
                try:
                    xform, cases = bulk_update_cases(
                        self.domain, cases_to_update, self.__module__)
                    fh.write(xform.form_id)
                except LocalSubmissionError as e:
                    print(str(e))
                    failed_updates.extend(case[0] for case in cases_to_update)
            fh.write('--------Failed Cases--------------')
            for case_id in failed_updates:
                fh.write(case_id)

    def _get_cases_to_process(self):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            for case_type in ('household', 'household_member'):
                cases = CommCareCaseSQL.objects.using(db).filter(domain=self.domain, type=case_type)
                for case in cases:
                    yield case

    def _process_cases(self, cases, failed_updates, loc_mapping):
        cases_to_update = []
        for case in cases:
            try:
                if not case.get_case_property('location_migration_complete') is None:
                    level2_code = case.get_case_property('household_level2_code', '')
                    ward_number = case.get_case_property('household_ward_number', '')
                    new_site_code = '{}{}'.format(level2_code, ward_number.zfill(2))
                    new_owner_id = loc_mapping.get(new_site_code, 'c9c86e46f57b4d2f81045e5250e03889')
                    case_properties = {
                        'owner_id': new_owner_id,
                        'location_migration_complete': 'no' if 'c9c86e46f57b4d2f81045e5250e03889' else 'yes'
                    }
                    cases_to_update.append((case.case_id, case_properties, False))
            except:
                failed_updates.append(case.case_id)
