from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.private_sector_datamigration.factory import PERSON_CASE_TYPE
from custom.enikshay.private_sector_datamigration.models import Beneficiary


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        self.domain = domain
        case_accessor = CaseAccessors(domain)
        for person_case_id in case_accessor.get_case_ids_in_domain(type=PERSON_CASE_TYPE):
            person_case = case_accessor.get_case(person_case_id)
            case_properties = person_case.dynamic_case_properties()
            if self.should_add_state_and_district(case_properties):
                beneficiary = Beneficiary.objects.get(caseId=case_properties['migration_created_from_record'])
                self.add_state_and_district(person_case, beneficiary, case_properties)

    @staticmethod
    def should_add_state_and_district(case_properties):
        return (
            case_properties.get('enrolled_in_private') == 'true' and
            case_properties.get('migration_created_case') == 'true' and
            case_properties.get('migration_comment') in [
                'july_7',
                'july_7_unassigned',
                'july_7-unassigned',
                'incr_bene_jul19',
            ]
        )

    def add_state_and_district(self, person_case, beneficiary, case_properties):
        update = {}
        if not case_properties.get('current_address_state_choice'):
            update['current_address_state_choice'] = STATE_ID_TO_LOCATION[beneficiary.stateId]
        if not case_properties.get('current_address_district_choice'):
            update['current_address_district_choice'] = DISTRICT_ID_TO_LOCATION[beneficiary.districtId]

        if update:
            CaseFactory(self.domain).update_case(
                person_case.case_id,
                update=update,
            )

STATE_ID_TO_LOCATION = {
    '136': 'fa7472fe0c9751e5d14595c1a08698e2',
    '154': 'fa7472fe0c9751e5d14595c1a091f17d',
    '155': 'fa7472fe0c9751e5d14595c1a08c12b5',
    '2283': 'fa7472fe0c9751e5d14595c1a07b44b0',
    '2284': 'fa7472fe0c9751e5d14595c1a0858ee2',
    '2285': 'fa7472fe0c9751e5d14595c1a0749123', # typo?
    '2286': 'fa7472fe0c9751e5d14595c1a0833621',
    '2287': 'fa7472fe0c9751e5d14595c1a0844aab',
    '2288': 'fa7472fe0c9751e5d14595c1a07a5f13',
    '2289': 'fa7472fe0c9751e5d14595c1a0772ff2',
    '2294': 'fa7472fe0c9751e5d14595c1a07d7e61',
    '2298': 'fa7472fe0c9751e5d14595c1a0878be3',
    '2299': 'fa7472fe0c9751e5d14595c1a074036c',
    '2300': 'fa7472fe0c9751e5d14595c1a0818d00',
    '2301': 'fa7472fe0c9751e5d14595c1a07c6cd7',
    '2302': 'fa7472fe0c9751e5d14595c1a0856b69',
    '2303': 'fa7472fe0c9751e5d14595c1a07efcca',
    '2305': 'fa7472fe0c9751e5d14595c1a0846c7b',
    '2308': 'fa7472fe0c9751e5d14595c1a088b490',
    '2309': 'fa7472fe0c9751e5d14595c1a080b2ee',
    '2310': 'fa7472fe0c9751e5d14595c1a083567c',
    '2313': 'fa7472fe0c9751e5d14595c1a0793593',
}

DISTRICT_ID_TO_LOCATION = {
    '157': 'Mahesana',
    '189': 'fa7472fe0c9751e5d14595c1a09001de',
    '625': 'Nagpur',
    '626': 'Nagpur MC',
    '647': 'Thane',
    '1001': '',
    '1002': '',
    '1003': '',
    '1004': '',
    '1005': '',
    '1006': '',
    '1007': '',
    '1008': '',
    '1009': '',
    '1010': '',
    '1011': '',
    '1012': '',
    '1013': '',
    '1014': '',
    '1015': '',
    '1016': '',
    '1017': '',
    '1018': '',
    '1019': '',
    '1020': '',
    '1021': '',
    '1022': '',
    '1023': '',
    '1024': '',
    '1025': '',
    '1026': 'Patna',
    '1027': '',
    '1028': '',
    '1029': '',
    '1030': '',
    '1031': '',
    '1032': '',
    '1033': '',
    '1034': '',
    '1035': '',
    '1036': '',
    '1037': '',
    '1038': '',
    '1193': '',
    '1194': '',
}
