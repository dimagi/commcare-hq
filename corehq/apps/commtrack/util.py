import uuid
from collections import namedtuple
from xml.etree import ElementTree
from casexml.apps.case.models import CommCareCase
from corehq import toggles, feature_previews
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.commtrack.models import CommtrackConfig, SupplyPointCase, CommtrackActionConfig, \
    CommtrackRequisitionConfig
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
import itertools
from datetime import date, timedelta
from calendar import monthrange
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock
from django.utils.text import slugify
from unidecode import unidecode
from django.utils.translation import ugettext as _
import re

from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.utils.general import should_use_sql_backend

CaseLocationTuple = namedtuple('CaseLocationTuple', 'case location')


def all_sms_codes(domain):
    config = CommtrackConfig.for_domain(domain)

    actions = dict((action.keyword, action) for action in config.actions)
    products = dict((p.code, p) for p in Product.by_domain(domain))
    commands = {
        config.multiaction_keyword: {'type': 'stock_report_generic', 'caption': 'Stock Report'},
    }

    sms_codes = zip(('action', 'product', 'command'), (actions, products, commands))
    return dict(itertools.chain(*([(k.lower(), (type, v)) for k, v in codes.iteritems()] for type, codes in sms_codes)))


def get_supply_point_and_location(domain, site_code):
    location = SQLLocation.objects.get_or_None(domain=domain, site_code=site_code)
    if location:
        case = location.linked_supply_point()
    else:
        case = None

    return CaseLocationTuple(case=case, location=location)


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


def _create_commtrack_config_if_needed(domain):
    if CommtrackConfig.for_domain(domain):
        return

    CommtrackConfig(
        domain=domain,
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
    ).save()


def _enable_commtrack_previews(domain):
    for toggle_class in (
        toggles.COMMTRACK,
        feature_previews.VELLUM_ADVANCED_ITEMSETS,
        toggles.STOCK_TRANSACTION_EXPORT,
    ):
        toggle_class.set(domain, True, toggles.NAMESPACE_DOMAIN)


def make_domain_commtrack(domain_object):
    domain_object.commtrack_enabled = True
    domain_object.locations_enabled = True
    domain_object.save()
    _create_commtrack_config_if_needed(domain_object.name)
    get_or_create_default_program(domain_object.name)
    _enable_commtrack_previews(domain_object.name)


def get_default_requisition_config():
    return CommtrackRequisitionConfig(
        enabled=True,
        actions=[
            CommtrackActionConfig(
                action=RequisitionActions.REQUEST,
                keyword='req',
                caption='Request',
            ),
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


def submit_mapping_case_block(user, index):
    mapping = user.get_location_map_case()

    if mapping:
        caseblock = CaseBlock(
            create=False,
            case_id=mapping.case_id,
            index=index
        )
    else:
        caseblock = CaseBlock(
            create=True,
            case_type=const.USER_LOCATION_OWNER_MAP_TYPE,
            case_id=location_map_case_id(user),
            owner_id=user._id,
            index=index,
            case_name=const.USER_LOCATION_OWNER_MAP_TYPE.replace('-', ' '),
            user_id=const.COMMTRACK_USERNAME,
        )

    submit_case_blocks(
        ElementTree.tostring(
            caseblock.as_xml()
        ),
        user.domain,
    )


def location_map_case_id(user):
    if should_use_sql_backend(user.domain):
        user_id = user.user_id
        if isinstance(user_id, unicode):
            user_id = user_id.encode('utf8')
        return uuid.uuid5(const.MOBILE_WORKER_UUID_NS, user_id).hex
    return 'user-owner-mapping-' + user.user_id


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
    }.get(data.get('type'), CommCareCase)


def unicode_slug(text):
    return slugify(unicode(unidecode(text)))


def encode_if_needed(val):
    return val.encode("utf8") if isinstance(val, unicode) else val


def _fetch_ending_numbers(s):
    matcher = re.compile("\d*$")
    return matcher.search(s).group()


def generate_code(object_name, existing_codes):
    if not object_name:
        object_name = 'no name'

    matcher = re.compile("[\W\d]+")
    name_slug = matcher.sub(
        '_',
        unicode_slug(object_name.lower())
    ).strip('_')

    postfix = _fetch_ending_numbers(object_name)

    while name_slug + postfix in existing_codes:
        if postfix:
            postfix = str(int(postfix) + 1)
        else:
            postfix = '1'

    return name_slug + postfix
