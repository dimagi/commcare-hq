from django.conf import settings

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from corehq.apps.celery import periodic_task
from corehq.apps.es.case_search import CaseSearchES, case_property_query
from corehq.apps.es import filters
from corehq.apps.geospatial.utils import get_celery_task_tracker
from corehq.apps.integration.kyc.models import KycConfig, KycVerificationStatus
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.services import request_payments_for_cases, request_payments_status_for_cases
from corehq.toggles import KYC_VERIFICATION, MTN_MOBILE_WORKER_VERIFICATION
from corehq.util.metrics import metrics_gauge
from corehq.apps.integration.payments.const import PaymentProperties, PaymentStatus
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE

logger = get_task_logger(__name__)
REQUEST_MOMO_PAYMENTS_TASK_SLUG = 'request_momo_payments'


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
    deferred_domains = []
    for domain in MTN_MOBILE_WORKER_VERIFICATION.get_enabled_domains():
        try:
            config = MoMoConfig.objects.get(domain=domain)
        except MoMoConfig.DoesNotExist:
            continue

        if _is_revert_verification_request_active(domain):
            deferred_domains.append(domain)
            continue

        _request_momo_payments_for_domain(domain, config)

    _retry_for_deferred_domains(deferred_domains)


def _is_revert_verification_request_active(domain):
    from corehq.apps.integration.payments.views import REVERT_VERIFICATION_REQUEST_SLUG

    task_tracker = get_celery_task_tracker(domain, REVERT_VERIFICATION_REQUEST_SLUG)
    return task_tracker.is_active()


def _retry_for_deferred_domains(deferred_domains):
    # Implements a one-time retry for domains that had an active revert verification request
    # during the initial attempt. If the revert request is still active at retry time, the domain is skipped
    # and payment submissions will be picked up in the next scheduled run.

    for domain in deferred_domains:
        if _is_revert_verification_request_active(domain):
            logger.info(
                "Skipped payment submissions for domain {} as revert verification request is active."
                "Will be retried in next schedule".format(domain)
            )
            continue
        config = MoMoConfig.objects.get(domain=domain)
        _request_momo_payments_for_domain(domain, config)


def _request_momo_payments_for_domain(domain, config):
    task_tracker = get_celery_task_tracker(domain, REQUEST_MOMO_PAYMENTS_TASK_SLUG)
    task_tracker.mark_requested(timeout=60 * 60)
    try:
        case_ids = _get_payment_case_ids_on_domain(domain)
        request_payments_for_cases(case_ids, config)
    except Exception as err:
        raise err
    finally:
        task_tracker.mark_completed()


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


@periodic_task(
    run_every=crontab(minute=0, hour=[3, 6]),
    queue=settings.CELERY_PERIODIC_QUEUE,
    acks_late=True,
    ignore_result=True,
)
def fetch_momo_payments_status():
    for domain in MTN_MOBILE_WORKER_VERIFICATION.get_enabled_domains():
        try:
            config = MoMoConfig.objects.get(domain=domain)
            case_ids = _get_submitted_payment_case_ids_on_domain(domain)
            request_payments_status_for_cases(case_ids, config)
        except MoMoConfig.DoesNotExist:
            continue


def _get_submitted_payment_case_ids_on_domain(domain):
    return (
        CaseSearchES()
        .domain(domain)
        .case_type(MOMO_PAYMENT_CASE_TYPE)
        .filter(
            case_property_query(PaymentProperties.PAYMENT_STATUS, PaymentStatus.SUBMITTED),
        )
    ).values_list('_id', flat=True)
