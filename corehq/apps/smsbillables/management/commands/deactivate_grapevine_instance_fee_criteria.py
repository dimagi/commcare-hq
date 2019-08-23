from django.core.management.base import BaseCommand
from corehq.apps.smsbillables.models import SmsGatewayFeeCriteria
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.grapevine.models import SQLGrapevineBackend


def deactivate_grapevine_instance_fee_criteria(apps=None):
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    to_deactivate = sms_gateway_fee_criteria_class.objects.filter(
        backend_api_id=SQLGrapevineBackend.get_api_id(),
        backend_instance__isnull=False,
        is_active=True,
    )
    assert to_deactivate.count() <= 2
    to_deactivate.update(is_active=False)

    log_smsbillables_info("Deactivated Grapevine instance fees.")


class Command(BaseCommand):
    help = "Deactivate Grapevine instance fees"

    def handle(self, **options):
        deactivate_grapevine_instance_fee_criteria()
