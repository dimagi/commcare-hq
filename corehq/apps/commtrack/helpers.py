
from corehq.apps.users.models import CommCareUser
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.commtrack.models import Product
from corehq.apps.sms import test_backend
from dimagi.utils.couch.database import get_db

def make_verified_contact(username, backend=test_backend.API_ID):
    """utility function to register 'verified' phone numbers for a commcare user"""
    u = CommCareUser.get_by_username(username)
    for phone in u.phone_numbers:
        u.save_verified_number(u.domain, phone, True, backend)

def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code
    p.save()
    return p

def make_supply_point(domain, code, all_products=True):
    c = CommCareCase()
    c.domain = domain
    c.site_code = code
    c.type = 'supply-point'
    c.save()

    products = []
    if all_products:
        products = get_db().view('commtrack/products', start_key=[domain], end_key=[domain, {}])
    for p in products:
        prod_id = p['id']
        pc = CommCareCase()
        pc.domain = domain
        pc.type = 'supply-point-product'
        pc.product = prod_id
        ix = CommCareCaseIndex()
        ix.identifier = 'parent'
        ix.referenced_type = 'supply-point'
        ix.referenced_id = c._id
        pc.indices = [ix]
        pc.save()

    return c
