from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration

DATAMIGRATION_CASE_PROPERTY = 'datamigation_result_summary_display'
RESULT_SUMMARY_DISPLAY = 'result_summary_display'


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        RESULT_SUMMARY_DISPLAY,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property(DATAMIGRATION_CASE_PROPERTY) == 'yes'
            or not (
                test.get_case_property('result_recorded') == 'yes'
                and not test.get_case_property('test_type_value')
            )
        ):
            return {}

        new_result_display_summary = '\n'.join(filter(None, [
            {
                'tb_detected': 'TB Detected',
                'tb_not_detected': 'TB Not Detected',
            }.get(test.get_case_property('result')),
            {
                'negative_not_seen': None,
                '1plus': 'Result Grade 1+',
                '2plus': 'Result Grade 2+',
                '3plus': 'Result Grade 3+',
                'error_invalid_result': 'Result Grade: Error Invalid Result',
                '0': None,
                'n/a': None,
                '1+': 'Result Grade 1+',
                '2+': 'Result Grade 2+',
                '3+': 'Result Grade 3+',
                'scanty': 'Result Grade: scanty',
                None: None,
                '': None,
            }.get(test.get_case_property('result_grade'), 'Result Grade: %s' % test.get_case_property('result_grade')),
            'R:Res' if test.get_case_property('drug_resistance_list') == 'r' else None,
            'R:Sens' if test.get_case_property('drug_sensitive_list') == 'r' else None,
            'Count of bacilli: %s' % test.get_case_property('max_bacilli_count')
            if test.get_case_property('max_bacilli_count') else None,
            test.get_case_property('clinical_remarks'),
        ]))
        if new_result_display_summary != test.get_case_property(RESULT_SUMMARY_DISPLAY):
            return {
                RESULT_SUMMARY_DISPLAY: new_result_display_summary,
            }
        else:
            return {}
