from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.apps.change_feed import topics
from corehq.util.couchdb_management import couch_config
from corehq.util.pagination import PaginationEventHandler
from fluff.pillow import get_fluff_pillow_configs
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider
from pillowtop.reindexer.reindexer import PillowChangeProviderReindexer
from pillowtop.utils import get_pillow_by_name


class ReindexEventHandler(PaginationEventHandler):

    def __init__(self, log_prefix):
        self.log_prefix = log_prefix

    def page_start(self, total_emitted, *args, **kwargs):
        domain, doc_type = kwargs.get('startkey')[:2]
        print ('{} Fetching rows {}-{} from couch: domain="{}" doc_type="{}"'.format(
            self.log_prefix,
            total_emitted,
            total_emitted + kwargs['limit'] - 1,
            domain,
            doc_type
        ))

    def page_end(self, total_emitted, duration, *args, **kwargs):
        print('{} View call took {}'.format(self.log_prefix, duration))


class Command(BaseCommand):
    help = (
        'Reindex a fluff pillow. '
        'If no domains are specified all domains for the pillow will be re-indexed.'
    )

    def add_arguments(self, parser):
        parser.add_argument('pillow_name')
        parser.add_argument('--domain', nargs='+')

    def handle(self, pillow_name, **options):
        fluff_configs = {config.name: config for config in get_fluff_pillow_configs()}

        if pillow_name not in fluff_configs:
            raise CommandError('Unrecognised fluff pillow: "{}". Options are:\n\t{}'.format(
                pillow_name, '\n\t'.join(fluff_configs)))

        pillow_getter = get_pillow_by_name(pillow_name, instantiate=False)
        pillow = pillow_getter(delete_filtered=True)

        domains = options.get('domain') or pillow.domains
        domains_not_in_pillow = set(domains) - set(pillow.domains)
        if domains_not_in_pillow:
            bad_domains = ', '.join(domains_not_in_pillow)
            available_domains = ', '.join(pillow.domains)
            raise CommandError(
                "The following domains aren't for this pillow: {}.\nAvailable domains are: {}".format(
                    bad_domains, available_domains
                ))

        if pillow.kafka_topic in (topics.CASE, topics.FORM):
            couch_db = couch_config.get_db(None)
        elif pillow.kafka_topic == topics.COMMCARE_USER:
            couch_db = couch_config.get_db(settings.NEW_USERS_GROUPS_DB)
        else:
            raise CommandError('Reindexer not configured for topic: {}'.format(pillow.kafka_topic))

        change_provider = CouchDomainDocTypeChangeProvider(
            couch_db=couch_db,
            domains=domains,
            doc_types=[pillow.doc_type],
            event_handler=ReindexEventHandler(pillow_name),
        )

        PillowChangeProviderReindexer(pillow, change_provider).reindex()
