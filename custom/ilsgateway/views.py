from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.commtrack.models import Product
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser, WebUser


class GlobalStats(BaseDomainView):

    section_name = 'Global Stats'
    section_url = ""
    template_name = "ilsgateway/global_stats.html"

    @property
    def main_context(self):
        try:
            facilities = Location.filter_by_type_count(self.domain, 'FACILITY')
        except TypeError:
            facilities = 0

        contacts = CommCareUser.by_domain(self.domain, reduce=True)
        web_users = WebUser.by_domain(self.domain, reduce=True)

        try:
            products = len(Product.by_domain(self.domain))
        except ResourceNotFound:
            products = 0

        main_context = super(GlobalStats, self).main_context
        context = {
            'supply_points':  len(list(Location.by_domain(self.domain))),
            'facilities': facilities,
            'contacts':  contacts[0]['value'] if contacts else 0,
            'web_users': web_users[0]['value'] if web_users else 0,
            'products':  products,
            #TODO add next after the enlargement ILS migration
            'product_stocks':  0,
            'stock_transactions':  0,
            'inbound_messages':  0,
            'outbound_messages':  0
        }
        main_context.update(context)
        return main_context

