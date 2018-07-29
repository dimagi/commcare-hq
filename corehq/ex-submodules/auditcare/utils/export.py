from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils.datastructures import OrderedSet

from auditcare.models import NavigationEventAudit
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
