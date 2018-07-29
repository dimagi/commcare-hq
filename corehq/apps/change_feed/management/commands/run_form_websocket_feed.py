from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from django_countries.data import COUNTRIES
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from ws4redis.publisher import RedisPublisher
from ws4redis.redis_store import RedisMessage
import json
import time
from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache
import six


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--from',
            action='store',
            dest='from',
            default=None,
            help="Start at this point in the changes feed (defaults to the end)",
        )
        parser.add_argument(
            '--sleep',
            action='store',
            dest='sleep',
            default=None,
            help="Sleep this long between emissions (useful for demos)",
        )
        parser.add_argument(
            '--compact',
            action='store_true',
            dest='compact',
            default=False,
            help="Use 'compact' mode - don't include additional domain metadata (faster)",
        )

    def handle(self, **options):
        since = options['from']
        sleep = float(options['sleep'] or '.01')
        last_domain = None
        change_feed = KafkaChangeFeed(topics=[topics.FORM], group_id='form-feed')
        for change in change_feed.iter_changes(since=since, forever=True):
            if not change.deleted:
                # this is just helpful for demos to find domain transitions
                if change.metadata.domain != last_domain:
                    last_domain = change.metadata.domain
                    print(change.sequence_id, last_domain)

                metadata = change.metadata.to_json()
                if not options['compact']:
                    metadata['country'] = _get_country(change.metadata.domain)
                message = RedisMessage(json.dumps(metadata))
                RedisPublisher(facility='form-feed', broadcast=True).publish_message(message)
                time.sleep(sleep)


@quickcache(vary_on=['domain'], timeout=600)
def _get_country(domain):
    project = Domain.get_by_name(domain)
    if project and project.deployment.countries:
        return six.text_type(COUNTRIES.get(project.deployment.countries[0], ''))
