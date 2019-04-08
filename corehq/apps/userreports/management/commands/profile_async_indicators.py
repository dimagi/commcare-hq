from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import cProfile

from django.core.management.base import BaseCommand

from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from corehq.apps.userreports.management.commands.profile_data_source import print_profile_stats
from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.tasks import _get_config


class Command(BaseCommand):
    help = "Profile async indicator processing time"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('count', type=int)
        parser.add_argument('--sort', dest='sort', action='store', default='time')

    def handle(self, domain, count, **options):
        sort_by = options['sort']
        indicators = AsyncIndicator.objects.filter(domain=domain).order_by('-date_created')[:count]
        print('processing {} indicators'.format(len(indicators)))

        # build up data source configs and docs
        configs = {}
        docs = {}
        for indicator in indicators:
            doc_store = get_document_store_for_doc_type(
                domain, indicator.doc_type, load_source="profile_async_indicators")
            docs[indicator.doc_id] = doc_store.get_document(indicator.doc_id)
            for config_id in indicator.indicator_config_ids:
                configs[config_id] = _get_config(config_id)

        local_variables = {
            '_simulate_indicator_saves': _simulate_indicator_saves,
            'indicators': indicators,
            'docs': docs,
            'configs': configs,
        }
        cProfile.runctx('_simulate_indicator_saves(indicators, docs, configs)', {},
                        local_variables, 'async_ucr_stats.log')
        print_profile_stats('async_ucr_stats.log', sort_by)


def _simulate_indicator_saves(indicators, docs, configs):
    for indicator in indicators:
        _simulate_async_indicator_save(indicator, docs[indicator.doc_id], configs)


def _simulate_async_indicator_save(indicator, doc, configs):
    eval_context = EvaluationContext(doc)
    for config_id in indicator.indicator_config_ids:
        config = configs[config_id]
        config.get_all_values(doc, eval_context)
