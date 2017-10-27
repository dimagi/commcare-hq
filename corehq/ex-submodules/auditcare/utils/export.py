from django.utils.datastructures import OrderedSet

from auditcare.models import NavigationEventAudit
from dimagi.utils.couch.database import iter_docs


def navigation_event_ids_by_user(user):
    database = NavigationEventAudit.get_db()

    ids = OrderedSet()
    results = database.view(
        'auditcare/urlpath_by_user_date',
        startkey=[user],
        endkey=[user, {}],
        reduce=False,
        include_docs=False,
    )
    for row in results:
        ids.add(row['id'])
    return ids


def write_log_events(writer, user, domain=None, override_user=None):
    for event in iter_docs(NavigationEventAudit.get_db(), navigation_event_ids_by_user(user)):
        doc = NavigationEventAudit.wrap(event)
        if not domain or domain == doc.domain:
            write_log_event(writer, doc, override_user)


def write_log_event(writer, event, override_user=None):
    if override_user:
        event.user = override_user
    writer.writerow([event.event_date, event.user, event.domain, event.ip_address, event.request_path])
