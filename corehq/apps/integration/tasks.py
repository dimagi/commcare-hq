from django.conf import settings

from celery.schedules import crontab

from corehq.apps.celery import periodic_task
from corehq.apps.es.case_search import CaseSearchES, case_property_missing, case_property_query
from corehq.apps.es import filters
from corehq.apps.integration.kyc.models import KycConfig, KycVerificationStatus
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.services import request_payments_for_cases
from corehq.toggles import KYC_VERIFICATION, MTN_MOBILE_WORKER_VERIFICATION
from corehq.util.metrics import metrics_gauge
from corehq.apps.integration.payments.const import PaymentProperties
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE


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
    run_every=crontab(minute="*/15"),
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
                filters.OR(
                    case_property_query(PaymentProperties.PAYMENT_SUBMITTED, 'False'),
                    case_property_missing(PaymentProperties.PAYMENT_SUBMITTED),
                ),
            )
        )
    ).values_list('_id', flat=True)
