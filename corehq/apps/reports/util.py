from datetime import datetime
from django.contrib import messages
import logging
from corehq.apps.announcements.models import ReportAnnouncement
from corehq.apps.groups.models import Group
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.models import HQUserType, TempCommCareUser
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import user_id_to_username
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.modules import to_function
from django.http import Http404
import pytz
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request
from django.conf import settings


def make_form_couch_key(domain, by_submission_time=True,
                   xmlns=None, user_id=Ellipsis, app_id=None):
    """
        This sets up the appropriate query for couch based on common report parameters.

        Note: Ellipsis is used as the default for user_id because
        None is actually emitted as a user_id on occasion in couch
    """
    prefix = ["submission"] if by_submission_time else ["completion"]
    key = [domain] if domain is not None else []
    if xmlns == "":
        prefix.append('xmlns')
    elif app_id == "":
        prefix.append('app')
    elif user_id == "":
        prefix.append('user')
    else:
        if xmlns:
            prefix.append('xmlns')
            key.append(xmlns)
        if app_id:
            prefix.append('app')
            key.append(app_id)
        if user_id is not Ellipsis:
            prefix.append('user')
            key.append(user_id)
    return [" ".join(prefix)] + key


def all_xmlns_in_domain(domain):
    # todo replace form_list with this
    key = make_form_couch_key(domain, xmlns="")
    domain_xmlns = get_db().view('reports_forms/all_forms',
        startkey=key,
        endkey=key+[{}],
        group=True,
        group_level=3,
    ).all()
    return [d['key'][-1] for d in domain_xmlns if d['key'][-1] is not None]


def user_list(domain):
    #todo cleanup
    #referenced in filters.users.SelectMobileWorkerFilter
    users = list(CommCareUser.by_domain(domain))
    users.extend(CommCareUser.by_domain(domain, is_active=False))
    users.sort(key=lambda user: (not user.is_active, user.username))
    return users


def get_group_params(domain, group='', users=None, user_id_only=False, **kwargs):
    # refrenced in reports/views and create_export_filter below
    if group:
        if not isinstance(group, Group):
            group = Group.get(group)
        users = group.get_user_ids() if user_id_only else group.get_users()
    else:
        users = users or []
        if user_id_only:
            users = users or [user.user_id for user in CommCareUser.by_domain(domain)]
        else:
            users = [CommCareUser.get_by_user_id(userID) for userID in users] or CommCareUser.by_domain(domain)
    if not user_id_only:
        users = sorted(users, key=lambda user: user.user_id)
    return group, users


def get_all_users_by_domain(domain=None, group=None, user_ids=None,
                            user_filter=None, simplified=False, CommCareUser=None, include_inactive=False):
    """
        WHEN THERE ARE A LOT OF USERS, THIS IS AN EXPENSIVE OPERATION.
        Returns a list of CommCare Users based on domain, group, and user 
        filter (demo_user, admin, registered, unknown)
    """
    user_ids = user_ids if user_ids and user_ids[0] else None
    if not CommCareUser:
        from corehq.apps.users.models import CommCareUser

    if group:
        # get all the users only in this group and don't bother filtering.
        if not isinstance(group, Group):
            group = Group.get(group)
        users = group.get_users(only_commcare=True)
    elif user_ids is not None:
        try:
            users = [CommCareUser.get_by_user_id(id) for id in user_ids]
        except Exception:
            users = []
        if users and users[0] is None:
            raise Http404()
    else:
        if not user_filter:
            user_filter = HQUserType.use_defaults()
        users = []
        submitted_user_ids = get_all_userids_submitted(domain)
        registered_user_ids = dict([(user.user_id, user) for user in CommCareUser.by_domain(domain)])
        if include_inactive:
            registered_user_ids.update(dict([(u.user_id, u) for u in CommCareUser.by_domain(domain, is_active=False)]))
        for user_id in submitted_user_ids:
            if user_id in registered_user_ids and user_filter[HQUserType.REGISTERED].show:
                user = registered_user_ids[user_id]
                users.append(user)
            elif not user_id in registered_user_ids and \
                 (user_filter[HQUserType.ADMIN].show or
                  user_filter[HQUserType.DEMO_USER].show or
                  user_filter[HQUserType.UNKNOWN].show):
                username = get_username_from_forms(domain, user_id)
                temp_user = TempCommCareUser(domain, username, user_id)
                if user_filter[temp_user.filter_flag].show:
                    users.append(temp_user)
        if user_filter[HQUserType.UNKNOWN].show:
            users.append(TempCommCareUser(domain, '*', None))

        if user_filter[HQUserType.REGISTERED].show:
            # now add all the registered users who never submitted anything
            for user_id in registered_user_ids:
                if not user_id in submitted_user_ids:
                    user = CommCareUser.get_by_user_id(user_id)
                    users.append(user)

    if simplified:
        return [_report_user_dict(user) for user in users]
    return users

def get_all_userids_submitted(domain):
    submitted = get_db().view('reports_forms/all_submitted_users',
        startkey=[domain],
        endkey=[domain, {}],
        group=True,
    ).all()
    return [user['key'][1] for user in submitted]

def get_all_owner_ids_submitted(domain):
    key = ["all owner", domain]
    submitted = get_db().view('case/all_cases',
        group_level=3,
        startkey=key,
        endkey=key + [{}],
    ).all()
    return set([row['key'][2] for row in submitted])

def get_username_from_forms(domain, user_id):
    key = make_form_couch_key(domain, user_id=user_id)
    user_info = get_db().view(
        'reports_forms/all_forms',
        startkey=key,
        limit=1,
        reduce=False
    ).one()
    username = HQUserType.human_readable[HQUserType.ADMIN]
    try:
        possible_username = user_info['value']['username']
        if not possible_username == 'none':
            username = possible_username
        return username
    except KeyError:
        possible_username = user_id_to_username(user_id)
        if possible_username:
            username = possible_username
    return username


def _report_user_dict(user):
    user_report_attrs = ['user_id', 'username_in_report', 'raw_username', 'is_active']
    return dict([(attr, getattr(user, attr)) for attr in user_report_attrs])


def format_datatables_data(text, sort_key):
    # used below
    data = {"html": text,
            "sort_key": sort_key}
    return data

def app_export_filter(doc, app_id):
    if app_id:
        return (doc['app_id'] == app_id) if doc.has_key('app_id') else False
    elif app_id == '':
        return not doc.has_key('app_id')
    else:
        return True

def get_timezone(couch_user_id, domain):
    #todo cleanup
    timezone = None
    if couch_user_id:
        try:
            requesting_user = WebUser.get_by_user_id(couch_user_id)
        except CouchUser.AccountTypeError:
            return pytz.utc
        domain_membership = requesting_user.get_domain_membership(domain)
        if domain_membership:
            timezone = tz_utils.coerce_timezone_value(domain_membership.timezone)

    if not timezone:
        current_domain = Domain.get_by_name(domain)
        try:
            timezone = tz_utils.coerce_timezone_value(current_domain.default_timezone)
        except pytz.UnknownTimeZoneError:
            timezone = pytz.utc
    return timezone

def datespan_export_filter(doc, datespan):
    if isinstance(datespan, dict):
        datespan = DateSpan(**datespan)
    try:
        received_on = doc['received_on']
    except Exception:
        if settings.DEBUG:
            raise
        return False

    if datespan.startdate_param <= received_on < datespan.enddate_param:
        return True
    return False

def case_users_filter(doc, users):
    try:
        return doc['user_id'] in users
    except KeyError:
        return False

def case_group_filter(doc, group):
    if group:
        user_ids = set(group.get_static_user_ids())
        try:
            return doc['user_id'] in user_ids
        except KeyError:
            return False
    else:
        return True

def users_filter(doc, users):
    try:
        user_id = doc['form']['meta']['userID']
    except KeyError:
        user_id = None
    return user_id in users

def group_filter(doc, group):
    if group:
        user_ids = set(group.get_static_user_ids())
        try:
            return doc['form']['meta']['userID'] in user_ids
        except KeyError:
            return False
    else:
        return True


def create_export_filter(request, domain, export_type='form'):
    from corehq.apps.reports.filters.users import UserTypeFilter
    app_id = request.GET.get('app_id', None)

    group, users = get_group_params(domain, **json_request(request.GET))

    user_filters, use_user_filters = UserTypeFilter.get_user_filter(request)

    if export_type == 'case':
        if user_filters and use_user_filters:
            users_matching_filter = map(lambda x: x.get('user_id'), get_all_users_by_domain(domain,
                user_filter=user_filters, simplified=True))
            filter = SerializableFunction(case_users_filter, users=users_matching_filter)
        else:
            filter = SerializableFunction(case_group_filter, group=group)
    else:
        filter = SerializableFunction(app_export_filter, app_id=app_id)
        filter &= SerializableFunction(datespan_export_filter, datespan=request.datespan)
        if user_filters and use_user_filters:
            users_matching_filter = map(lambda x: x.get('user_id'), get_all_users_by_domain(domain,
                user_filter=user_filters, simplified=True))
            filter &= SerializableFunction(users_filter, users=users_matching_filter)
        else:
            filter &= SerializableFunction(group_filter, group=group)
    return filter


def get_possible_reports(domain):
    from corehq.apps.reports.dispatcher import (ProjectReportDispatcher,
        CustomProjectReportDispatcher)
    from corehq.apps.adm.dispatcher import ADMSectionDispatcher
    reports = []
    report_map = ProjectReportDispatcher().get_reports(domain) + \
                 CustomProjectReportDispatcher().get_reports(domain) +\
                 ADMSectionDispatcher().get_reports(domain)
    for heading, models in report_map:
        for model in models:
            reports.append({
                'path': model.__module__ + '.' + model.__name__, 
                'name': model.name
            })
    return reports

def format_relative_date(date, tz=pytz.utc):
    #todo cleanup
    now = datetime.now(tz=tz)
    time = datetime.replace(date, tzinfo=tz)
    dtime = now - time
    if dtime.days < 1:
        dtext = "Today"
    elif dtime.days < 2:
        dtext = "Yesterday"
    else:
        dtext = "%s days ago" % dtime.days
    return format_datatables_data(dtext, dtime.days)

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


def set_report_announcements_for_user(request, couch_user):
    key = ["type", ReportAnnouncement.__name__]
    now = datetime.utcnow()
    data = ReportAnnouncement.get_db().view('announcements/all_announcements',
        reduce=False,
        startkey=key + [now.isoformat()],
        endkey=key + [{}],
        stale=settings.COUCH_STALE_QUERY,
    ).all()
    announce_ids = [a['id'] for a in data if a['id'] not in couch_user.announcements_seen]
    for announcement_id in announce_ids:
        try:
            announcement = ReportAnnouncement.get(announcement_id)
            if announcement.show_to_new_users or (announcement.date_created > couch_user.created_on):
                messages.info(request, announcement.as_html)
        except Exception as e:
            logging.error("Could not fetch Report Announcement: %s" % e)


# Copied from http://djangosnippets.org/snippets/1170/
def batch_qs(qs, batch_size=1000):
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
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        yield (start, end, total, qs[start:end])

def stream_qs(qs, batch_size=1000):
    for _, _, _, qs in batch_qs(qs, batch_size):
        for item in qs:
            yield item
