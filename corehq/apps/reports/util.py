import json
import logging
import math
import warnings
from collections import defaultdict, namedtuple
from datetime import datetime
import pytz

from django.core.cache import cache
from django.db.transaction import atomic
from django.http import Http404
from django.utils.translation import gettext as _

from memoized import memoized

from dimagi.utils.dates import DateSpan
from dimagi.utils.logging import notify_exception

from celery.schedules import crontab

from corehq.apps.celery import periodic_task
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.const import USER_QUERY_LIMIT, HQ_TABLEAU_GROUP_NAME
from corehq.apps.reports.exceptions import TableauAPIError
from corehq.apps.reports.models import TableauServer, TableauAPISession, TableauUser, TableauConnectedApp
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser
from corehq.apps.users.permissions import get_extra_permissions
from corehq.apps.users.util import user_id_to_username
from corehq.apps.user_importer.helpers import spec_value_to_boolean_or_none
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstance
from corehq.toggles import TABLEAU_USER_SYNCING
from corehq.util.log import send_HTML_email
from corehq.util.quickcache import quickcache

from .analytics.esaccessors import (
    get_all_user_ids_submitted,
    get_username_in_last_form_user_id_submitted,
)
from .models import HQUserType, TempCommCareUser
from corehq.apps.es.case_search import CaseSearchES, case_property_missing


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
                if not user and (user_filter[HQUserType.ADMIN].show
                      or user_filter[HQUserType.DEMO_USER].show
                      or user_filter[HQUserType.UNKNOWN].show):
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
            elif (user_id not in registered_users_by_id
                 and (user_filter[HQUserType.ADMIN].show
                 or user_filter[HQUserType.DEMO_USER].show
                 or user_filter[HQUserType.UNKNOWN].show)):
                user = _create_temp_user(user_id)
                if user:
                    users.append(user)
        if user_filter[HQUserType.UNKNOWN].show:
            users.append(TempCommCareUser(domain, '*', None))

        if user_filter[HQUserType.ACTIVE].show:
            # now add all the registered users who never submitted anything
            users.extend(user for id, user in registered_users_by_id.items() if id not in submitted_user_ids)

    if simplified:
        return [_report_user(user) for user in users]
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


def get_user_id_from_form(form_id):
    key = f'xform-{form_id}-user_id'
    user_id = cache.get(key)
    if not user_id:
        try:
            user_id = XFormInstance.objects.get_form(form_id).user_id
        except XFormNotFound:
            return None
        cache.set(key, user_id, 12 * 60 * 60)
    return user_id


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
        '_id', 'domain', 'username', 'first_name', 'last_name',
        'doc_type', 'is_active', 'location_id', '__group_ids'
    ]

    @property
    @memoized
    def group_ids(self):
        if hasattr(self, '__group_ids'):
            return getattr(self, '__group_ids')
        return Group.by_user_id(self.user_id, False)


def _report_user(user):
    """
    Accepts a user object or a dict such as that returned from elasticsearch.
    Make sure the following fields (attributes) are available:
    _id, username, first_name, last_name, doc_type, is_active
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
    users = list(map(_report_user, users))
    return sorted(users, key=lambda u: u.username_in_report)


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
    report_map = (ProjectReportDispatcher().get_reports(domain_name)
                  + CustomProjectReportDispatcher().get_reports(domain_name))
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
            elif not convert == 'int':  # assume this is a percentage column
                text = '%.f%%' % value
        except ValueError:
            value = text
    return format_datatables_data(text=text, sort_key=value, raw=raw)


def datespan_from_beginning(domain_object, timezone):
    # Start and end dates must be naive (no timezone) to work with DateSpan
    # domain creation time is expected to be a naive date in UTC
    startdate = pytz.utc.localize(domain_object.date_created)
    localized_start = startdate.astimezone(timezone)
    localized_start = datetime(year=localized_start.year, month=localized_start.month, day=localized_start.day)

    now = datetime.now(tz=timezone)
    localized_end = datetime(year=now.year, month=now.month, day=now.day)

    datespan = DateSpan(localized_start, localized_end, timezone=timezone)
    datespan.is_default = True
    return datespan


def get_null_empty_value_bindparam(field_slug):
    return f'{field_slug}_empty_eq'


def get_INFilter_element_bindparam(base_name, index):
    return '%s_%d' % (base_name, index)


def get_INFilter_bindparams(base_name, values):
    return tuple(get_INFilter_element_bindparam(base_name, i) for i, val in enumerate(values))


@quickcache(['domain', 'mobile_user_and_group_slugs'], timeout=10)
def is_query_too_big(domain, mobile_user_and_group_slugs, request_user):
    from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter

    user_es_query = ExpandedMobileWorkerFilter.user_es_query(
        domain,
        mobile_user_and_group_slugs,
        request_user,
    )
    return user_es_query.count() > USER_QUERY_LIMIT


def send_report_download_email(title, recipient, link, subject=None, domain=None):
    if subject is None:
        subject = _("%s: Requested export excel data") % title
    body = "The export you requested for the '%s' report is ready.<br>" \
           "You can download the data at the following link: %s<br><br>" \
           "Please remember that this link will only be active for 24 hours."

    send_HTML_email(
        subject,
        recipient,
        _(body) % (title, "<a href='%s'>%s</a>" % (link, link)),
        domain=domain,
        use_domain_gateway=True,
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


# --- Tableau API util methods ---

TableauGroupTuple = namedtuple('TableauGroupTuple', ['name', 'id'])
DEFAULT_TABLEAU_ROLE = TableauUser.Roles.UNLICENSED.value
logger = logging.getLogger('tableau_util')


def tableau_username(HQ_username):
    return 'HQ/' + HQ_username


def _group_json_to_tuples(group_json):
    group_tuples = [TableauGroupTuple(group_dict['name'], group_dict['id']) for group_dict in group_json]
    # Remove default Tableau group and HQ group:
    group_tuples_without_defaults = []
    for group in group_tuples:
        if not (group.name == 'All Users' or group.name == HQ_TABLEAU_GROUP_NAME):
            group_tuples_without_defaults.append(group)
    return group_tuples_without_defaults


@quickcache(['domain'], timeout=30 * 60)
def get_all_tableau_groups(domain, session=None):
    '''
    Returns a list of all Tableau groups on the site as list of TableauGroupTuples.
    '''
    session = session or TableauAPISession.create_session_for_domain(domain)
    group_json = session.query_groups()
    return _group_json_to_tuples(group_json)


def get_allowed_tableau_groups_for_domain(domain):
    '''
    Returns a list of the Tableau groups that have been approved in the project settings.
    '''
    return TableauServer.objects.get(domain=domain).allowed_tableau_groups


def get_tableau_groups_for_user(domain, username):
    '''
    Returns a list of Tableau groups that the given user belongs to.
    '''
    session = TableauAPISession.create_session_for_domain(domain)
    user = TableauUser.objects.filter(
        server=session.tableau_connected_app.server
    ).get(username=username)
    group_json = session.get_groups_for_user_id(user.tableau_user_id)
    return _group_json_to_tuples(group_json)


def _notify_tableau_exception(e, domain):
    notify_exception(None, str(e), details={
        'domain': domain
    })


def get_matching_tableau_users_from_other_domains(user):
    return list(TableauUser.objects.filter(
        username=user.username,
        server__server_name=user.server.server_name,
        server__target_site=user.server.target_site,
    ).exclude(server__domain=user.server.domain))


@atomic
def add_tableau_user(domain, username):
    '''
    Creates a TableauUser object with the given username and a default role of Viewer, and adds a new user with
    these details to the Tableau instance.
    '''
    try:
        session = TableauAPISession.create_session_for_domain(domain)
    except TableauConnectedApp.DoesNotExist as e:
        _notify_tableau_exception(e, domain)
        return
    user, created, matching_tableau_users_from_other_domains_exist = _add_tableau_user_local(session, username)
    if created and not matching_tableau_users_from_other_domains_exist:
        try:
            _add_tableau_user_remote(session, user)
        except TableauAPIError as e:
            if e.code != 409017:  # This is the "user already added to site" code.
                raise


def _add_tableau_user_local(session, username, role=DEFAULT_TABLEAU_ROLE):
    user, created = TableauUser.objects.get_or_create(
        server=session.tableau_connected_app.server,
        username=username,
        role=role,
    )

    # Copy information from matching TableauUsers on other domains if there are any
    matching_tableau_users_from_other_domains = get_matching_tableau_users_from_other_domains(user)
    if matching_tableau_users_from_other_domains:
        user.tableau_user_id = matching_tableau_users_from_other_domains[0].tableau_user_id
        user.role = matching_tableau_users_from_other_domains[0].role
        user.save()

    return (user, created, bool(matching_tableau_users_from_other_domains))


def _add_tableau_user_remote(session, user, role=DEFAULT_TABLEAU_ROLE):
    new_id = session.create_user(tableau_username(user.username), role)
    for local_tableau_user in [user] + get_matching_tableau_users_from_other_domains(user):
        local_tableau_user.tableau_user_id = new_id
        local_tableau_user.save()
    _add_user_to_HQ_group(session, user)
    return new_id


@atomic
def delete_tableau_user(domain, username, session=None):
    '''
    Deletes the TableauUser object with the given username and removes it from the Tableau instance.
    '''
    session = session or TableauAPISession.create_session_for_domain(domain)
    if get_matching_tableau_users_from_other_domains(
            TableauUser.objects.get(username=username, server__domain=domain)):
        _delete_user_local(session, username)
    else:
        deleted_user_id = _delete_user_local(session, username)
        _delete_user_remote(session, deleted_user_id)  # Only delete remotely if no other local TableauUsers exist


def _delete_user_local(session, username):
    user = TableauUser.objects.filter(
        server=session.tableau_connected_app.server
    ).get(username=username)
    id = user.tableau_user_id
    user.delete()
    return id


def _delete_user_remote(session, deleted_user_id):
    session.delete_user(deleted_user_id)


@atomic
def update_tableau_user(domain, username, role=None, groups=[], session=None):
    '''
    Update the TableauUser object to have the given role and new group details. The `groups` arg should be a list
    of TableauGroupTuples.
    '''
    session = session or TableauAPISession.create_session_for_domain(domain)
    user = TableauUser.objects.filter(
        server=session.tableau_connected_app.server
    ).get(username=username)
    if role:
        for local_tableau_user in [user] + get_matching_tableau_users_from_other_domains(user):
            local_tableau_user.role = role
            local_tableau_user.save()

    # Group management
    allowed_groups_for_domain = get_allowed_tableau_groups_for_domain(domain)
    existing_groups = _group_json_to_tuples(session.get_groups_for_user_id(user.tableau_user_id))
    edited_groups_list = list(filter(lambda group: group.name in allowed_groups_for_domain, groups))
    other_groups = [group for group in existing_groups if group.name not in allowed_groups_for_domain]
    # The list of groups for the user should be a combination of those edited by the web admin and the existing
    # groups the user belongs to that are not editable on that domain.
    new_groups = edited_groups_list + other_groups

    _update_user_remote(session, user, groups=new_groups)


def _update_user_remote(session, user, groups=[]):
    new_id = session.update_user(user.tableau_user_id, role=user.role, username=tableau_username(user.username))
    for local_tableau_user in [user] + get_matching_tableau_users_from_other_domains(user):
        local_tableau_user.tableau_user_id = new_id
        local_tableau_user.save()
    # Add default group
    _add_user_to_HQ_group(session, user)
    for group in groups:
        session.add_user_to_group(user.tableau_user_id, group.id)


def _add_user_to_HQ_group(session, user):
    remote_HQ_group_id = _get_hq_group_id(session)
    if remote_HQ_group_id:
        session.add_user_to_group(user.tableau_user_id, remote_HQ_group_id)
    else:
        _notify_tableau_exception(
            f'HQ Group did not exist when trying to add user to it. Username: {user.username}.',
            user.server.domain)


def _get_hq_group_id(session):
    return session.get_group(HQ_TABLEAU_GROUP_NAME).get('id')


@periodic_task(run_every=crontab(minute=0, hour='*/1'), queue='background_queue')
def sync_all_tableau_users():
    domains_grouped_by_server = defaultdict(list)  # Looks like {(server name, tableau site): [domains]...}
    for domain in TABLEAU_USER_SYNCING.get_enabled_domains():
        server = TableauConnectedApp.get_server(domain)
        if not server:
            continue
        server_details = (server.server_name, server.target_site)
        domains_grouped_by_server[server_details].append(domain)
    for list_of_domains_for_server in domains_grouped_by_server.values():
        logger.info(f"Syncing Tableau users on domains: {list_of_domains_for_server}.")
        try:
            sync_tableau_users_on_domains(list_of_domains_for_server)
        except (TableauAPIError, TableauConnectedApp.DoesNotExist) as e:
            _notify_tableau_exception(e, domain)


def sync_tableau_users_on_domains(domains):
    def _sync_tableau_users_with_hq(session, domain):
        tableau_user_names = [tableau_user.username for tableau_user in TableauUser.objects.filter(
            server=TableauServer.objects.get(domain=domain)
        )]
        web_users_names = [web_user.username for web_user in WebUser.by_domain(domain)]
        # If there's a web user that isn't in the TableauUser model, create a new Tableau user
        for web_user_name in web_users_names:
            if web_user_name not in tableau_user_names:
                _add_tableau_user_local(session, web_user_name)
        # If there's a TableauUser with no corresponding WebUser, delete the Tableau user
        for tableau_user_name in tableau_user_names:
            if tableau_user_name not in web_users_names:
                _delete_user_local(session, tableau_user_name)

    def _sync_tableau_users_with_remote(session, domains):
        # Setup
        def _get_HQ_group_users(session):
            remote_HQ_group_id = _get_hq_group_id(session)
            if remote_HQ_group_id:
                remote_HQ_group_users = session.get_users_in_group(remote_HQ_group_id)
            else:
                session.create_group(HQ_TABLEAU_GROUP_NAME)
                remote_HQ_group_users = []
            return remote_HQ_group_users

        all_remote_users = {username.lower(): value for username, value in session.get_users_on_site().items()}
        all_local_users = TableauUser.objects.filter(server__domain__in=domains)
        distinct_local_users = all_local_users.distinct('username')
        remote_HQ_group_users = _get_HQ_group_users(session)

        # Add/delete/update remote users to match with local reality
        for local_user in distinct_local_users:
            local_tableau_username = tableau_username(local_user.username).lower()
            if local_tableau_username not in all_remote_users:
                _add_tableau_user_remote(session, local_user, local_user.role)
            elif local_user.tableau_user_id != all_remote_users[local_tableau_username]['id']:
                _delete_user_remote(session, all_remote_users[local_tableau_username]['id'])
                _add_tableau_user_remote(session, local_user)
            elif local_user.role != all_remote_users[local_tableau_username]['siteRole']:
                _update_user_remote(
                    session,
                    local_user,
                    groups=_group_json_to_tuples(session.get_groups_for_user_id(local_user.tableau_user_id))
                )

        # Remove any remote users that don't exist locally
        local_users_usernames = [tableau_username(user.username).lower() for user in distinct_local_users]
        for remote_user in remote_HQ_group_users:
            if remote_user['name'].lower() not in local_users_usernames:
                _delete_user_remote(session, remote_user['id'])

    for domain in domains:
        # Sync the web users on HQ with the TableauUser model
        _sync_tableau_users_with_hq(
            TableauAPISession.create_session_for_domain(domain),
            domain
        )

    # Sync the TableauUser model with Tableau users on the remote Tableau instance
    _sync_tableau_users_with_remote(
        TableauAPISession.create_session_for_domain(domains[0]),  # Can use a session for any of the domains
        domains
    )


def is_hq_user(tableau_username):
    return tableau_username and tableau_username.startswith('HQ/')


def tableau_username_to_hq(tableau_username):
    if is_hq_user(tableau_username):
        return tableau_username[3:]


# Attaches to the parse_web_users method, used for user export
def add_on_tableau_details(domain, web_user_dicts):

    session = TableauAPISession.create_session_for_domain(domain)

    def _get_roles_by_user(domain, usernames):
        return {
            user['username']: user['role'] for user in TableauUser.objects.filter(
                server=TableauServer.objects.get(domain=domain)
            ).filter(username__in=usernames).values('username', 'role')
        }

    def _get_groups_by_username(session, domain):
        try:
            groups_by_username = defaultdict(list)
            all_groups = get_all_tableau_groups(domain, session=session)
            for group in all_groups:
                for user_dict in session.get_users_in_group(group.id):
                    hq_username = tableau_username_to_hq(user_dict.get('name'))
                    if hq_username:
                        groups_by_username[hq_username].append(group.name)
            return groups_by_username
        except TableauAPIError:
            return None

    users_to_edit = []
    for web_user_dict in web_user_dicts:
        user = CouchUser.get_by_username(web_user_dict['username'], strict=True)
        # Make sure user already exists on domain (i.e. not an invited user)
        if user and user.get_domain_membership(domain):
            users_to_edit.append(user.username)

    roles_by_user = _get_roles_by_user(domain, users_to_edit)
    groups_by_username = _get_groups_by_username(session, domain)

    for web_user_dict in web_user_dicts:
        username = web_user_dict['username']
        if username not in users_to_edit:
            web_user_dict['tableau_role'] = 'N/A'
            web_user_dict['tableau_groups'] = 'N/A'
        else:
            web_user_dict['tableau_role'] = roles_by_user.get(username, 'ERROR')
            if groups_by_username is None:
                web_user_dict['tableau_groups'] = 'ERROR'
            else:
                web_user_dict['tableau_groups'] = ','.join(groups_by_username.get(username, ''))
    return web_user_dicts


# Attaches to the import_users method
def import_tableau_users(domain, web_user_specs):
    # Skip the Tableau users part of the import if one of the columns is missing
    if (not web_user_specs or web_user_specs[0].get('tableau_role') is None
    or web_user_specs[0].get('tableau_groups') is None):
        return
    session = TableauAPISession.create_session_for_domain(domain)
    known_groups = {}
    for row in web_user_specs:
        username = row.get('username')
        remove = spec_value_to_boolean_or_none(row, 'remove')
        user = CouchUser.get_by_username(username, strict=True)
        if user:
            if remove:
                delete_tableau_user(domain, username, session=session)
            elif user.get_domain_membership(domain):
                tableau_role = row.get('tableau_role')
                tableau_groups_txt = row.get('tableau_groups')
                BAD_VALUES = ['ERROR', 'N/A']
                if tableau_role in BAD_VALUES or tableau_groups_txt in BAD_VALUES:
                    continue

                def _get_tableau_group_tuples_from_names(names, known_groups):
                    groups = []
                    for group_name in names:
                        if group_name in known_groups:
                            groups.append(known_groups[group_name])
                        else:
                            try:
                                new_group = TableauGroupTuple(group_name,
                                    session.get_group(group_name)['id'])
                            except (TableauAPIError, KeyError) as e:
                                _notify_tableau_exception(e, domain)
                            else:
                                groups.append(new_group)
                                known_groups[group_name] = new_group
                    return groups, known_groups

                tableau_group_names = tableau_groups_txt.split(',')
                tableau_group_names = tableau_group_names if tableau_group_names[0] else []
                tableau_groups, known_groups = _get_tableau_group_tuples_from_names(tableau_group_names,
                                                                                    known_groups)

                update_tableau_user(domain, username, role=tableau_role, groups=tableau_groups, session=session)


def domain_copied_cases_by_owner(domain, owner_ids):
    """
    Returns all the cases on a domain belonging to a set of owners
    where the cases have the COMMCARE_CASE_COPY_PROPERTY_NAME case
    property.
    """
    from corehq.apps.hqcase.case_helper import CaseCopier
    return CaseSearchES()\
        .domain(domain)\
        .owner(owner_ids)\
        .NOT(case_property_missing(CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME))\
        .values_list('_id', flat=True)
