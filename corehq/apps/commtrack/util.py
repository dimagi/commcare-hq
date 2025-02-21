import re
import uuid
from calendar import monthrange
from collections import namedtuple
from datetime import date, timedelta

from django.utils.text import slugify
from django.utils.translation import gettext as _

from text_unidecode import unidecode

from corehq import feature_previews, toggles
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import (
    ActionConfig,
    AlertConfig,
    CommtrackConfig,
    ConsumptionConfig,
    StockLevelsConfig,
    StockRestoreConfig,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program

CaseLocationTuple = namedtuple('CaseLocationTuple', 'case location')


def all_sms_codes(domain):
    config = CommtrackConfig.for_domain(domain)

    actions = {action.keyword: action for action in config.all_actions}
    products = {p.code: p for p in SQLProduct.active_objects.filter(domain=domain)}

    ret = {}
    for action_key, action in actions.items():
        ret[action_key] = ('action', action)
    for product_key, product in products.items():
        ret[product_key] = ('product', product)

    return ret


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

    config = CommtrackConfig(domain=domain)
    config.save()   # must be saved before submodels can be saved

    AlertConfig(commtrack_config=config).save()
    ConsumptionConfig(commtrack_config=config).save()
    StockLevelsConfig(commtrack_config=config).save()
    StockRestoreConfig(commtrack_config=config).save()
    config.set_actions([
        ActionConfig(
            action='receipts',
            keyword='r',
            caption='Received',
        ),
        ActionConfig(
            action='consumption',
            keyword='c',
            caption='Consumed',
        ),
        ActionConfig(
            action='consumption',
            subaction='loss',
            keyword='l',
            caption='Losses',
        ),
        ActionConfig(
            action='stockonhand',
            keyword='soh',
            caption='Stock on hand',
        ),
        ActionConfig(
            action='stockout',
            keyword='so',
            caption='Stock-out',
        ),
    ])
    config.save()   # save actions, and sync couch


def _enable_commtrack_previews(domain):
    for toggle_class in (
        toggles.COMMTRACK,
        feature_previews.VELLUM_ADVANCED_ITEMSETS,
    ):
        toggle_class.set(domain, True, toggles.NAMESPACE_DOMAIN)


def make_domain_commtrack(domain_object):
    domain_object.commtrack_enabled = True
    domain_object.locations_enabled = True
    domain_object.save()
    _create_commtrack_config_if_needed(domain_object.name)
    get_or_create_default_program(domain_object.name)
    _enable_commtrack_previews(domain_object.name)


def due_date_weekly(dow, past_period=0):  # 0 == sunday
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


def location_map_case_id(user):
    user_id = user.user_id
    case_id = uuid.uuid5(const.MOBILE_WORKER_UUID_NS, user_id).hex
    return case_id


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


def unicode_slug(text):
    return slugify(str(unidecode(text)))


def encode_if_needed(val):
    return val.encode("utf8") if isinstance(val, str) else val


def _fetch_ending_numbers(s):
    postfix = ''
    for char in s[::-1]:
        if not char.isdigit():
            break
        postfix = char + postfix
    return postfix


def generate_code(object_name, existing_codes):
    if not object_name:
        object_name = 'no name'

    matcher = re.compile(r"[\W\d]+")
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
