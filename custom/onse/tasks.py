import sys

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from time import sleep
from typing import Iterable, List, Optional, Tuple, Union
from urllib.error import HTTPError

import attr
from celery.schedules import crontab
from celery.task import periodic_task, task
from dateutil.relativedelta import relativedelta
from requests import RequestException

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from dimagi.utils.chunked import chunked

from corehq.apps.domain.dbaccessors import domain_exists
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.models import ConnectionSettings
from corehq.util.soft_assert import soft_assert
from custom.onse.const import (
    CASE_TYPE,
    CONNECTION_SETTINGS_NAME,
    DOMAIN,
    LAST_IMPORTED_PROPERTY,
    MAX_RETRY_ATTEMPTS,
    TASK_RETRY_FACTOR
)
from custom.onse.models import iter_mappings

# The production DHIS2 server is on the other side of an
# interoperability service that changes the URL schema from
# "base_url/api/resource" to "service/dhis2core/api/v0/resource".
# Its ConnectionSettings instance uses URL "service/dhis2core/api/v0/"
# Set ``DROP_API_PREFIX = True`` to drop the "/api" before "/resource",
# so that resource URLs end up as "service/dhis2core/api/v0/resource".
DROP_API_PREFIX = True
MAX_THREAD_WORKERS = 10

_soft_assert = soft_assert('@'.join(('nhooper', 'dimagi.com')))


@attr.s(auto_attribs=True)
class CassiusMarcellus:  # TODO: Come up with a better name. Please!
    """
    Stores a case, and its updates.

    Allows us to read current case property values and build a CaseBlock
    """
    case: Union[CommCareCase, CommCareCaseSQL]
    updates: dict = attr.Factory(dict)

    @property
    def case_block(self):
        return CaseBlock(
            case_id=self.case.case_id,
            external_id=self.case.external_id,
            case_type=CASE_TYPE,
            case_name=self.case.name,
            update=self.updates,
        )


@periodic_task(
    # Run on the 5th day of every quarter
    run_every=crontab(day_of_month=5, month_of_year='1,4,7,10',
                      hour=22, minute=30),
    queue='background_queue',
)
def update_facility_cases_from_dhis2_data_elements():
    _update_facility_cases_from_dhis2_data_elements.delay()


@task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def _update_facility_cases_from_dhis2_data_elements(self, period, print_notifications):
    if not domain_exists(DOMAIN):
        return
    dhis2_server = get_dhis2_server(print_notifications)
    server_status = check_server_status(dhis2_server)

    if server_status['ready']:
        execute_update_facility_cases_from_dhis2_data_elements(dhis2_server, period, print_notifications)
    else:
        exception = server_status['error']
        retry_days = 2 ** self.request.retries

        message = f'Importing {DOMAIN.upper()} cases from {CONNECTION_SETTINGS_NAME} failed: {exception}. ' \
                  f'Retrying in {retry_days} days'
        _notify_message(print_notifications, message, dhis2_server, exception)

        self.retry(countdown=(retry_days * TASK_RETRY_FACTOR))


def check_server_status(dhis2_server: ConnectionSettings):
    server_status = {
        'ready': True,
        'error': None
    }
    requests = dhis2_server.get_requests()
    try:
        requests.send_request_unlogged("HEAD", dhis2_server.url, raise_for_status=True)
    except HTTPError as e:
        if e.response.status_code != 405:  # ignore method not allowed
            server_status['ready'] = False
            server_status['error'] = e
    except RequestException as re:
        server_status['ready'] = False
        server_status['error'] = re

    return server_status


def execute_update_facility_cases_from_dhis2_data_elements(
    dhis2_server: ConnectionSettings,
    period: Optional[str] = None,
    print_notifications: bool = False,
):
    """
    Update facility_supervision cases with indicators collected in DHIS2
    over the last quarter.

    :param dhis2_server: The ConnectionSettings instance to connect to
        the remote API.
    :param period: The period of data to import. e.g. "2020Q1". Defaults
        to last quarter.
    :param print_notifications: If True, notifications are printed,
        otherwise they are emailed.

    """
    try:
        clays = get_clays()
        with ThreadPoolExecutor(max_workers=MAX_THREAD_WORKERS) as executor:
            futures = (executor.submit(set_case_updates,
                                       dhis2_server, clay, period)
                       for clay in clays)
            for futures_chunk in chunked(as_completed(futures), 100):
                case_blocks_chunk = [f.result() for f in futures_chunk]
                save_cases(case_blocks_chunk)
    except Exception as err:
        handle_error(err, dhis2_server, print_notifications)
    else:
        handle_success(dhis2_server, print_notifications)


def get_dhis2_server(
    print_notifications: bool = False
) -> ConnectionSettings:
    try:
        return ConnectionSettings.objects.get(domain=DOMAIN,
                                              name=CONNECTION_SETTINGS_NAME)
    except ConnectionSettings.DoesNotExist:
        message = (f'ConnectionSettings {CONNECTION_SETTINGS_NAME!r} not '
                   f'found in domain {DOMAIN!r} for importing DHIS2 data '
                   f'elements.')
        if print_notifications:
            print(message, file=sys.stderr)
        else:
            _soft_assert(False, message)
        raise


def get_clays() -> Iterable[CassiusMarcellus]:
    case_accessors = CaseAccessors(DOMAIN)
    for case_id in case_accessors.get_case_ids_in_domain(type=CASE_TYPE):
        case = case_accessors.get_case(case_id)
        if not case.external_id:
            # This case is not mapped to a facility in DHIS2.
            continue
        yield CassiusMarcellus(case)


def set_case_updates(
    dhis2_server: ConnectionSettings,
    clay: CassiusMarcellus,
    requested_period: Optional[str],
) -> CassiusMarcellus:
    """
    Fetch data sets of data elements for last quarter from ``dhis2_server``
    and update the data elements corresponding case properties in
    ``case_block`` in place.
    """
    last_imported = clay.case.get_case_property(LAST_IMPORTED_PROPERTY)
    if last_imported:
        last_imported = datetime.strptime(last_imported, '%Y-%m-%d').date()
    # Several of the data elements we want belong to the same data
    # sets. Only fetch a data set if we don't already have it.
    data_set_cache = {}
    for mapping in iter_mappings():
        if not mapping.data_set_id:
            raise ValueError(
                f'Mapping {mapping} does not include data set ID. '
                'Use **fetch_onse_data_set_ids** command.')
        for period in get_periods(requested_period, last_imported):
            data_set_cache.setdefault(period, {})
            if mapping.data_set_id not in data_set_cache[period]:
                data_set_cache[period][mapping.data_set_id] = fetch_data_set(
                    dhis2_server,
                    mapping.data_set_id,
                    # facility case external_id is set to its DHIS2 org
                    # unit. This is the DHIS2 facility whose data we
                    # want to import.
                    org_unit_id=clay.case.external_id,
                    period=period,
                )
            data_values = data_set_cache[period][mapping.data_set_id]

            if data_values is None:
                continue  # No data for this facility. Try previous quarter
            found, total = get_data_element_total(
                mapping.data_element_id,
                data_values,
            )
            if found:
                clay.updates[mapping.case_property] = total
                break
            # else: look for values in previous quarter
    clay.updates[LAST_IMPORTED_PROPERTY] = date.today().isoformat()
    return clay


def get_periods(
    requested_period: Optional[str],
    last_imported: Optional[date],
) -> Iterable[str]:
    if requested_period:
        return [requested_period]
    if last_imported:
        return previous_quarters_up_to(last_imported)
    return previous_quarters_up_to(five_years_ago())


def previous_quarters_up_to(some_date: date) -> Iterable[str]:
    """
    Returns quarters in DHIS2 web API `period format`_ in reverse
    chronological order.

    .. _period format: https://docs.dhis2.org/master/en/developer/html/webapi_date_perid_format.html
    """
    current_date = datetime.utcnow().date()
    while current_date > some_date:
        yield previous_quarter(current_date)
        current_date -= relativedelta(months=3)


def five_years_ago():
    """
    Returns the date five years ago today.
    """
    return datetime.utcnow().date() - relativedelta(years=5)


def fetch_data_set(
    dhis2_server: ConnectionSettings,
    data_set_id: str,
    org_unit_id: str,
    period: str,
) -> Optional[List[dict]]:
    """
    Returns a list of `DHIS2 data values`_, or ``None`` if the the given
    org unit has no data collected for the last quarter.

    Raises exceptions on connection timeout or non-200 response status.


    .. _DHIS2 data values: https://docs.dhis2.org/master/en/developer/html/webapi_data_values.html

    """
    max_attempts = 3
    backoff_seconds = 3 * 60

    requests = dhis2_server.get_requests()
    endpoint = '/dataValueSets' if DROP_API_PREFIX else '/api/dataValueSets'
    params = {
        'period': period,
        'dataSet': data_set_id,
        'orgUnit': org_unit_id,
    }
    attempt = 0
    while True:
        attempt += 1
        try:
            response = requests.get(endpoint, params, raise_for_status=True)
        except (RequestException, HTTPError):
            if attempt < max_attempts:
                sleep(backoff_seconds * attempt)
            else:
                raise
        else:
            break
    return response.json().get('dataValues', None)


def previous_quarter(some_date: date) -> str:
    """
    Returns the previous quarter in DHIS2 web API `period format`_.
    e.g. "2004Q1"

    .. _period format: https://docs.dhis2.org/master/en/developer/html/webapi_date_perid_format.html
    """
    year = some_date.year
    quarter = (some_date.month - 1) // 3
    if quarter == 0:
        year -= 1
        quarter = 4
    return f"{year}Q{quarter}"


def get_data_element_total(
    data_element_id: str,
    data_values: List[dict],
) -> Tuple[bool, int]:
    """
    A DHIS2 data element may be broken down by category options, and
    ``data_values`` can contain multiple entries for the same data
    element. This function returns whether ``data_element_id`` is found
    in ``data_values``, and its total.

    The following doctest shows an example value for ``data_values`` as
    might be returned by DHIS2:

    >>> data_values = [
    ...     {
    ...         "dataElement": "f7n9E0hX8qk",
    ...         "period": "2014Q1",
    ...         "orgUnit": "DiszpKrYNg8",
    ...         "categoryOption": "FNnj3jKGS7i",
    ...         "value": "12"
    ...     },
    ...     {
    ...         "dataElement": "f7n9E0hX8qk",
    ...         "period": "2014Q1",
    ...         "orgUnit": "DiszpKrYNg8",
    ...         "categoryOption": "Jkhdsf8sdf4",
    ...         "value": "16"
    ...     }
    ... ]
    >>> get_data_element_total('f7n9E0hX8qk', data_values)
    (True, 28)

    """
    found = False
    value = 0
    for data_value in data_values:
        if data_value['dataElement'] == data_element_id:
            found = True
            value += int(data_value['value'])
    return found, value


def save_cases(clays: List[CassiusMarcellus]):
    today = date.today().isoformat()
    submit_case_blocks(
        [clay.case_block.as_text() for clay in clays],
        DOMAIN,
        xmlns='http://commcarehq.org/dhis2-import',
        device_id=f"dhis2-import-{DOMAIN}-{today}",
    )


def handle_error(
    err: Exception,
    dhis2_server: ConnectionSettings,
    print_notifications: bool,
):
    message = f'Importing {DOMAIN.upper()} cases from {CONNECTION_SETTINGS_NAME} failed: {err}'
    _notify_message(print_notifications, message, dhis2_server, err)


def handle_success(
    dhis2_server: ConnectionSettings,
    print_notifications: bool,
):
    message = f'Successfully imported {DOMAIN.upper()} cases from {CONNECTION_SETTINGS_NAME}'
    _notify_message(print_notifications, message, dhis2_server)


def _notify_message(print_notifications, message, connection_settings, exception=None):
    if print_notifications:
        print(message, file=sys.stderr)
    else:
        if exception is not None:
            connection_settings.get_requests().notify_exception(message)
            raise exception
        else:
            # For most things we pass silently. But we can repurpose
            # `notify_error()` to tell admins that the import went through,
            # because it only happens once a quarter.
            connection_settings.get_requests().notify_error(message)
