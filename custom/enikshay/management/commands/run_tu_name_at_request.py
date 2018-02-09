from __future__ import absolute_import
from custom.enikshay.management.commands.utils import (
    BaseEnikshayCaseMigration,
    get_form_path,
    get_test_created_form,
)


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        'tu_name_at_request',
    ]
    datamigration_case_property = 'datamigration_tu_name_at_request'
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property('datamigration_tu_name_at_request') == 'yes'
            or test.get_case_property('migration_created_case') == 'true'
            or test.get_case_property('tu_name_at_request')
        ):
            return {}
        else:
            form_data = get_test_created_form(test)
            tu_name_at_request = get_form_path(
                ['person', 'tu_name'], form_data
            )
            if tu_name_at_request:
                return {
                    'tu_name_at_request': tu_name_at_request,
                }
            else:
                return {}
