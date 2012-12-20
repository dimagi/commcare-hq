
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
    p.code = code.lower()
    p.save()
    return p

# TODO use case-xml case creation workflow
def make_supply_point(domain, location, code):
    c = CommCareCase()
    c.domain = domain
    c.site_code = code
    c.type = 'supply-point'
    c.bind_to_location(location)
    c.save()
    return c

# TODO use case-xml case creation workflow
def make_supply_point_product(supply_point_case, product_uuid):
    pc = CommCareCase()
    pc.domain = supply_point_case.domain
    pc.type = 'supply-point-product'
    pc.product = product_uuid
    ix = CommCareCaseIndex()
    ix.identifier = 'parent'
    ix.referenced_type = 'supply-point'
    ix.referenced_id = supply_point_case._id
    pc.indices = [ix]
    pc.location_ = supply_point_case.location_
    pc.save()
    return pc

def make_psi_config(domain):
    c = CommtrackConfig(
        domain=domain,
        multiaction_enabled=True,
        multiaction_keyword='s',
        actions = [
            CommtrackActionConfig(
                action_type='stockedoutfor',
                keyword='d',
                caption='Stock-out Days'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                keyword='r',
                caption='Other Receipts'
            ),
            CommtrackActionConfig(
                action_type='stockonhand',
                keyword='b',
                caption='Balance'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                name='sales',
                keyword='p',
                caption='Placements'
            ),
        ]
    )
    c.save()
    return c

    
