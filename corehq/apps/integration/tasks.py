
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.utils.module_loading import import_string
from django.conf import settings


from corehq.apps.reports.tasks import _store_excel_in_blobdb
from corehq.apps.reports.util import send_report_download_email
from corehq.util.view_utils import absolute_reverse

from corehq.apps.celery import periodic_task, task
from corehq.apps.es.case_search import CaseSearchES, case_property_query
from corehq.apps.es import filters
from corehq.apps.integration.kyc.models import KycConfig, KycVerificationStatus
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.services import request_payments_for_cases
from corehq.toggles import KYC_VERIFICATION, MTN_MOBILE_WORKER_VERIFICATION
from corehq.util.metrics import metrics_gauge
from corehq.apps.integration.payments.const import PaymentProperties, PaymentStatus
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE


logger = get_task_logger(__name__)


@periodic_task(run_every=crontab(minute=0, hour=1, day_of_week=1), queue=settings.CELERY_PERIODIC_QUEUE,
               acks_late=True, ignore_result=True)
def report_verification_status_count():
    for domain in KYC_VERIFICATION.get_enabled_domains():
        kyc_config = KycConfig.objects.get(domain=domain)
        kyc_users = kyc_config.get_kyc_users()
        success_count = 0
        failure_count = 0
        for kyc_user in kyc_users:
            if kyc_user.kyc_verification_status == KycVerificationStatus.PASSED:
                success_count += 1
            elif kyc_user.kyc_verification_status == KycVerificationStatus.FAILED:
                failure_count += 1

        metrics_gauge(
            'commcare.integration.kyc.verification.success.count',
            success_count,
            tags={'domain': domain}
        )
        metrics_gauge(
            'commcare.integration.kyc.verification.failure.count',
            failure_count,
            tags={'domain': domain}
        )


@periodic_task(
    run_every=crontab(minute=0, hour=1),
    queue=settings.CELERY_PERIODIC_QUEUE,
    acks_late=True,
    ignore_result=True,
)
def request_momo_payments():
    for domain in MTN_MOBILE_WORKER_VERIFICATION.get_enabled_domains():
        try:
            config = MoMoConfig.objects.get(domain=domain)
        except MoMoConfig.DoesNotExist:
            continue

        case_ids = _get_payment_case_ids_on_domain(domain)
        request_payments_for_cases(case_ids, config)


def _get_payment_case_ids_on_domain(domain):
    return (
        CaseSearchES()
        .domain(domain)
        .case_type(MOMO_PAYMENT_CASE_TYPE)
        .filter(
            filters.AND(
                case_property_query(PaymentProperties.PAYMENT_VERIFIED, 'True'),
                filters.NOT(
                    case_property_query(PaymentProperties.PAYMENT_STATUS, PaymentStatus.SUBMITTED),
                ),
            )
        )
    ).values_list('_id', flat=True)


@task(serializer='json', ignore_result=True)
def export_all_rows_task(class_path, export_context, recipient_list=None, subject=None):
    ReportClass = import_string(class_path)
    report = ReportClass.reconstruct_from_export_context(export_context)

    file = report.export_to_file()
    hash_id = _store_excel_in_blobdb(class_path, file, export_context['domain'], report.report_title)
    logger.info(f'Stored report {report.report_title} with parameters: {export_context["request_params"]} in hash {hash_id}')
    if not recipient_list:
        recipient_list = [report.request.couch_user.get_email()]
    for recipient in recipient_list:
        link = absolute_reverse(
            "export_report",
            args=[export_context['domain'], str(hash_id), report.get_export_format()],
        )
        send_report_download_email(report.report_title, recipient, link, subject, domain=export_context['domain'])
        logger.info(f'Sent {report.report_title} with hash {hash_id} to {recipient}')
