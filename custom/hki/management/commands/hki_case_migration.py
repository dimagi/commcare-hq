from django.core.management import BaseCommand

from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import update_case
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.models import CommCareCaseSQL
from corehq.util.log import with_progress_bar


class Command(BaseCommand):

    def handle(self, **options):
        domain = 'hki-nepal-suaahara-2'
        loc_mapping = {}
        locs = SQLLocation.objects.filter(domain=domain, level=4)
        for loc in locs:
            loc_mapping[loc.site_code] = loc.location_id

        failed_updates = []
        total_cases = CaseES().domain(domain).case_type('household').count()
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            for case_type in ('household', 'household_member'):
                cases = CommCareCaseSQL.objects.using(db).filter(domain=domain, type=case_type)
                for case in with_progress_bar(cases, total_cases/10/2):
                    try:
                        if not case.get_case_property('location_migration_complete') is None:
                            level2_code = case.get_case_property('household_level2_code')
                            ward_number = case.get_case_property('household_ward_number')
                            new_site_code = '{}{}'.format(level2_code, ward_number.zfill(2))
                            new_owner_id = loc_mapping.get(new_site_code, 'c9c86e46f57b4d2f81045e5250e03889')
                            case_properties = {
                                'owner_id': new_owner_id,
                                'location_migration_complete': 'no' if 'c9c86e46f57b4d2f81045e5250e03889' else 'yes'
                            }
                            update_case(domain, case.case_id, case_properties)
                    except:
                        failed_updates.append(case.case_id)
        for case in failed_updates:
            print case
