from celery.schedules import crontab
from celery.task import task

from corehq.apps.hqadmin.tasks import (
    AbnormalUsageAlert,
    send_abnormal_usage_alert,
)
from corehq.util.metrics import metrics_gauge_task

from .do_import import do_import
from .exceptions import ImporterError
from .tracking.analytics import get_case_upload_files_total_bytes
from .tracking.case_upload_tracker import CaseUpload
from .tracking.task_status import normalize_task_status_result, make_task_status_success
from .util import get_importer_error_message, exit_celery_with_error_message


@task(serializer='pickle', queue='case_import_queue')
def bulk_import_async(config, domain, excel_id):
    case_upload = CaseUpload.get(excel_id)
    result_stored = False
    try:
        case_upload.check_file()
        with case_upload.get_spreadsheet() as spreadsheet:
            result = do_import(spreadsheet, config, domain, task=bulk_import_async,
                               record_form_callback=case_upload.record_form)

        _alert_on_result(result, domain)
        # save the success result into the CaseUploadRecord
        case_upload.store_task_result(make_task_status_success(result))
        result_stored = True
    except ImporterError as e:
        return exit_celery_with_error_message(bulk_import_async, get_importer_error_message(e))
    finally:
        if not result_stored:
            store_task_result_if_failed.delay(excel_id)


@task(serializer='pickle', queue='case_import_queue')
def store_task_result_if_failed(upload_id):
    case_upload = CaseUpload.get(upload_id)
    case_upload.store_task_result_if_failed()


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


total_bytes = metrics_gauge_task(
    'commcare.case_importer.files.total_bytes',
    get_case_upload_files_total_bytes,
    run_every=crontab(minute=0)
)
