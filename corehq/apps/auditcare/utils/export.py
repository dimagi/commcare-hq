import csv
from datetime import datetime, timedelta
from itertools import chain

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import ForeignKey

import attr
from couchdbkit.ext.django.loading import get_db

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.parsing import string_to_datetime

from corehq.apps.domain.utils import get_domain_from_url
from corehq.apps.users.models import WebUser, Invitation
from corehq.util.models import ForeignValue

from ..models import AccessAudit, NavigationEventAudit


def navigation_events_by_user(user, start_date=None, end_date=None):
    params = {"user": user, "start_date": start_date, "end_date": end_date}
    sql_start_date = determine_sql_start_date(start_date)
    where = get_date_range_where(sql_start_date, end_date)
    query = NavigationEventAudit.objects.filter(user=user, **where)
    return chain(
        iter_couch_audit_events(params),
        AuditWindowQuery(query),
    )


def write_log_events(writer, user, domain=None, override_user=None, start_date=None, end_date=None):
    start_date = string_to_datetime(start_date).replace(tzinfo=None) if start_date else None
    end_date = string_to_datetime(end_date).replace(tzinfo=None) if end_date else None

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
        removed_users = []
        super_users = []
    else:
        users = {u.username for u in WebUser.by_domain(domain)}
        super_users = {u['username'] for u in User.objects.filter(is_superuser=True).values('username')}
        users_who_accepted_invitations = set(Invitation.objects.filter(is_accepted=True, domain=domain).values_list('email', flat=True))
        removed_users = users_who_accepted_invitations - users
        super_users = super_users - users
    return users, removed_users, super_users


def get_all_log_events(start_date=None, end_date=None):
    params = {"start_date": start_date, "end_date": end_date}
    sql_start_date = determine_sql_start_date(start_date)
    where = get_date_range_where(sql_start_date, end_date)
    return chain(
        iter_couch_audit_events(params),
        AuditWindowQuery(AccessAudit.objects.filter(**where)),
        AuditWindowQuery(NavigationEventAudit.objects.filter(**where)),
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


def iter_couch_audit_events(params, chunksize=10000):
    if not (params.get("start_date") or params.get("user")):
        raise NotImplementedError("auditcare queries on Couch have not "
            "been designed for unbounded queries")
    if params.get("start_date"):
        sql_start = get_sql_start_date()
        if params["start_date"] > sql_start:
            return
    db = get_db("auditcare")
    if "user" in params:
        view_name = "auditcare/urlpath_by_user_date"
    else:
        view_name = "auditcare/all_events"
    startkey, endkey = _get_couch_view_keys(**params)
    doc_ids = {r["id"] for r in db.view(
        view_name,
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        include_docs=False,
    )}
    for doc in iter_docs(db, doc_ids, chunksize=chunksize):
        yield CouchAuditEvent(doc)


def get_fixed_start_date_for_sql():
    # reemove after auditcare migration is done
    return FIXED_START_DATES.get(settings.SERVER_ENVIRONMENT)


FIXED_START_DATES = {
    'production': datetime(2021, 3, 24, 6, 17, 21, 988840),
    'india': datetime(2021, 3, 23, 21, 52, 25, 476894),
    'staging': datetime(2021, 3, 20, 11, 50, 2, 921916),
    'swiss': datetime(2021, 3, 25, 8, 22, 53, 179334),
}


def determine_sql_start_date(start_date):
    fixed_start_date = get_fixed_start_date_for_sql()
    if fixed_start_date and start_date < fixed_start_date:
        return fixed_start_date
    else:
        return start_date


def get_sql_start_date():
    """Get the date of the first SQL auditcare record

    HACK this uses `NavigationEventAudit` since that model is likely to
    have the record with the earliest timestamp.

    NOTE this function assumes no SQL data has been archived, and that
    all auditcare data in Couch will be obsolete and/or archived before
    SQL data. It should be removed when the data in Couch is no longer
    relevant.

    NOTE the output is being hardcoded for the time historical auditcare events are copied to SQL
    """
    fixed_sql_start = get_fixed_start_date_for_sql()
    if fixed_sql_start:
        return fixed_sql_start
    manager = NavigationEventAudit.objects
    row = manager.order_by("event_date").values("event_date")[:1].first()
    return row["event_date"] if row else None


class CouchAuditEvent:
    def __init__(self, doc):
        self.__dict__ = doc

    def __repr__(self):
        return f"{type(self).__name__}({self.__dict__!r})"

    @property
    def domain(self):
        return get_domain_from_url(self.path)

    @property
    def event_date(self):
        datestr = self.__dict__["event_date"]
        return string_to_datetime(datestr).replace(tzinfo=None)

    @property
    def path(self):
        if self.doc_type == "NavigationEventAudit":
            return self.request_path
        return self.path_info


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
