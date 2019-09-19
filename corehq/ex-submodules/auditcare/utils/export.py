from datetime import timedelta

from django.contrib.auth.models import User
from django.utils.datastructures import OrderedSet

from auditcare.models import NavigationEventAudit, wrap_audit_event
from corehq.apps.users.models import WebUser
from dimagi.utils.couch.database import iter_docs


def navigation_event_ids_by_user(user, start_date=None, end_date=None):
    database = NavigationEventAudit.get_db()

    def _date_key(date):
        return [date.year, date.month, date.day]

    startkey = [user]
    if start_date:
        startkey.extend(_date_key(start_date))

    endkey = [user]
    if end_date:
        end = end_date + timedelta(days=1)
        endkey.extend(_date_key(end))
    else:
        endkey.append({})

    ids = OrderedSet()
    results = database.view(
        'auditcare/urlpath_by_user_date',
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        include_docs=False,
    )
    for row in results:
        ids.add(row['id'])
    return ids


def write_log_events(writer, user, domain=None, override_user=None, start_date=None, end_date=None):
    event_ids = navigation_event_ids_by_user(user, start_date, end_date)
    for event in iter_docs(NavigationEventAudit.get_db(), event_ids):
        doc = NavigationEventAudit.wrap(event)
        if not domain or domain == doc.domain:
            write_log_event(writer, doc, override_user)


def write_log_event(writer, event, override_user=None):
    if override_user:
        event.user = override_user
    writer.writerow([event.event_date, event.user, event.domain, event.ip_address, event.request_path])


def get_users_to_export(username, domain):
    if username:
        users = [username]
        super_users = []
    else:
        users = {u.username for u in WebUser.by_domain(domain)}
        super_users = {u['username'] for u in User.objects.filter(is_superuser=True).values('username')}
        super_users = super_users - users

    return users, super_users


def get_all_log_events(start_date=None, end_date=None):
    def _date_key(date):
        return [date.year, date.month, date.day]

    startkey = []
    if start_date:
        startkey.extend(_date_key(start_date))

    endkey = []
    if end_date:
        end = end_date + timedelta(days=1)
        endkey.extend(_date_key(end))
    else:
        endkey.append({})

    results = NavigationEventAudit.get_db().view(
        'auditcare/all_events',
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        include_docs=True,
    )
    for row in results:
        yield wrap_audit_event(row['doc'])


def write_generic_log_event(writer, event):
    action = ''
    resource = ''
    if event.doc_type == 'NavigationEventAudit':
        action = event.headers['REQUEST_METHOD']
        resource = event.request_path
    elif event.doc_type == 'AccessAudit':
        action = event.access_type
        resource = event.path_info
    elif event.doc_type == 'ModelActionAudit':
        resource = f'{event.object_type}:{event.object_uuid}'

    writer.writerow([
        event.event_date, event.doc_type, event.user, getattr(event, 'domain', ''),
        getattr(event, 'ip_address', ''), action, resource, event.description
    ])
