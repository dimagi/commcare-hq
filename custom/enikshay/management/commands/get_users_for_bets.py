from __future__ import absolute_import
from __future__ import print_function
import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.util.log import with_progress_bar
from custom.enikshay.integrations.bets.repeater_generators import BETSUserPayloadGenerator
from custom.enikshay.integrations.bets.repeaters import BETSUserRepeater
from six.moves import map


class Command(BaseCommand):
    field_names = [
        'username',
        'first_name',
        'last_name',
        'default_phone_number',
        'user_data.secondary_pincode',
        'user_data.address_line_1',
        'user_data.use_new_ids',
        'user_data.pcc_pharmacy_affiliation',
        'user_data.plc_lab_collection_center_name',
        'user_data.commcare_project',
        'user_data.pcp_professional_org_membership',
        'user_data.pincode',
        'user_data.id_issuer_body',
        'user_data.agency_status',
        'user_data.secondary_date_of_birth',
        'user_data.tb_corner',
        'user_data.pcc_pharmacy_name',
        'user_data.id_device_number',
        'user_data.secondary_gender',
        'user_data.plc_tb_tests',
        'user_data.landline_no',
        'user_data.id_issuer_number',
        'user_data.secondary_landline_no',
        'user_data.plc_lab_or_collection_center',
        'user_data.secondary_first_name',
        'user_data.commcare_primary_case_sharing_id',
        'user_data.pcp_qualification',
        'user_data.pac_qualification',
        'user_data.secondary_unique_id_type',
        'user_data.email',
        'user_data.commcare_location_id',
        'user_data.issuing_authority',
        'user_data.pcc_tb_drugs_in_stock',
        'user_data.secondary_mobile_no_2',
        'user_data.secondary_mobile_no_1',
        'user_data.secondary_middle_name',
        'user_data.plc_accredidation',
        'user_data.mobile_no_2',
        'user_data.commcare_location_ids',
        'user_data.mobile_no_1',
        'user_data.is_test',
        'user_data.secondary_email',
        'user_data.id_device_body',
        'user_data.secondary_unique_id_Number',
        'user_data.plc_hf_if_nikshay',
        'user_data.usertype',
        'user_data.user_level',
        'user_data.gender',
        'user_data.secondary_address_line_1',
        'user_data.secondary_last_name',
        'user_data.secondary_address_line_2',
        'user_data.address_line_2',
        'user_data.registration_number',
        'user_data.nikshay_id',
        'id',
        'groups',
        'phone_numbers',
        'user_data.email',
        'dtoLocation',
        'privateSectorOrgId',
        'resource_uri',
        'migrationCrtdRecordId',
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def get_data_fields(self):
        data_model = CustomDataFieldsDefinition.get_or_create(
            self.domain,
            UserFieldsView.field_type,
        )
        return sorted(data_model.fields)

    def handle(self, domain, **options):
        self.domain = domain
        self.locationless_users = []
        self.locations_by_id = {
            loc.location_id: loc for loc in SQLLocation.objects.filter(domain=domain)
        }
        filename = 'agency_users.csv'
        self.data_fields = self.get_data_fields()
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(self.field_names)
            for user in with_progress_bar(CommCareUser.by_domain(domain)):
                self.add_user(user, writer)
        print("Wrote to {}".format(filename))

        if self.locationless_users:
            with open('locationless_' + filename, 'w') as f:
                writer = csv.writer(f)
                for username, user_id in self.locationless_users:
                    writer.writerow([username, user_id])

    def add_user(self, user, writer):

        def _is_relevant_location(location):
            return (location.metadata.get('is_test') != "yes"
                    and location.location_type.code in BETSUserRepeater.location_types_to_forward)

        user_locations = [self.locations_by_id.get(loc_id) for loc_id in user.get_location_ids(self.domain)]
        if not (user.user_data.get('user_level', None) == 'real'
                and any(_is_relevant_location(loc) for loc in user_locations)):
            return

        user_data = BETSUserPayloadGenerator.serialize(self.domain, user)
        user_data['migrationCrtdRecordId'] = user.user_data.get('agency_id_legacy', '')

        def get_field(field):
            if field == 'phone_numbers':
                return ''
            elif '.' in field:
                obj, key = field.split('.')
                return user_data[obj].get(key, '')
            return user_data.get(field, '')

        writer.writerow(list(map(get_field, self.field_names)))
