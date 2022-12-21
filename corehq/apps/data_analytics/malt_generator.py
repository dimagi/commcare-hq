import datetime
import logging
from collections import namedtuple

from django.db import IntegrityError
from django.http.response import Http404

from couchforms.analytics import get_last_form_submission_received
from dimagi.utils.chunked import chunked

from corehq.apps.app_manager.const import AMPLIFIES_NOT_SET
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.data_analytics.const import AMPLIFY_COUCH_TO_SQL_MAP, NOT_SET
from corehq.apps.data_analytics.esaccessors import (
    get_app_submission_breakdown_es,
)
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors import get_all_user_rows
from corehq.apps.users.models import CouchUser
from corehq.const import MISSING_APP_ID
from corehq.util.quickcache import quickcache

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_MINIMUM_USE_THRESHOLD = 15
DEFAULT_EXPERIENCED_THRESHOLD = 3

MaltAppData = namedtuple('MaltAppData', 'wam pam use_threshold experienced_threshold is_app_deleted')


def generate_malt(monthspans, domains=None):
    """
    Populates MALTRow SQL table with app submission data for a given list of months
    :param monthspans: list of DateSpan objects
    :param domains: list of domain names
    """
    domain_names = domains or Domain.get_all_names()
    for domain_name in domain_names:
        last_submission_date = get_last_form_submission_received(domain_name)
        last_malt_run_dates_by_month = _get_last_run_date_for_malt_by_month(domain_name, monthspans)
        for monthspan in monthspans:
            # if the MALTRow last_run_date is none, use the start date of the month
            last_malt_run_date = last_malt_run_dates_by_month.get(monthspan.startdate.date(), monthspan.startdate)
            if last_submission_date and last_submission_date >= last_malt_run_date:
                # use this date to populate last_run_date for all MALTRows with this domain and month
                run_date = datetime.datetime.utcnow()
                logger.info(f"Building MALT for {domain_name} for {monthspan} up to {run_date}")
                all_users = get_all_user_rows(domain_name, include_inactive=False, include_docs=True)
                for users in chunked(all_users, 1000):
                    users_by_id = {user['id']: CouchUser.wrap_correctly(user['doc']) for user in users}
                    malt_row_dicts = _get_malt_row_dicts(domain_name, monthspan, users_by_id, run_date)
                    if malt_row_dicts:
                        _save_malt_row_dicts_to_db(malt_row_dicts)


def _get_last_run_date_for_malt_by_month(domain_name, monthspans):
    """
    Return month and last_run_date values for MALTRows for this domain
    """
    return dict(MALTRow.objects.filter(
        domain_name=domain_name,
        month__in=[month.startdate for month in monthspans],
        last_run_date__isnull=False,
    ).values_list("month", "last_run_date"))


@quickcache(['domain', 'app_id'])
def _get_malt_app_data(domain, app_id):
    default_app_data = MaltAppData(
        AMPLIFIES_NOT_SET, AMPLIFIES_NOT_SET, DEFAULT_MINIMUM_USE_THRESHOLD, DEFAULT_EXPERIENCED_THRESHOLD, False
    )
    if not app_id:
        return default_app_data
    try:
        app = get_app(domain, app_id)
    except Http404:
        logger.debug("App not found %s" % app_id)
        return default_app_data

    return MaltAppData(getattr(app, 'amplifies_workers', AMPLIFIES_NOT_SET),
                       getattr(app, 'amplifies_project', AMPLIFIES_NOT_SET),
                       getattr(app, 'minimum_use_threshold', DEFAULT_MINIMUM_USE_THRESHOLD),
                       getattr(app, 'experienced_threshold', DEFAULT_EXPERIENCED_THRESHOLD),
                       app.is_deleted())


def _build_malt_row_dict(app_row, domain_name, user, monthspan, run_date):
    app_data = _get_malt_app_data(domain_name, app_row.app_id)

    return {
        'month': monthspan.startdate,
        'user_id': user._id,
        'username': user.username,
        'email': user.email,
        'user_type': user.doc_type,
        'domain_name': domain_name,
        'num_of_forms': app_row.doc_count,
        'app_id': app_row.app_id or MISSING_APP_ID,
        'device_id': app_row.device_id,
        'wam': AMPLIFY_COUCH_TO_SQL_MAP.get(app_data.wam, NOT_SET),
        'pam': AMPLIFY_COUCH_TO_SQL_MAP.get(app_data.pam, NOT_SET),
        'use_threshold': app_data.use_threshold,
        'experienced_threshold': app_data.experienced_threshold,
        'is_app_deleted': app_data.is_app_deleted,
        'last_run_date': run_date,
    }


def _get_malt_row_dicts(domain_name, monthspan, users_by_id, run_date):
    """
    Only processes domains that have had a form submission since the startdate of the month
    Includes expensive elasticsearch query
    :param domain_name: domain name
    :param monthspan: DateSpan of month to process
    :param users_by_id: list of dictionaries [{user_id: user_obj}, ...]
    """
    malt_row_dicts = []
    app_rows = get_app_submission_breakdown_es(domain_name, monthspan, list(users_by_id))
    for app_row in app_rows:
        user = users_by_id[app_row.user_id]
        malt_row_dict = _build_malt_row_dict(app_row, domain_name, user, monthspan, run_date)
        malt_row_dicts.append(malt_row_dict)

    return malt_row_dicts


def _save_malt_row_dicts_to_db(malt_row_dicts):
    try:
        MALTRow.objects.bulk_create(
            [MALTRow(**malt_dict) for malt_dict in malt_row_dicts]
        )
    except IntegrityError:
        for malt_row_dict in malt_row_dicts:
            _update_or_create_malt_row(malt_row_dict)


def _update_or_create_malt_row(malt_row_dict):
    unique_field_dict = {k: v for (k, v) in malt_row_dict.items() if k in MALTRow.get_unique_fields()}
    # use the unique_field_dict to specify key/value pairs to filter on
    MALTRow.objects.update_or_create(defaults=malt_row_dict, **unique_field_dict)
