import json
import math
import warnings
from collections import namedtuple
from datetime import datetime, timedelta
from importlib import import_module

from django.conf import settings
from django.http import Http404
from django.utils.translation import ugettext as _

import pytz
from memoized import memoized

from dimagi.utils.dates import DateSpan

from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.const import USER_QUERY_LIMIT
from corehq.apps.reports.exceptions import EditFormValidationError
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.permissions import get_extra_permissions
from corehq.apps.users.util import user_id_to_username
from corehq.util.dates import iso_string_to_datetime
from corehq.util.log import send_HTML_email
from corehq.util.quickcache import quickcache
from corehq.util.timezones.utils import get_timezone_for_user

from .analytics.esaccessors import (
    get_all_user_ids_submitted,
    get_username_in_last_form_user_id_submitted,
)
from .models import HQUserType, TempCommCareUser


def make_form_couch_key(domain, user_id=Ellipsis):
    """
        This sets up the appropriate query for couch based on common report parameters.

        Note: Ellipsis is used as the default for user_id because
        None is actually emitted as a user_id on occasion in couch
    """
    prefix = ["submission"]
    key = [domain] if domain is not None else []
    if user_id == "":
        prefix.append('user')
    elif user_id is not Ellipsis:
        prefix.append('user')
        key.append(user_id)
    return [" ".join(prefix)] + key


def user_list(domain):
    #referenced in filters.users.SelectMobileWorkerFilter
    users = list(CommCareUser.by_domain(domain))
    users.extend(CommCareUser.by_domain(domain, is_active=False))
    users.sort(key=lambda user: (not user.is_active, user.username))
    return users


def get_all_users_by_domain(domain=None, group=None, user_ids=None,
                            user_filter=None, simplified=False, CommCareUser=None, include_inactive=False):
    """
        WHEN THERE ARE A LOT OF USERS, THIS IS AN EXPENSIVE OPERATION.
        Returns a list of CommCare Users based on domain, group, and user 
        filter (demo_user, admin, registered, unknown)
    """
    def _create_temp_user(user_id):
        username = get_username_from_forms(domain, user_id).lower()
        temp_user = TempCommCareUser(domain, username, user_id)
        if user_filter[temp_user.filter_flag].show:
            return temp_user
        return None

    user_ids = user_ids or []
    user_ids = [_f for _f in user_ids if _f]  # remove empty strings if any
    if not CommCareUser:
        from corehq.apps.users.models import CommCareUser

    if group:
        # get all the users only in this group and don't bother filtering.
        if not isinstance(group, Group):
            group = Group.get(group)
        users = group.get_users(is_active=(not include_inactive), only_commcare=True)
    elif user_ids:
        try:
            users = []
            for id in user_ids:
                user = CommCareUser.get_by_user_id(id)
                if not user and (user_filter[HQUserType.ADMIN].show or
                      user_filter[HQUserType.DEMO_USER].show or
                      user_filter[HQUserType.UNKNOWN].show):
                    user = _create_temp_user(id)
                if user:
                    users.append(user)
        except Exception:
            users = []
        if users and users[0] is None:
            raise Http404()
    else:
        if not user_filter:
            user_filter = HQUserType.all()
        users = []
        submitted_user_ids = set(get_all_user_ids_submitted(domain))
        registered_users_by_id = dict([(user.user_id, user) for user in CommCareUser.by_domain(domain)])
        if include_inactive:
            registered_users_by_id.update(dict(
                [(u.user_id, u) for u in CommCareUser.by_domain(domain, is_active=False)]
            ))
        for user_id in submitted_user_ids:
            if user_id in registered_users_by_id and user_filter[HQUserType.ACTIVE].show:
                user = registered_users_by_id[user_id]
                users.append(user)
            elif (user_id not in registered_users_by_id and
                 (user_filter[HQUserType.ADMIN].show or
                  user_filter[HQUserType.DEMO_USER].show or
                  user_filter[HQUserType.UNKNOWN].show)):
                user = _create_temp_user(user_id)
                if user:
                    users.append(user)
        if user_filter[HQUserType.UNKNOWN].show:
            users.append(TempCommCareUser(domain, '*', None))

        if user_filter[HQUserType.ACTIVE].show:
            # now add all the registered users who never submitted anything
            users.extend(user for id, user in registered_users_by_id.items() if id not in submitted_user_ids)

    if simplified:
        return [_report_user_dict(user) for user in users]
    return users


def get_username_from_forms(domain, user_id):

    def possible_usernames():
        yield get_username_in_last_form_user_id_submitted(domain, user_id)
        yield user_id_to_username(user_id)

    for possible_username in possible_usernames():
        if possible_username:
            return possible_username
    else:
        return HQUserType.human_readable[HQUserType.ADMIN]


def namedtupledict(name, fields):
    cls = namedtuple(name, fields)

    def __getitem__(self, item):
        if isinstance(item, str):
            warnings.warn(
                "namedtuple fields should be accessed as attributes",
                DeprecationWarning,
            )
            return getattr(self, item)
        return cls.__getitem__(self, item)

    def get(self, item, default=None):
        warnings.warn(
            "namedtuple fields should be accessed as attributes",
            DeprecationWarning,
        )
        return getattr(self, item, default)
    # return a subclass of cls that has the above __getitem__
    return type(name, (cls,), {
        '__getitem__': __getitem__,
        'get': get,
    })


class SimplifiedUserInfo(
        namedtupledict('SimplifiedUserInfo', (
            'user_id',
            'username_in_report',
            'raw_username',
            'is_active',
            'location_id',
        ))):

    ES_FIELDS = [
        '_id', 'username', 'first_name', 'last_name', 'doc_type', 'is_active', 'location_id', '__group_ids'
    ]

    @property
    @memoized
    def group_ids(self):
        if hasattr(self, '__group_ids'):
            return getattr(self, '__group_ids')
        return Group.by_user_id(self.user_id, False)


def _report_user_dict(user):
    """
    Accepts a user object or a dict such as that returned from elasticsearch.
    Make sure the following fields are available:
    ['_id', 'username', 'first_name', 'last_name', 'doc_type', 'is_active']
    """
    if not isinstance(user, dict):
        user_report_attrs = [
            'user_id', 'username_in_report', 'raw_username', 'is_active', 'location_id'
        ]
        return SimplifiedUserInfo(**{attr: getattr(user, attr)
                                     for attr in user_report_attrs})
    else:
        username = user.get('username', '')
        raw_username = (username.split("@")[0]
                        if user.get('doc_type', '') == "CommCareUser"
                        else username)
        first = user.get('first_name', '')
        last = user.get('last_name', '')
        username_in_report = _get_username_fragment(raw_username, first, last)
        info = SimplifiedUserInfo(
            user_id=user.get('_id', ''),
            username_in_report=username_in_report,
            raw_username=raw_username,
            is_active=user.get('is_active', None),
            location_id=user.get('location_id', None)
        )
        if '__group_ids' in user:
            group_ids = user['__group_ids']
            info.__group_ids = group_ids if isinstance(group_ids, list) else [group_ids]
        return info


# TODO: This is very similar code to what exists in apps/users/util/user_display_string
def _get_username_fragment(username, first='', last=''):
    full_name = ("%s %s" % (first, last)).strip()

    result = username
    if full_name:
        result = '{} "{}"'.format(result, full_name)

    return result


def get_simplified_users(user_es_query):
    """
    Accepts an instance of UserES and returns SimplifiedUserInfo dicts for the
    matching users, sorted by username.
    """
    users = user_es_query.fields(SimplifiedUserInfo.ES_FIELDS).run().hits
    users = list(map(_report_user_dict, users))
    return sorted(users, key=lambda u: u['username_in_report'])


def format_datatables_data(text, sort_key, raw=None):
    # todo: this is redundant with report.table_cell()
    # should remove/refactor one of them away
    data = {"html": text, "sort_key": sort_key}
    if raw is not None:
        data['raw'] = raw
    return data


def get_possible_reports(domain_name):
    from corehq.apps.reports.dispatcher import (ProjectReportDispatcher, CustomProjectReportDispatcher)

    # todo: exports should be its own permission at some point?
    report_map = (ProjectReportDispatcher().get_reports(domain_name) +
                  CustomProjectReportDispatcher().get_reports(domain_name))
    reports = []
    domain_obj = Domain.get_by_name(domain_name)
    for heading, models in report_map:
        for model in models:
            if getattr(model, 'parent_report_class', None):
                report_to_check_if_viewable = model.parent_report_class
            else:
                report_to_check_if_viewable = model

            if report_to_check_if_viewable.show_in_user_roles(domain=domain_name, project=domain_obj):
                path = model.__module__ + '.' + model.__name__
                reports.append({
                    'path': path,
                    'name': model.name,
                    'slug': path.replace('.', '_'),
                })

    for slug, name, is_visible in get_extra_permissions():
        if is_visible(domain_obj):
            reports.append({
                'path': slug,
                'name': name,
                'slug': slug.replace('.', '_'),
            })
    return reports


def friendly_timedelta(td):
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = [
        ("day", td.days),
        ("hour", hours),
        ("minute", minutes),
        ("second", seconds),
    ]
    text = []
    for t in parts:
        if t[1]:
            text.append("%d %s%s" % (t[1], t[0], "s" if t[1] != 1 else ""))
    return ", ".join(text)


# Copied/extended from http://djangosnippets.org/snippets/1170/
def batch_qs(qs, num_batches=10, min_batch_size=100000):
    """
    Returns a (start, end, total, queryset) tuple for each batch in the given
    queryset.

    Usage:
        # Make sure to order your querset
        article_qs = Article.objects.order_by('id')
        for start, end, total, qs in batch_qs(article_qs):
            print "Now processing %s - %s of %s" % (start + 1, end, total)
            for article in qs:
                print article.body
    """
    total = qs.count()
    if total < min_batch_size:
        batch_size = total
    else:
        batch_size = int(total / num_batches) or total
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        yield (start, end, total, qs[start:end])


def numcell(text, value=None, convert='int', raw=None):
    if value is None:
        try:
            value = int(text) if convert == 'int' else float(text)
            if math.isnan(value):
                text = '---'
            elif not convert == 'int': # assume this is a percentage column
                text = '%.f%%' % value
        except ValueError:
            value = text
    return format_datatables_data(text=text, sort_key=value, raw=raw)


def datespan_from_beginning(domain_object, timezone):
    startdate = domain_object.date_created
    now = datetime.utcnow()
    datespan = DateSpan(startdate, now, timezone=timezone)
    datespan.is_default = True
    return datespan


def get_installed_custom_modules():

    return [import_module(module) for module in settings.CUSTOM_MODULES]


def get_null_empty_value_bindparam(field_slug):
    return f'{field_slug}_empty_eq'


def get_INFilter_element_bindparam(base_name, index):
    return '%s_%d' % (base_name, index)


def get_INFilter_bindparams(base_name, values):
    return tuple(get_INFilter_element_bindparam(base_name, i) for i, val in enumerate(values))


def validate_xform_for_edit(xform):
    for node in xform.bind_nodes:
        if '@case_id' in node.attrib.get('nodeset') and node.attrib.get('calculate') == 'uuid()':
            raise EditFormValidationError(_('Form cannot be edited because it will create a new case'))

    return None


def get_report_timezone(request, domain):
    if not domain:
        return pytz.utc
    else:
        try:
            return get_timezone_for_user(request.couch_user, domain)
        except AttributeError:
            return get_timezone_for_user(None, domain)


@quickcache(['domain', 'mobile_user_and_group_slugs'], timeout=10)
def is_query_too_big(domain, mobile_user_and_group_slugs, request_user):
    from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter

    user_es_query = ExpandedMobileWorkerFilter.user_es_query(
        domain,
        mobile_user_and_group_slugs,
        request_user,
    )
    return user_es_query.count() > USER_QUERY_LIMIT


def send_report_download_email(title, recipient, link, subject=None):
    if subject is None:
        subject = _("%s: Requested export excel data") % title
    body = "The export you requested for the '%s' report is ready.<br>" \
           "You can download the data at the following link: %s<br><br>" \
           "Please remember that this link will only be active for 24 hours."

    send_HTML_email(
        subject,
        recipient,
        _(body) % (title, "<a href='%s'>%s</a>" % (link, link)),
        email_from=settings.DEFAULT_FROM_EMAIL
    )


class DatatablesParams(object):
    def __init__(self, count, start, desc, echo, search=None):
        self.count = count
        self.start = start
        self.end = start + count
        self.desc = desc
        self.echo = echo
        self.search = search

    def __repr__(self):
        return json.dumps({
            'start': self.start,
            'count': self.count,
            'echo': self.echo,
        }, indent=2)

    @classmethod
    def from_request_dict(cls, query):
        count = int(query.get("iDisplayLength", "10"))
        start = int(query.get("iDisplayStart", "0"))

        desc = (query.get("sSortDir_0", "desc") == "desc")
        echo = query.get("sEcho", "0")
        search = query.get("sSearch", "")

        return DatatablesParams(count, start, desc, echo, search)
