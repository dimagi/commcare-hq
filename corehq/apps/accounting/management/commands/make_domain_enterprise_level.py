from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand

from corehq.apps.domain.forms import DimagiOnlyEnterpriseForm
from corehq.apps.domain.models import Domain
from corehq.util.decorators import require_debug_true


class Command(BaseCommand):
    help = ('Create a billing account and an enterprise level subscription '
            'for the given domain')

    def add_arguments(self, parser):
        parser.add_argument('domain')

    @require_debug_true()
    def handle(self, domain, **kwargs):
        assert Domain.get_by_name(domain) is not None
        DimagiOnlyEnterpriseForm(domain, 'management@command.com').process_subscription_management()
