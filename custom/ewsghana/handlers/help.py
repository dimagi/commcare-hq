from corehq.apps.products.models import SQLProduct
from custom.ewsghana.handlers import HELP_TEXT, DEACTIVATE_REMINDERS, REACTIVATE_REMINDERS
from custom.ewsghana.handlers.keyword import KeywordHandler
from custom.ewsghana.utils import user_needs_reminders


class HelpHandler(KeywordHandler):

    def help(self):
        self.respond(HELP_TEXT)

    def handle(self):
        topic = self.args[0].lower()
        if topic == 'stock':
            self.respond("Please send your receipts in the format "
                         "' <Commodity code> <stock on hand > . <quantity received>'")
        elif topic == 'reminder':
            if user_needs_reminders(self.user):
                self.respond(DEACTIVATE_REMINDERS)
            else:
                self.respond(REACTIVATE_REMINDERS)
        elif 'code' in topic:
            codes = SQLProduct.by_domain(self.domain).order_by('code').values_list('code', flat=True)
            self.respond("Available commodity codes: %(codes)s", codes=", ".join(codes))
        else:
            try:
                sql_product = SQLProduct.objects.get(domain=self.domain, code=topic)
                msg = "%s is the commodity code for %s" % (topic, sql_product.name)
                if sql_product.units:
                    msg += " (%s)" % sql_product.units
                if sql_product.description and sql_product.description not in sql_product.name:
                    msg += " %s" % sql_product.description
                self.respond(msg)
            except SQLProduct.DoesNotExist:
                self.help()
