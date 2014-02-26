from corehq.apps.accounting.forms import is_active_subscription
from corehq.apps.accounting.models import Subscription
from django.core.management import BaseCommand
from optparse import make_option


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--update', action='store_true', default=False, help='Update the subscriptions'),
    )

    def handle(self, *args, **options):
        for subscription in Subscription.objects.all():
            is_subscription_active = is_active_subscription(subscription.date_start, subscription.date_end)
            if subscription.is_active != is_subscription_active:
                if options.get('update', False):
                    print 'Updating subscription with id=%d' % subscription.id
                    subscription.is_active = is_subscription_active
                    subscription.save()
                else:
                    print 'Subscription needs updating: id=%d ' % subscription.id
