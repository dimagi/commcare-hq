from django.conf import settings

from celery.schedules import crontab

from corehq.apps.celery import periodic_task
from corehq.apps.integration.kyc.models import KycConfig, KycVerificationStatus
from corehq.toggles import KYC_VERIFICATION
from corehq.util.metrics import metrics_gauge


@periodic_task(run_every=crontab(minute=0, hour=1, day_of_week=1), queue=settings.CELERY_PERIODIC_QUEUE,
               acks_late=True, ignore_result=True)
def report_verification_status_count():
    for domain in KYC_VERIFICATION.get_enabled_domains():
        kyc_config = KycConfig.objects.get(domain=domain)
        kyc_users = kyc_config.get_kyc_users()
        success_count = 0
        failure_count = 0
        for kyc_user in kyc_users:
            if kyc_user.kyc_verification_status is KycVerificationStatus.PASSED:
                success_count += 1
            elif kyc_user.kyc_verification_status is KycVerificationStatus.FAILED:
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
