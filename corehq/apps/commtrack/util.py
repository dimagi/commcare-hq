from xml.etree import ElementTree
from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import (CommtrackConfig, CommtrackActionConfig, LocationType, RequisitionActions,
                                          CommtrackRequisitionConfig, Product, SupplyPointCase, SupplyPointProductCase,
                                          RequisitionCase, Program)
from corehq.apps.locations.models import Location
import itertools
from datetime import datetime, date, timedelta
from calendar import monthrange
import math
import bisect
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2


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

    actions = dict((action.keyword, action) for action in config.actions)
    products = dict((p.code, p) for p in Product.by_domain(domain))
    commands = {
        config.multiaction_keyword: {'type': 'stock_report_generic', 'caption': 'Stock Report'},
    }

    sms_codes = zip(('action', 'product', 'command'), (actions, products, commands))
    return dict(itertools.chain(*([(k.lower(), (type, v)) for k, v in codes.iteritems()] for type, codes in sms_codes)))

def get_supply_point(domain, site_code=None, loc=None):
    if loc is None:
        loc = Location.view('commtrack/locations_by_code',
                            key=[domain, site_code.lower()],
                            include_docs=True).first()
    if loc:
        case = SupplyPointCase.get_by_location(loc)
    else:
        case = None

    return {
        'case': case,
        'location': loc,
    }

def make_product(domain, name, code, program_id):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.program_id = program_id
    p.save()
    return p

def make_program(domain, name, code):
    p = Program()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p

def get_or_make_def_program(domain):
    program = [p for p in Program.by_domain(domain) if p.name == "Default"]
    if len(program) == 0:
        return make_program(domain, 'Default', 'def')
    else:
        return program[0]


def bootstrap_commtrack_settings_if_necessary(domain, requisitions_enabled=False):
    if not(domain and domain.commtrack_enabled and not domain.commtrack_settings):
        return

    c = CommtrackConfig(
        domain=domain.name,
        multiaction_enabled=True,
        multiaction_keyword='report',
        actions=[
            CommtrackActionConfig(
                action='receipts',
                keyword='r',
                caption='Received',
            ),
            CommtrackActionConfig(
                action='consumption',
                keyword='c',
                caption='Consumed',
            ),
            CommtrackActionConfig(
                action='consumption',
                subaction='loss',
                keyword='l',
                caption='Losses',
            ),
            CommtrackActionConfig(
                action='stockonhand',
                keyword='soh',
                caption='Stock on hand',
            ),
            CommtrackActionConfig(
                action='stockout',
                keyword='so',
                caption='Stock-out',
            ),
        ],
        location_types=[
            LocationType(name='state', allowed_parents=[''], administrative=True),
            LocationType(name='district', allowed_parents=['state'], administrative=True),
            LocationType(name='block', allowed_parents=['district'], administrative=True),
            LocationType(name='village', allowed_parents=['block'], administrative=True),
            LocationType(name='outlet', allowed_parents=['block', 'village']),
        ],
        supply_point_types=[],
    )
    if requisitions_enabled:
        c.requisition_config = CommtrackRequisitionConfig(
            enabled=True,
            actions=[
                CommtrackActionConfig(
                    action=RequisitionActions.REQUEST,
                    keyword='req',
                    caption='Request',
                ),
                CommtrackActionConfig(
                    action=RequisitionActions.APPROVAL,
                    keyword='approve',
                    caption='Approved',
                ),
                CommtrackActionConfig(
                    action=RequisitionActions.PACK,
                    keyword='pack',
                    caption='Packed',
                ),
                CommtrackActionConfig(
                    action=RequisitionActions.RECEIPTS,
                    keyword='rec',
                    caption='Requisition Receipts',
                ),
            ],
        )
    c.save()

    program = make_program(domain.name, 'Default', 'def')
    make_product(domain.name, 'Sample Product 1', 'pp', program.get_id)
    make_product(domain.name, 'Sample Product 2', 'pq', program.get_id)
    make_product(domain.name, 'Sample Product 3', 'pr', program.get_id)

    return c


def due_date_weekly(dow, past_period=0): # 0 == sunday
    """compute the next due date on a weekly schedule, where reports are
    due on 'dow' day of the week (0:sunday, 6:saturday). 'next' due date
    is the first due date that occurs today or in the future. if past_period
    is non-zero, return the due date that occured N before the next due date
    """
    cur_weekday = date.today().isoweekday()
    days_till_due = (dow - cur_weekday) % 7
    return date.today() + timedelta(days=days_till_due - 7 * past_period)

def due_date_monthly(day, from_end=False, past_period=0):
    """compute the next due date on a monthly schedule, where reports are
    due on 'day' day of the month. (if from_end is true, due date is 'day' days
    before the end of the month, where 0 is the last day of the month). 'next' due date
    is the first due date that occurs today or in the future. if past_period
    is non-zero, return the due date that occured N before the next due date
    """
    if from_end:
        assert False, 'not supported yet'

    month_diff = -past_period
    if date.today().day > day:
        month_diff += 1
    month_seq = date.today().year * 12 + (date.today().month - 1)
    month_seq += month_diff

    y = month_seq // 12
    m = month_seq % 12 + 1
    return date(y, m, min(day, monthrange(y, m)[1]))

def num_periods_late(product_case, schedule, *schedule_args):
    last_reported = datetime.strptime(getattr(product_case, 'last_reported', '2000-01-01')[:10], '%Y-%m-%d').date()

    class DueDateStream(object):
        """mimic an array of due dates to perform a binary search"""

        def __getitem__(self, i):
            return self.normalize(self.due_date(i + 1))

        def __len__(self):
            """highest number of periods late before we stop caring"""
            max_horizon = 30. * 365.2425 / self.period_length() # arbitrary upper limit -- 30 years
            return math.ceil(max_horizon)

        def due_date(self, n):
            return {
                'weekly': due_date_weekly,
                'monthly': due_date_monthly,
            }[schedule](*schedule_args, past_period=n)

        def period_length(self, n=100):
            """get average length of reporting period"""
            return (self.due_date(0) - self.due_date(n)).days / float(n)

        def normalize(self, dt):
            """convert dates into a numerical scale (where greater == more in the past)"""
            return -(dt - date(2000, 1, 1)).days

    stream = DueDateStream()
    # find the earliest due date that is on or after the most-recent report date,
    # and return how many reporting periods back it occurs
    return bisect.bisect_right(stream, stream.normalize(last_reported))

def submit_mapping_case_block(user, index):
    mapping = user.get_location_map_case()

    if mapping:
        caseblock = CaseBlock(
            create=False,
            case_id=mapping._id,
            version=V2,
            index=index
        )
    else:
        caseblock = CaseBlock(
            create=True,
            case_type=const.USER_LOCATION_OWNER_MAP_TYPE,
            case_id=location_map_case_id(user),
            version=V2,
            owner_id=user._id,
            index=index
        )

    submit_case_blocks(
        ElementTree.tostring(caseblock.as_xml()),
        user.domain,
        user.username,
        user._id
    )


def location_map_case_id(user):
    return 'user-owner-mapping-' + user._id


def is_commtrack_location(user, domain):
    return True if user and user.location_id and domain.commtrack_enabled else False


def get_case_wrapper(data):
    return {
        const.SUPPLY_POINT_CASE_TYPE: SupplyPointCase,
        const.SUPPLY_POINT_PRODUCT_CASE_TYPE: SupplyPointProductCase,
        const.REQUISITION_CASE_TYPE: RequisitionCase,
    }.get(data.get('type'), CommCareCase)


def wrap_commtrack_case(case_json):
    return get_case_wrapper(case_json).wrap(case_json)
