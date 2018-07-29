from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.accounting.signals import subscription_upgrade_or_downgrade
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = ("Send KISSmetrics data on subscriptions for all domains")

    def handle(self, **options):
        for domain in Domain.get_all():
            subscription_upgrade_or_downgrade.send_robust(None, domain=domain)
