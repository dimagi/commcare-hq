
from corehq.apps.users.models import CommCareUser
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.commtrack.models import *
from dimagi.utils.couch.database import get_db

"""
helper code to populate the various commtrack models, for ease of
development/testing, before we have proper UIs and imports
"""

def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code
    p.save()
    return p

def make_supply_point(domain, location, code, all_products=True):
    c = CommCareCase()
    c.domain = domain
    c.site_code = code
    c.type = 'supply-point'
    c.bind_to_location(location)
    c.save()

    products = []
    if all_products:
        products = get_db().view('commtrack/products', startkey=[domain], endkey=[domain, {}])
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
        pc.bind_to_location(location)
        pc.save()

    return c

def make_psi_config(domain):
    c = CommtrackConfig(
        domain=domain,
        multiaction_enabled=True,
        multiaction_keyword='p',
        actions = [
            CommtrackActionConfig(
                action_type='stockedoutfor',
                keyword='so',
                caption='Stock-out Days'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                keyword='r',
                caption='Other Receipts'
            ),
            CommtrackActionConfig(
                action_type='stockonhand',
                keyword='soh',
                multiaction_keyword='st',
                caption='Stock on Hand'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                keyword='s',
                name='sales',
                caption='Sales'
            ),
        ]
    )
    c.save()
    return c

    
