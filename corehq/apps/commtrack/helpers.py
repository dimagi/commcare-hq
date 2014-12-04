from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.products.models import Product

"""
helper code to populate the various commtrack models, for ease of
development/testing, before we have proper UIs and imports
"""


def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p


def make_supply_point(domain, location, owner_id=None):
    return SupplyPointCase.create_from_location(domain, location, owner_id)
