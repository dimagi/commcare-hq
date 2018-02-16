from __future__ import absolute_import
from collections import defaultdict

from django.core.management import BaseCommand

from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.tasks import _queue_indicators


class Command(BaseCommand):

    def handle(self, **options):
        indicators_by_domain_doc_type = defaultdict(list)
        for indicator in AsyncIndicator.objects.all():
            indicators_by_domain_doc_type[(indicator.domain, indicator.doc_type)].append(indicator)
        for k, indicators in indicators_by_domain_doc_type.items():
            _queue_indicators(indicators)
