import csv
from datetime import timedelta
from itertools import chain

import attr
from couchdbkit.ext.django.loading import get_db
from django.contrib.auth.models import User
from django.db.models import ForeignKey

from corehq.apps.users.models import WebUser
from corehq.util.models import ForeignValue

from ..models import AccessAudit, NavigationEventAudit


def navigation_events_by_user(user, start_date=None, end_date=None):
    params = {"user": user, "start_date": start_date, "end_date": end_date}
    where = get_date_range_where(start_date, end_date)
    query = NavigationEventAudit.objects.filter(user=user, **where)
    return AuditWindowQuery(query, params)


def write_log_events(writer, user, domain=None, override_user=None, start_date=None, end_date=None):
    for event in navigation_events_by_user(user, start_date, end_date):
        if not domain or domain == event.domain:
            write_log_event(writer, event, override_user)


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
    params = {"start_date": start_date, "end_date": end_date}
    where = get_date_range_where(start_date, end_date)
    return chain(
        AuditWindowQuery(AccessAudit.objects.filter(**where), params),
        AuditWindowQuery(NavigationEventAudit.objects.filter(**where), params),
    )


def write_generic_log_event(writer, event):
    action = ''
    resource = ''
    if event.doc_type == 'NavigationEventAudit':
        action = event.headers['REQUEST_METHOD']
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
        where["event_date__gt"] = start_date.date()
    if end_date:
        where["event_date__lt"] = end_date.date() + timedelta(days=1)
    return where


@attr.s(cmp=False)
class AuditWindowQuery:
    query = attr.ib()
    params = attr.ib()
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

    def count(self):
        return self.query.count() + self.couch_count()

    def couch_count(self):
        db = get_db("auditcare")
        if "user" in self.params:
            view_name = "auditcare/urlpath_by_user_date"
        else:
            view_name = "auditcare/all_events"
            raise NotImplementedError("not yet used")
        startkey, endkey = _get_couch_view_keys(**self.params)
        return db.view(
            view_name,
            startkey=startkey,
            endkey=endkey,
            reduce=False,
            include_docs=False,
        ).count()


def _get_couch_view_keys(user=None, start_date=None, end_date=None):
    def date_key(date):
        return [date.year, date.month, date.day]

    startkey = [user] if user else []
    if start_date:
        startkey.extend(date_key(start_date))

    endkey = [user] if user else []
    if end_date:
        end = end_date + timedelta(days=1)
        endkey.extend(date_key(end))
    else:
        endkey.append({})

    return startkey, endkey


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
