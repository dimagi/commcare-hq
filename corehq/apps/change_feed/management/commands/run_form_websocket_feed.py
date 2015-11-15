from optparse import make_option
from django.core.management import BaseCommand
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from ws4redis.publisher import RedisPublisher
from ws4redis.redis_store import RedisMessage
import json
import time


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--from',
                    action='store',
                    dest='from',
                    default=None,
                    help="Start at this point in the changes feed (defaults to the end)"),
        make_option('--sleep',
                    action='store',
                    dest='sleep',
                    default=None,
                    help="Start at this point in the changes feed (defaults to the end)"),
    )

    def handle(self, *args, **options):
        since = options['from']
        sleep = float(options['sleep'] or '.01')
        last_domain = None
        change_feed = KafkaChangeFeed(topic=topics.FORM, group_id='form-feed')
        for change in change_feed.iter_changes(since=since, forever=True):
            if not change.deleted:
                # this is just helpful for demos to find domain transitions
                if change.metadata.domain != last_domain:
                    last_domain = change.metadata.domain
                    print change.sequence_id, last_domain

                message = RedisMessage(json.dumps(change.metadata.to_json()))
                RedisPublisher(facility='form-feed', broadcast=True).publish_message(message)
                time.sleep(sleep)
