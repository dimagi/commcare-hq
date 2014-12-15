from xml.etree import ElementTree
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import (
    CommtrackConfig, CommtrackActionConfig, RequisitionActions,
    CommtrackRequisitionConfig, SupplyPointCase, RequisitionCase
)
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
from corehq.apps.locations.models import Location
from corehq.apps.locations.schema import LocationType
import itertools
from datetime import datetime, date, timedelta
from calendar import monthrange
import math
import bisect
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from django.utils.text import slugify
from unidecode import unidecode
from dimagi.utils.parsing import json_format_datetime
from django.utils.translation import ugettext as _
import re


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


def make_program(domain, name, code, default=False):
    p = Program()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.default = default
    p.save()
    return p


def get_or_create_default_program(domain):
    program = Program.default_for_domain(domain)

    if program:
        return program
    else:
        return make_program(
            domain,
            _('Uncategorized'),
            _('uncategorized'),
            default=True
        )


def bootstrap_commtrack_settings_if_necessary(domain, requisitions_enabled=False):
    """
    Create a new CommtrackConfig object for a domain
    if it does not already exist.


    This adds some collection of default products, programs,
    SMS keywords, etc.
    """
    def _needs_commtrack_config(domain):
        return (domain and
                domain.commtrack_enabled and
                not CommtrackConfig.for_domain(domain.name))

    if not _needs_commtrack_config(domain):
        return

    config = CommtrackConfig(
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
    )

    if requisitions_enabled:
        config.requisition_config = get_default_requisition_config()

    config.save()

    program = get_or_create_default_program(domain.name)
    make_product(domain.name, 'Sample Product 1', 'pp', program.get_id)
    make_product(domain.name, 'Sample Product 2', 'pq', program.get_id)
    make_product(domain.name, 'Sample Product 3', 'pr', program.get_id)

    domain.location_types = [
        LocationType(
            name='state',
            allowed_parents=[''],
            administrative=True
        ),
        LocationType(
            name='district',
            allowed_parents=['state'],
            administrative=True
        ),
        LocationType(
            name='block',
            allowed_parents=['district'],
            administrative=True
        ),
        LocationType(
            name='village',
            allowed_parents=['block'],
            administrative=True
        ),
        LocationType(
            name='outlet',
            allowed_parents=['village']
        ),
    ]
    # this method is called during domain's post save, so this
    # is a little tricky, but it happens after the config is
    # created so should not cause problems
    domain.save()

    return config


def get_default_requisition_config():
    return CommtrackRequisitionConfig(
        enabled=True,
        actions=[
            CommtrackActionConfig(
                action=RequisitionActions.REQUEST,
                keyword='req',
                caption='Request',
            ),
            # TODO not tested yet, so not included
            # CommtrackActionConfig(
            #    action=RequisitionActions.APPROVAL,
            #    keyword='approve',
            #    caption='Approved',
            # ),
            CommtrackActionConfig(
                action=RequisitionActions.FULFILL,
                keyword='fulfill',
                caption='Fulfilled',
            ),
            CommtrackActionConfig(
                action=RequisitionActions.RECEIPTS,
                keyword='rec',
                caption='Requisition Receipts',
            ),
        ],
    )


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
            index=index,
            case_name=const.USER_LOCATION_OWNER_MAP_TYPE.replace('-', ' '),
            user_id=const.COMMTRACK_USERNAME,
        )

    submit_case_blocks(
        ElementTree.tostring(
            caseblock.as_xml(format_datetime=json_format_datetime)
        ),
        user.domain,
    )


def location_map_case_id(user):
    return 'user-owner-mapping-' + user._id


def get_commtrack_location_id(user, domain):
    if (
        user and
        user.get_domain_membership(domain.name) and
        user.get_domain_membership(domain.name).location_id and
        domain.commtrack_enabled
    ):
        return user.get_domain_membership(domain.name).location_id
    else:
        return None


def get_case_wrapper(data):
    return {
        const.SUPPLY_POINT_CASE_TYPE: SupplyPointCase,
        const.REQUISITION_CASE_TYPE: RequisitionCase,
    }.get(data.get('type'), CommCareCase)


def wrap_commtrack_case(case_json):
    return get_case_wrapper(case_json).wrap(case_json)


def unicode_slug(text):
    return slugify(unicode(unidecode(text)))


def encode_if_needed(val):
    return val.encode("utf8") if isinstance(val, unicode) else val


def generate_code(object_name, existing_codes):
    if not object_name:
        object_name = 'no name'

    matcher = re.compile("[\W\d]+")
    name_slug = matcher.sub(
        '_',
        unicode_slug(object_name.lower())
    ).strip('_')
    postfix = ''

    while name_slug + postfix in existing_codes:
        if postfix:
            postfix = str(int(postfix) + 1)
        else:
            postfix = '1'

    return name_slug + postfix
