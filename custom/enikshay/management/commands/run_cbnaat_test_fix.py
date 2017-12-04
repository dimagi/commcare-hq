from __future__ import print_function
from __future__ import absolute_import
from custom.enikshay.management.commands.utils import (
    BaseEnikshayCaseMigration,
    get_result_recorded_form,
    get_form_path
)


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        'result_summary_display',
        'drug_resistance_list',
        'drug_sensitive_list'
    ]
    datamigration_case_property = 'datamigration_cbnaat_test_fix'
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property('datamigration_cbnaat_test_fix') != 'yes'
            and test.get_case_property('updated_by_migration') == 'enikshay_2b_cbnaat_fix'
        ):
            form_data = get_result_recorded_form(test)
            if form_data:
                test_success = get_form_path(
                    ['update_test_result', 'cbnaat', 'ql_cbnaat', 'test_success'],
                    form_data)
                if test_success == 'success':
                    tb_detected_a = get_form_path(
                        ['update_test_result', 'cbnaat', 'ql_sample_a', 'sample_a_mtb_result'],
                        form_data)
                    tb_detected_b = get_form_path(
                        ['update_test_result', 'cbnaat', 'ql_sample_b', 'sample_b_mtb_result'],
                        form_data)
                    rif_a = get_form_path(
                        ['update_test_result', 'cbnaat', 'ql_sample_a', 'sample_a_rif_resistance_result'],
                        form_data,
                    )
                    rif_b = get_form_path(
                        ['update_test_result', 'cbnaat', 'ql_sample_b', 'sample_b_rif_resistance_result'],
                        form_data,
                    )

                    if tb_detected_a == 'detected' or tb_detected_b == 'detected':
                        detected = 'TB Detected'
                    else:
                        detected = 'TB Not Detected'

                    if rif_a == 'detected' or rif_b == 'detected':
                        drug_resistance_list = 'r'
                        drug_sensitive_list = ''
                        resistance_display = 'R: Res'
                    elif rif_a == 'not_detected' or rif_b == 'not_detected':
                        drug_resistance_list = ''
                        drug_sensitive_list = 'r'
                        resistance_display = 'R: Sens'
                    else:
                        drug_resistance_list = ''
                        drug_sensitive_list = ''
                        resistance_display = ''

                    result_summary_display = '\n'.join([_f for _f in [
                        detected,
                        resistance_display,
                    ] if _f])
                elif test_success == 'error':
                    error_code = get_form_path(
                        ['update_test_result', 'cbnaat', 'error_code'],
                        form_data)
                    result_summary_display = 'Test Error (' + error_code + ')'
                    drug_resistance_list = ''
                    drug_sensitive_list = ''
                elif test_success == 'invalid_result':
                    result_summary_display = 'Invalid Test Result'
                    drug_resistance_list = ''
                    drug_sensitive_list = ''
                else:
                    result_summary_display = 'Unknown Result'
                    drug_resistance_list = ''
                    drug_sensitive_list = ''

                return {
                    'result_summary_display': result_summary_display,
                    'drug_resistance_list': drug_resistance_list,
                    'drug_sensitive_list': drug_sensitive_list
                }
        return {}
