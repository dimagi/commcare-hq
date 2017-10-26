from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration

TEST_TYPE_VALUE = 'test_type_value'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_pmdt_test_type_value'


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        TEST_TYPE_VALUE,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(episode, domain):
        if (
            episode.get_case_property(DATAMIGRATION_CASE_PROPERTY) != 'yes'
            and episode.get_case_property('migration_type') == 'pmdt_excel'
            and episode.get_case_property('test_type')
        ):
            return {
                TEST_TYPE_VALUE: episode.get_case_property('test_type')
            }
        else:
            return {}