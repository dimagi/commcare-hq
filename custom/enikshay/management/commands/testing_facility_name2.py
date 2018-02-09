from __future__ import print_function

from __future__ import absolute_import
from corehq.apps.users.models import CommCareUser
from custom.enikshay.management.commands.utils import (
    BaseEnikshayCaseMigration,
    get_result_recorded_form,
)


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        'testing_facility_id',
        'testing_facility_name',
    ]
    datamigration_case_property = 'datamigration_testing_facility_name2'
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property('datamigration_testing_facility_name2') == 'yes'
            or test.get_case_property('migration_created_case') == 'true'
            or test.get_case_property('result_recorded') != 'yes'
            or test.get_case_property('testing_facility_id')
        ):
            return {}

        form_data = get_result_recorded_form(test)
        if form_data is None:
            return {}

        user_id = form_data['meta']['userID']
        user = CommCareUser.get_by_user_id(user_id)
        user_location = user.get_sql_location('enikshay')
        if user_location is not None:
            user_location_id = user_location.location_id
            user_location_type = user_location.location_type.code
        else:
            if 'user_location_id' in form_data:
                user_location_id = form_data['user_location_id']
            elif 'user' in form_data:
                user_location_id = form_data['user']['user_location_id']
            else:
                print('user %s doesnt have user_location_id: form %s' % (user_id, form_data['meta']['instanceID']))
                return {}

            if 'user_location_type' in form_data:
                user_location_type = form_data['user_location_type']
            elif 'user' in form_data:
                user_location_type = form_data['user']['user_location_type']
            else:
                print(
                    'user %s doesnt have user_location_type: form %s'
                    % (user_id, form_data['meta']['instanceID'])
                )
                return {}

        if user_location_type in ['cdst', 'dmc']:
            return {
                'testing_facility_id': user_location_id,
                'testing_facility_name': user_location.name,
            }
        else:
            return {}
