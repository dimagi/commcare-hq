from celery.schedules import crontab
from corehq.apps.celery import task

from corehq.apps.hqadmin.tasks import (
    AbnormalUsageAlert,
    send_abnormal_usage_alert,
)
from corehq.util.metrics import metrics_gauge_task
from corehq.util.metrics.const import MPM_MAX
from corehq.apps.data_dictionary.util import get_data_dict_deprecated_case_types

from .do_import import do_import
from .exceptions import ImporterError
from .tracking.analytics import get_case_upload_files_total_bytes
from .tracking.case_upload_tracker import CaseUpload
from .tracking.task_status import make_task_status_success
from .util import (
    ImporterConfig,
    exit_celery_with_error_message,
    get_importer_error_message,
    merge_dicts
)


@task(queue='case_import_queue')
def bulk_import_async(config_list_json, domain, excel_id):
    case_upload = CaseUpload.get(excel_id)
    # case_upload.trigger_upload fires off this task right before saving the CaseUploadRecord
    # because CaseUploadRecord needs to be saved with the task id firing off the task creates.
    # Occasionally, this task could start before the CaseUploadRecord was saved,
    # which causes unpredictable/undesirable error behavior
    case_upload.wait_for_case_upload_record()
    result_stored = False
    deprecated_case_types = get_data_dict_deprecated_case_types(domain)
    try:
        case_upload.check_file()
        all_results = []
        for index, config_json in enumerate(config_list_json):
            config = ImporterConfig.from_json(config_json)
            if config.case_type in deprecated_case_types:
                all_results.append(
                    _create_deprecated_error_dict(config.case_type)
                )
                continue

            with case_upload.get_spreadsheet(index) as spreadsheet:
                result = do_import(
                    spreadsheet,
                    config,
                    domain,
                    task=bulk_import_async,
                    record_form_callback=case_upload.record_form,
                )
                all_results.append(result)

        result = _merge_import_results(all_results)
        _alert_on_result(result, domain)
        # save the success result into the CaseUploadRecord
        case_upload.store_task_result(make_task_status_success(result))
        result_stored = True
    except ImporterError as e:
        return exit_celery_with_error_message(bulk_import_async, get_importer_error_message(e))
    finally:
        if not result_stored:
            store_failed_task_result.delay(excel_id)


@task(queue='case_import_queue')
def store_failed_task_result(upload_id):
    case_upload = CaseUpload.get(upload_id)
    case_upload.store_failed_task_result()


def _alert_on_result(result, domain):
    """ Check import result and send internal alerts based on result

    :param result: dict that should include key "created_count" pointing to an int
    """

    if result['created_count'] > 10000:
        message = "A case import just uploaded {num} new cases to HQ. {domain} might be scaling operations".format(
            num=result['created_count'],
            domain=domain
        )
        alert = AbnormalUsageAlert(source="case importer", domain=domain, message=message)
        send_abnormal_usage_alert.delay(alert)


def _merge_import_results(result_list):
    result = merge_dicts(result_list, keys_to_exclude=['errors'])

    # The errors key will be a dict, so we need to make sure to merge all unique
    # errors together for the final result
    result['errors'] = {}
    for r in result_list:
        new_errors = set(r['errors']) - set(result['errors'])
        for new_error in new_errors:
            result['errors'][new_error] = r['errors'][new_error]

    return result


def _create_deprecated_error_dict(case_type):
    return {
        'errors': {
            '': {
                'case_type': {
                    'error': 'Deprecated case type',
                    'description': f"Cannot import rows for deprecated \"{case_type}\" case type",
                    'rows': [],
                }
            }
        }
    }


metrics_gauge_task(
    'commcare.case_importer.files.total_bytes',
    get_case_upload_files_total_bytes,
    run_every=crontab(minute=0),
    multiprocess_mode=MPM_MAX
)
