from dimagi.utils.couch.database import get_db
from corehq.apps.commtrack.models import *
from corehq.apps.locations.models import Location
from casexml.apps.case.models import CommCareCase
import itertools

def all_supply_point_types(domain):
    return [e['key'][1] for e in get_db().view('commtrack/supply_point_types', startkey=[domain], endkey=[domain, {}], group_level=2)]

def supply_point_type_categories(domain):
    config = CommtrackConfig.for_domain(domain)
    categories = config.supply_point_categories
    other_types = set(all_supply_point_types(domain)) - set(config.known_supply_point_types)
    categories['_oth'] = list(other_types)
    return categories

def all_sms_codes(domain):
    config = CommtrackConfig.for_domain(domain)

    actions = dict((action_config._keyword(False), action_config) for action_config in config.actions)
    products = dict((p.code, p) for p in Product.by_domain(domain))
    commands = {
        config.multiaction_keyword: {'type': 'stock_report_generic', 'caption': 'Stock Report'},
    }

    sms_codes = zip(('action', 'product', 'command'), (actions, products, commands))
    return dict(itertools.chain(*([(k.lower(), (type, v)) for k, v in codes.iteritems()] for type, codes in sms_codes)))

def get_supply_point(domain, site_code):
    loc = Location.view('commtrack/locations_by_code',
                        key=[domain, site_code.lower()],
                        include_docs=True).first()
    if loc:
        case = CommCareCase.view('commtrack/supply_point_by_loc',
                                 key=[domain, loc._id],
                                 include_docs=True).first()
    else:
        case = None

    return {
        'case': case,
        'location': loc,
    }

def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p

def bootstrap_default(domain, requisitions_enabled=False):
    c = CommtrackConfig(
        domain=domain,
        multiaction_enabled=True,
        multiaction_keyword='report',
        actions=[
            CommtrackActionConfig(
                action_type='receipts',
                keyword='r',
                caption='Received',
                name='received',
            ),
            CommtrackActionConfig(
                action_type='consumption',
                keyword='c',
                caption='Consumed',
                name='consumed',
            ),
            CommtrackActionConfig(
                action_type='stockonhand',
                keyword='soh',
                caption='Stock on hand',
                name='stock_on_hand',
            ),
            CommtrackActionConfig(
                action_type='stockout',
                keyword='so',
                caption='Stock-out',
                name='stock_out',
            ),
        ],
        location_types=[
            LocationType(name='province', allowed_parents=['']),
            LocationType(name='district', allowed_parents=['province']),
            LocationType(name='village', allowed_parents=['district']),
            LocationType(name='dispensary', allowed_parents=['village']),
        ],
        supply_point_types=[],
    )
    if requisitions_enabled:
        c.requisition_config = CommtrackRequisitionConfig(
            enabled=True,
            actions=[
                CommtrackActionConfig(
                    action_type=RequisitionActions.REQUEST,
                    keyword='req',
                    caption='Request',
                    name='request',
                ),
                CommtrackActionConfig(
                    action_type=RequisitionActions.APPROVAL,
                    keyword='approve',
                    caption='Approved',
                    name='approved',
                ),
                CommtrackActionConfig(
                    action_type=RequisitionActions.FILL,
                    keyword='fill',
                    caption='Filled',
                    name='filled',
                ),
                CommtrackActionConfig(
                    action_type=RequisitionActions.RECEIPTS,
                    keyword='rec',
                    caption='Requisition Receipts',
                    name='req_received',
                ),
            ],
        )
    c.save()

    make_product(domain, 'Sample Product 1', 'pp')
    make_product(domain, 'Sample Product 2', 'pq')
    make_product(domain, 'Sample Product 3', 'pr')

    return c
