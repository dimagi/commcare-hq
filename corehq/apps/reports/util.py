from datetime import datetime, timedelta
from corehq.apps.groups.models import Group
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.models import HQUserType, TempCommCareUser
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import user_id_to_username
from couchdbkit.schema.properties import DictProperty
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from dimagi.utils.couch.database import get_db
from dimagi.utils.data.deid_generator import DeidGenerator
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.modules import to_function
from dimagi.utils.parsing import string_to_datetime
from django.http import Http404
import pytz
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request
from django.conf import settings

def report_context(domain,
            report_partial=None,
            title=None,
            headers=None,
            rows=None,
            individual=None,
            case_type=None,
            show_case_type_counts=True,
            group=None,
            ufilter=None,
            form=None,
            datespan=None,
            show_time_notice=False
        ):
    context = {
        "domain": domain,
        "report": {
            "name": title,
            "headers": headers or [],
            "rows": rows or []
        },
        "show_time_notice": show_time_notice,
        "now": datetime.utcnow()
    }
    if report_partial:
        context.update(report_partial=report_partial)
    if individual is not None and domain is not None:
        context.update(
            show_users=True,
            users= user_list(domain),
            individual=individual,
        )
    if form is not None and domain is not None:
        context.update(
            show_forms=True,
            selected_form=form,
            forms=form_list(domain),
        )
        
    if group is not None and domain is not None:
        context.update(
            show_groups=True,
            group=group,
            groups=Group.get_reporting_groups(domain),
        )
    if case_type is not None and domain is not None:
        if individual:
            user_ids = [individual]
        elif group is not None:
            _, user_ids = get_all_users_by_domain(domain, group=group)
        elif ufilter is not None:
            _, user_ids = get_all_users_by_domain(domain, filter_users=ufilter)
        else:
            user_ids = None

        case_types = get_case_types(domain, user_ids)
        if len(case_types) == 1:
            case_type = case_types.items()[0][0]

        open_count, all_count = get_case_counts(domain, user_ids=user_ids)
        context.update(
            show_case_types=True,
            case_types=case_types,
            n_all_case_types={'all': all_count, 'open': open_count},
            case_type=case_type,
        )
    if datespan:
        context.update(
            show_dates=True,
            datespan=datespan
        )
    return context

def user_list(domain): 
    users = list(CommCareUser.by_domain(domain))
    users.extend(CommCareUser.by_domain(domain, is_active=False))
    users.sort(key=lambda user: (not user.is_active, user.username))
    return users

def form_list(domain):
    view = get_db().view("formtrends/form_duration_by_user",
                         startkey=["xdu", domain, ""],
                         endkey=["xdu", domain, {}],
                         group=True,
                         group_level=3,
                         reduce=True)
    return [{"text": xmlns_to_name(domain, r["key"][2], app_id=None), "val": r["key"][2]} for r in view]

def get_case_types(domain, user_ids=None):
    case_types = {}
    key = [domain]
    for r in get_db().view('hqcase/all_cases',
        startkey=key,
        endkey=key + [{}],
        group_level=2
    ).all():
        case_type = r['key'][1]
        if case_type:
            open_count, all_count = get_case_counts(domain, case_type, user_ids)
            case_types[case_type] = {'open': open_count, 'all': all_count}
    return case_types

def get_case_counts(domain, case_type=None, user_ids=None):
    user_ids = user_ids or [{}]
    for view_name in ('hqcase/open_cases', 'hqcase/all_cases'):
        def individual_counts():
            for user_id in user_ids:
                key = [domain, case_type or {}, user_id]
                try:
                    yield get_db().view(view_name,
                        startkey=key,
                        endkey=key + [{}],
                        group_level=0
                    ).one()['value']
                except TypeError:
                    yield 0
        yield sum(individual_counts())

def get_group_params(domain, group='', users=None, user_id_only=False, **kwargs):
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

# todo CLEAN THIS UP Clean up this whole file, too
def get_all_users_by_domain(domain, group='', individual='', filter_users=None):
    """ Returns a list of CommCare Users based on domain, group, and user filter (demo_user, admin, registered, unknown)
    """
    if group:
        # get all the users only in this group and don't bother filtering.
        if not isinstance(group, Group):
            group = Group.get(group)
        users =  group.get_users(only_commcare=True)
    elif individual:
        try:
            users = [CommCareUser.get_by_user_id(individual)]
        except Exception:
            users = []
        if users and users[0] is None:
            raise Http404()
    else:
        if not filter_users:
            filter_users = HQUserType.use_defaults()
        users = []
        submitted_user_ids = get_all_userids_submitted(domain)
        registered_user_ids = [user.user_id for user in CommCareUser.by_domain(domain)]
        for user_id in submitted_user_ids:
            if user_id in registered_user_ids and filter_users[HQUserType.REGISTERED].show:
                user = CommCareUser.get_by_user_id(user_id)
                users.append(user)
            elif not user_id in registered_user_ids and \
                 (filter_users[HQUserType.ADMIN].show or
                  filter_users[HQUserType.DEMO_USER].show or
                  filter_users[HQUserType.UNKNOWN].show):
                username = get_username_from_forms(domain, user_id)
                temp_user = TempCommCareUser(domain, username, user_id)
                if filter_users[temp_user.filter_flag].show:
                    users.append(temp_user)
        if filter_users[HQUserType.UNKNOWN].show:
            users.append(TempCommCareUser(domain, '', None))

        if filter_users[HQUserType.REGISTERED].show:
            # now add all the registered users who never submitted anything
            for user_id in registered_user_ids:
                if not user_id in submitted_user_ids:
                    user = CommCareUser.get_by_user_id(user_id)
                    users.append(user)
    return users

def get_all_userids_submitted(domain):
    submitted = get_db().view(
        'reports/all_users_submitted',
        startkey=[domain],
        endkey=[domain, {}],
        group=True,
        reduce=True
    ).all()
    return [ user['key'][1] for user in submitted]

def get_username_from_forms(domain, user_id):
    user_info = get_db().view(
        'reports/submit_history',
        startkey=[domain, user_id],
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

def format_datatables_data(text, sort_key):
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
    pass
    try:
        return doc['user_id'] in users
    except KeyError:
        return False

def case_group_filter(doc, group):
    if group:
        user_ids = set(group.get_user_ids())
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
        user_ids = set(group.get_user_ids())
        try:
            return doc['form']['meta']['userID'] in user_ids
        except KeyError:
            return False
    else:
        return True

def create_export_filter(request, domain, export_type='form'):
    from corehq.apps.reports.fields import FilterUsersField
    app_id = request.GET.get('app_id', None)

    group, users = get_group_params(domain, **json_request(request.GET))

    user_filters, use_user_filters = FilterUsersField.get_user_filter(request)

    if export_type == 'case':
        if user_filters and use_user_filters:
            users_matching_filter = map(lambda x: x._id, get_all_users_by_domain(domain, filter_users=user_filters))
            filter = SerializableFunction(case_users_filter, users=users_matching_filter)
        else:
            filter = SerializableFunction(case_group_filter, group=group)
    else:
        filter = SerializableFunction(instances) & SerializableFunction(app_export_filter, app_id=app_id)
        filter &= SerializableFunction(datespan_export_filter, datespan=request.datespan)
        if user_filters and use_user_filters:
            users_matching_filter = map(lambda x: x._id, get_all_users_by_domain(domain, filter_users=user_filters))
            filter &= SerializableFunction(users_filter, users=users_matching_filter)
        else:
            filter &= SerializableFunction(group_filter, group=group)
    return filter

def get_possible_reports(domain):
    reports = []
    report_map = []
    report_map.extend(settings.PROJECT_REPORT_MAP.items())
    report_map.extend(settings.CUSTOM_REPORT_MAP.get(domain, {}).items())
    for heading, models in report_map:
        for model in models:
            reports.append({'path': model, 'name': to_function(model).name})
    return reports

def format_relative_date(date, tz=pytz.utc):
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


def domain_from_args_or_kwargs(*args, **kwargs):
    domain = kwargs.get('domain')
    if not domain:
        for arg in args:
            if isinstance(arg, str):
                try:
                    domain = Domain.get_by_name(arg)
                except Exception:
                    pass
    return domain
