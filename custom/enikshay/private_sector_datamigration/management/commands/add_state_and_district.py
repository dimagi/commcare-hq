from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.private_sector_datamigration.factory import PERSON_CASE_TYPE
from custom.enikshay.private_sector_datamigration.models import Beneficiary


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_ids', nargs='*')

    def handle(self, domain, case_ids, **options):
        self.domain = domain
        case_accessor = CaseAccessors(domain)
        if not case_ids:
            case_ids = case_accessor.get_case_ids_in_domain(type=PERSON_CASE_TYPE)
        for person_case_id in case_ids:
            print person_case_id
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
            ] and
            case_properties.get('legacy_districtId')
        )

    def add_state_and_district(self, person_case, beneficiary, case_properties):
        update = {}
        # if not case_properties.get('current_address_state_choice'):
        #     update['current_address_state_choice'] = STATE_ID_TO_LOCATION[beneficiary.stateId]
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
    '1001': 'Araria',
    '1002': 'Arwal',
    '1003': 'Aurangabad-BI',
    '1004': 'Banka',
    '1005': 'Begusarai',
    '1006': 'Bhagalpur',
    '1007': 'Bhojpur',
    '1008': 'Buxar',
    '1009': 'Darbhanga',
    '1010': 'Gaya',
    '1011': 'Gopalganj',
    '1012': 'Jamui',
    '1013': 'Jehanabad',
    '1014': 'Kaimur',
    '1015': 'Katihar',
    '1016': 'Khagaria',
    '1017': 'Kishanganj',
    '1018': 'Lakhisarai',
    '1019': 'Madhepura',
    '1020': 'Madhubani',
    '1021': 'Munger',
    '1022': 'Muzaffarpur',
    '1023': 'Nalanda',
    '1024': 'Nawada',
    '1025': 'Pashchim Champaran',
    '1026': 'Patna',
    '1027': 'Purba Champaran',
    '1028': 'Purnia',
    '1029': 'Rohtas',
    '1030': 'Saharsa',
    '1031': 'Samastipur',
    '1032': 'Saran',
    '1033': 'Sheikhpura',
    '1034': 'Sheohar',
    '1035': 'Sitamarhi',
    '1036': 'Siwan',
    '1037': 'Supaul',
    '1038': 'Vaishali',
    '1193': '',
    '1194': '',
}
