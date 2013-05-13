from dimagi.utils.couch.database import get_db
from corehq.apps.commtrack.models import *
from corehq.apps.locations.models import Location
from casexml.apps.case.models import CommCareCase
import itertools
from datetime import datetime, date, timedelta
from calendar import monthrange
import math
import bisect

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

def bootstrap_default(domain, requisitions_enabled=True):
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
            LocationType(name='province', allowed_parents=[''], administrative=True),
            LocationType(name='district', allowed_parents=['province'], administrative=True),
            LocationType(name='village', allowed_parents=['district'], administrative=True),
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
                    action_type=RequisitionActions.PACK,
                    keyword='pack',
                    caption='Packed',
                    name='packed',
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
    last_reported = getattr(product_case, 'last_reported', datetime(2000, 1, 1)).date()

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
