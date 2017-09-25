from custom.enikshay.management.commands.utils import (
    BaseEnikshayCaseMigration,
    get_form_path,
    get_result_recorded_form,
    is_person_public,
)


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        'sputum_visual_appearance',
    ]
    datamigration_case_property = 'datamigration_sputum_visual_appearance'

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property('datamigration_sputum_visual_appearance') == 'yes'
            or test.get_case_property('migration_created_case') == 'true'
            or test.get_case_property('test_type_value') not in ['microscopy-zn', 'microscopy-fluorescent']
            or test.get_case_property('result_recorded') != 'yes'
            or test.get_case_property('sputum_visual_appearance')
            or not is_person_public(domain, test)
        ):
            return {}
        else:
            form_data = get_result_recorded_form(test)
            if form_data is None:
                return {}
            sputum_visual_appearance = get_form_path(
                ['update_test_result', 'microscopy', 'ql_result', 'sample_a_visual_appearance'],
                form_data
            ) or get_form_path(
                ['update_test_result', 'microscopy', 'ql_result', 'sample_b_visual_appearance'],
                form_data
            ) or get_form_path(
                ['microscopy', 'ql_result', 'sample_a_visual_appearance'],
                form_data
            ) or get_form_path(
                ['microscopy', 'ql_result', 'sample_b_visual_appearance'],
                form_data
            )
            if sputum_visual_appearance:
                return {
                    'sputum_visual_appearance': sputum_visual_appearance,
                }
            else:
                return {}
