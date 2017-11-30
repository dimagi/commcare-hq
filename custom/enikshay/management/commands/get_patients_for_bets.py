from __future__ import absolute_import
from __future__ import print_function
import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation
from corehq.util.log import with_progress_bar
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.integrations.bets.repeater_generators import BETSBeneficiaryPayloadGenerator
from custom.enikshay.case_utils import CASE_TYPE_PERSON
from six.moves import map


class Command(BaseCommand):
    field_names = [
        'case_id',
        'closed',
        'date_closed',
        'date_modified',
        'domain',
        'id',
        'indices',
        'properties.age',
        'properties.age_entered',
        'properties.case_name',
        'properties.case_type',
        'properties.current_address',
        'properties.current_address_block_taluka_mandal',
        'properties.current_address_district_choice',
        'properties.current_address_first_line',
        'properties.current_address_postal_code',
        'properties.current_address_state_choice',
        'properties.current_address_village_town_city',
        'properties.current_address_ward',
        'properties.current_episode_type',
        'properties.dataset',
        'properties.date_opened',
        'properties.dob',
        'properties.dob_known',
        'properties.enrolled_in_private',
        'properties.external_id',
        'properties.facility_assigned_to',
        'properties.first_name',
        'properties.husband_father_name',
        'properties.id_original_beneficiary_count',
        'properties.id_original_device_number',
        'properties.id_original_issuer_number',
        'properties.language_preference',
        'properties.last_name',
        'properties.other_id_type',
        'properties.owner_id',
        'properties.person_id',
        'properties.phi',
        'properties.phone_number',
        'properties.send_alerts',
        'properties.sex',
        'properties.tu_choice',
        'resource_uri',
        'server_date_modified',
        'server_date_opened',
        'user_id',
        'xform_ids',
        'uatbc_id',
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('parent_location_id')

    def handle(self, domain, parent_location_id, **options):
        self.domain = domain
        self.accessor = CaseAccessors(domain)
        self.location = SQLLocation.objects.get(domain=domain, location_id=parent_location_id)
        owner_ids = self.location.get_descendants(include_self=True).location_ids()

        filename = 'patients.csv'
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(self.field_names)

            person_ids = self.accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_PERSON, owner_ids)
            for person in with_progress_bar(self.accessor.iter_cases(person_ids), len(person_ids)):
                if person.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
                    self.add_person(person, writer)
        print("Wrote to {}".format(filename))

    def add_person(self, person, writer):
        person_data = BETSBeneficiaryPayloadGenerator.serialize(person)
        person_data['uatbc_id'] = person.get_case_property('migration_created_from_record')

        def get_field(field):
            if field in ('xform_ids', 'indices',):
                return ''
            elif '.' in field:
                obj, key = field.split('.')
                return person_data[obj].get(key, '')
            return person_data[field]

        writer.writerow(list(map(get_field, self.field_names)))
