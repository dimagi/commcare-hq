import csv
from datetime import timedelta
from itertools import chain

from django.contrib.auth.models import User
from django.db.models import ForeignKey, Min

import attr

from dimagi.utils.parsing import string_to_datetime

from corehq.apps.users.models import Invitation, WebUser
from corehq.util.models import ForeignValue

from ..models import AccessAudit, NavigationEventAudit


def navigation_events_by_user(user, start_date=None, end_date=None):
    where = get_date_range_where(start_date, end_date)
    query = NavigationEventAudit.objects.filter(user=user, **where)
    return AuditWindowQuery(query)


def write_log_events(writer, user, domain=None, override_user=None, start_date=None, end_date=None):
    for event in navigation_events_by_user(user, start_date, end_date):
        if not domain or domain == event.domain:
            write_log_event(writer, event, override_user)


def write_log_event(writer, event, override_user=None):
    if override_user:
        event.user = override_user
    writer.writerow([
        event.event_date,
        event.user,
        event.domain,
        event.ip_address,
        event.request_method,
        event.request_path
    ])


def get_users_for_domain(domain):
    users = {u.username for u in WebUser.by_domain(domain)}
    super_users = {u['username'] for u in User.objects.filter(is_superuser=True).values('username')}
    users_who_accepted_invitations = set(Invitation.objects.filter(
        is_accepted=True,
        domain=domain).values_list('email', flat=True)
    )
    removed_users = users_who_accepted_invitations - users
    super_users = super_users - users
    return users, removed_users, super_users


def get_all_log_events(start_date=None, end_date=None):
    where = get_date_range_where(start_date, end_date)
    return chain(
        AuditWindowQuery(AccessAudit.objects.filter(**where)),
        AuditWindowQuery(NavigationEventAudit.objects.filter(**where)),
    )


def get_domain_first_access_times(domains, start_date=None, end_date=None):
    """Query NavigationEventAudit events for _first event matching any of
    `domains` within each authenticated session_.

    NOTE: This function does _not_ query couch.

    NOTE: This function may return multiple "access events" from the same
          session (if multiple `domains` were accessed in the same session).

    Resulting SQL query:

    ```sql
    SELECT
        "user",
        domain,
        MIN(event_date) AS access_time
    FROM auditcare_navigationeventaudit
    WHERE (
        domain IN ( {domains} )
        AND event_date > {start_date}
        AND event_date <= {end_date}
        AND "user" IS NOT NULL
        AND session_key IS NOT NULL
    )
    GROUP BY ("user", domain, session_key)
    ORDER BY access_time ASC;
    ```
    """
    where = get_date_range_where(start_date, end_date)
    where["domain__in"] = domains
    where["user__isnull"] = False
    where["session_key__isnull"] = False
    return (NavigationEventAudit.objects
            .values("user", "domain", "session_key")  # GROUP BY fields
            .annotate(access_time=Min("event_date"))
            .values("user", "domain", "access_time")  # SELECT fields
            .filter(**where)
            .order_by("access_time")
            .iterator())


def write_generic_log_event(writer, event):
    action = ''
    resource = ''
    if event.doc_type == 'NavigationEventAudit':
        action = event.request_method
        resource = event.request_path
    else:
        assert event.doc_type == 'AccessAudit'
        action = event.access_type
        resource = event.path

    writer.writerow([
        event.event_date,
        event.doc_type,
        event.user,
        event.domain,
        event.ip_address,
        action,
        resource,
        event.description,
    ])


def write_export_from_all_log_events(file_obj, start, end):
    writer = csv.writer(file_obj)
    writer.writerow(['Date', 'Type', 'User', 'Domain', 'IP Address', 'Action', 'Resource', 'Description'])
    for event in get_all_log_events(start, end):
        write_generic_log_event(writer, event)


def get_date_range_where(start_date, end_date):
    """Get ORM filter kwargs for inclusive event_date range"""
    where = {}
    if start_date:
        start_date = string_to_datetime(start_date).replace(tzinfo=None)
        where["event_date__gt"] = start_date
    if end_date:
        end_date = string_to_datetime(end_date).replace(tzinfo=None)
        where["event_date__lt"] = end_date + timedelta(days=1)
    return where


@attr.s(cmp=False)
class AuditWindowQuery:
    query = attr.ib()
    window_size = attr.ib(default=10000)

    def __iter__(self):
        """Windowed query generator using WHERE/LIMIT

        Adapted from https://github.com/sqlalchemy/sqlalchemy/wiki/WindowedRangeQuery
        """
        query = self.query
        last_date = None
        last_ids = set()
        while True:
            qry = query
            if last_date is not None:
                qry = query.filter(event_date__gte=last_date).exclude(id__in=last_ids)
            rec = None
            for rec in qry.order_by("event_date")[:self.window_size]:
                yield NoForeignQuery(rec)
                if rec.event_date != last_date:
                    last_date = rec.event_date
                    last_ids = {rec.id}
                else:
                    last_ids.add(rec.id)
            if rec is None:
                break


def get_foreign_names(model):
    names = {f.name for f in model._meta.fields if isinstance(f, ForeignKey)}
    names.update(ForeignValue.get_names(model))
    return names


@attr.s
class NoForeignQuery:
    """Raise an error if a foreign key field is accessed

    This is a hack to prevent downstream code from accessing related
    objects, inadvertently triggering many extra queries.
    See also: https://stackoverflow.com/questions/66496443

    If a need arises for downstream code to access related fields,
    `navigation_events_by_user` should be updated to use
    `query.select_related` and/or `query.prefetch_related`, and this
    class should be refactored accordingly.
    """
    _obj = attr.ib()

    def __attrs_post_init__(self):
        self._fks = get_foreign_names(type(self._obj))

    def __getattr__(self, name):
        if name in self._fks:
            raise ForeignKeyAccessError(name)
        return getattr(self._obj, name)


class ForeignKeyAccessError(AttributeError):
    pass
