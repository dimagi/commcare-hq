from __future__ import absolute_import
from django.apps import apps
from django.core.management.base import BaseCommand

from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsUsageFee
from corehq.apps.smsbillables.utils import log_smsbillables_info


def bootstrap_usage_fees(apps):
    SmsUsageFee.create_new(INCOMING, 0.01)
    SmsUsageFee.create_new(OUTGOING, 0.01)
    log_smsbillables_info("Updated usage fees.")


class Command(BaseCommand):
    help = "bootstrap usage fees"

    def handle(self, **options):
        bootstrap_usage_fees(apps)
