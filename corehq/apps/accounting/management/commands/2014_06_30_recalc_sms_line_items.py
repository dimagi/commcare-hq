from optparse import make_option
from django.core.management import BaseCommand
from corehq.apps.accounting.invoicing import SmsLineItemFactory
from corehq.apps.accounting.models import LineItem, FeatureType


class Command(BaseCommand):
    help = ("Recalculates LineItems for SMS charges due to change in "
            "gateway_fee calculation.")

    def handle(self, *args, **options):
        sms_line_items = LineItem.objects.filter(
            feature_rate__feature__feature_type=FeatureType.SMS).all()
        for line_item in sms_line_items:
            line_item_factory = SmsLineItemFactory(
                line_item.invoice.subscription,
                line_item.feature_rate,
                line_item.invoice
            )
            new_cost = line_item_factory.unit_cost
            print "recalculating charge %s => %s" % (line_item.unit_cost, new_cost)
            line_item.unit_cost = new_cost
            line_item.save()

