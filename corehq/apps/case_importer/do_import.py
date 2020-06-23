import time
import uuid
from collections import Counter, defaultdict, namedtuple

from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from couchdbkit import NoResultFound

from casexml.apps.case.const import CASE_TAG_DATE_OPENED
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from corehq.apps.receiverwrapper.rate_limiter import rate_limit_submission
from corehq.util.timer import TimingContext
from couchexport.export import SCALAR_NEVER_WAS
from dimagi.utils.logging import notify_exception
from soil.progress import TaskProgressManager

from corehq.apps.case_importer.exceptions import CaseRowError
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.toggles import BULK_UPLOAD_DATE_OPENED
from corehq.util.metrics.load_counters import case_load_counter
from corehq.util.soft_assert import soft_assert
from corehq.util.metrics import metrics_counter, metrics_histogram

from . import exceptions
from .const import LookupErrors
from .util import EXTERNAL_ID, RESERVED_FIELDS, lookup_case

CASEBLOCK_CHUNKSIZE = 100
RowAndCase = namedtuple('RowAndCase', ['row', 'case'])
ALL_LOCATIONS = 'ALL_LOCATIONS'


def do_import(spreadsheet, config, domain, task=None, record_form_callback=None):
    importer = _TimedAndThrottledImporter(domain, config, task, record_form_callback)
    return importer.do_import(spreadsheet)


class _Importer(object):
    def __init__(self, domain, config, task, record_form_callback):
        self.domain = domain
        self.config = config
        self.task = task
        self.record_form_callback = record_form_callback

        self.results = _ImportResults()

        self.owner_accessor = _OwnerAccessor(domain, self.user)
        self.uncreated_external_ids = set()
        self._unsubmitted_caseblocks = []

    def do_import(self, spreadsheet):
        with TaskProgressManager(self.task, src="case_importer") as progress_manager:
            for row_num, row in enumerate(spreadsheet.iter_row_dicts(), start=1):
                progress_manager.set_progress(row_num - 1, spreadsheet.max_row)
                if row_num == 1:
                    continue  # skip first row (header row)

                try:
                    self.import_row(row_num, row)
                except exceptions.CaseRowError as error:
                    self.results.add_error(row_num, error)

            self.commit_caseblocks()
            return self.results.to_json()

    def import_row(self, row_num, raw_row):
        search_id = _parse_search_id(self.config, raw_row)
        fields_to_update = _populate_updated_fields(self.config, raw_row)
        if not any(fields_to_update.values()):
            # if the row was blank, just skip it, no errors
            return

        row = _CaseImportRow(
            search_id=search_id,
            fields_to_update=fields_to_update,
            config=self.config,
            domain=self.domain,
            user_id=self.user.user_id,
            owner_accessor=self.owner_accessor,
        )
        if row.relies_on_uncreated_case(self.uncreated_external_ids):
            self.commit_caseblocks()
        if row.is_new_case and not self.config.create_new_cases:
            return

        try:
            if row.is_new_case:
                if row.external_id:
                    self.uncreated_external_ids.add(row.external_id)
                caseblock = row.get_create_caseblock()
                self.results.add_created(row_num)
            else:
                caseblock = row.get_update_caseblock()
                self.results.add_updated(row_num)
        except CaseBlockError:
            raise exceptions.CaseGeneration()

        self.add_caseblock(RowAndCase(row_num, caseblock))

    @cached_property
    def user(self):
        return CouchUser.get_by_user_id(self.config.couch_user_id)

    def add_caseblock(self, caseblock):
        self._unsubmitted_caseblocks.append(caseblock)
        # check if we've reached a reasonable chunksize and if so, submit
        if len(self._unsubmitted_caseblocks) >= CASEBLOCK_CHUNKSIZE:
            self.commit_caseblocks()

    def commit_caseblocks(self):
        if self._unsubmitted_caseblocks:
            self.submit_and_process_caseblocks(self._unsubmitted_caseblocks)
            self.results.num_chunks += 1
            self._unsubmitted_caseblocks = []
            self.uncreated_external_ids = set()

    def submit_and_process_caseblocks(self, caseblocks):
        if not caseblocks:
            return
        self.pre_submit_hook()
        try:
            form, cases = self.submit_case_blocks(caseblocks)
            if form.is_error:
                raise Exception("Form error during case import: {}".format(form.problem))
        except Exception:
            notify_exception(None, "Case Importer: Uncaught failure submitting caseblocks")
            for row_number, case in caseblocks:
                self.results.add_error(row_number, exceptions.ImportErrorMessage())
        else:
            if self.record_form_callback:
                self.record_form_callback(form.form_id)
            properties = {p for c in cases for p in c.dynamic_case_properties().keys()}
            if self.config.case_type and len(properties):
                add_inferred_export_properties.delay(
                    'CaseImporter',
                    self.domain,
                    self.config.case_type,
                    properties,
                )
            else:
                _soft_assert = soft_assert(notify_admins=True)
                _soft_assert(
                    len(properties) == 0,
                    'error adding inferred export properties in domain '
                    '({}): {}'.format(self.domain, ", ".join(properties))
                )

    def pre_submit_hook(self):
        pass

    def submit_case_blocks(self, caseblocks):
        return submit_case_blocks(
            [cb.case.as_text() for cb in caseblocks],
            self.domain,
            self.user.username,
            self.user.user_id,
            device_id=__name__ + ".do_import",
        )


class _TimedAndThrottledImporter(_Importer):
    def __init__(self, domain, config, task, record_form_callback):
        super().__init__(domain, config, task, record_form_callback)

        self._last_submission_duration = 1  # duration in seconds; start with a value of 1s
        self._total_delayed_duration = 0  # sum of all rate limiter delays, in seconds

    def do_import(self, spreadsheet):
        with TimingContext() as timer:
            results = super().do_import(spreadsheet)
        try:
            self._report_import_timings(timer, results)
        except Exception:
            notify_exception(None, "Error reporting case import timings")
        finally:
            return results

    def _report_import_timings(self, timer, results):
        active_duration = timer.duration - self._total_delayed_duration
        rows_created = results['created_count']
        rows_updated = results['match_count']
        rows_failed = results['failed_count']

        # Add 1 to smooth / prevent denominator from ever being zero
        active_duration_per_case = active_duration / (rows_created + rows_updated + rows_failed + 1)
        metrics_histogram(
            'commcare.case_importer.duration_per_case', active_duration_per_case,
            buckets=[50, 70, 100, 150, 250, 350, 500], bucket_tag='duration', bucket_unit='ms',
        )

        for rows, status in ((rows_created, 'created'),
                             (rows_updated, 'updated'),
                             (rows_failed, 'error')):
            metrics_counter('commcare.case_importer.cases', rows, tags={
                'status': status,
            })

    def pre_submit_hook(self):
        if rate_limit_submission(self.domain):
            # the duration of the last submission is a combined heuristic
            # for the amount of load on the databases
            # and the amount of load that the requests from this import put on the databases.
            # The amount of time to wait, during a high submission period
            # and while this project is using up more than its fair share
            # should be proportional to this heuristic.
            # For a fully throttled domain, this will up to double
            # the amount of time the case import takes
            metrics_histogram(
                'commcare.case_importer.import_delays', self._last_submission_duration,
                buckets=[5, 7, 10, 15, 25, 35, 50], bucket_tag='duration', bucket_unit='s',
                tags={'domain': self.domain}
            )
            self._total_delayed_duration += self._last_submission_duration
            time.sleep(self._last_submission_duration)

    def submit_case_blocks(self, caseblocks):
        timer = None
        try:
            with TimingContext() as timer:
                return super().submit_case_blocks(caseblocks)
        finally:
            if timer:
                self._last_submission_duration = timer.duration


class _CaseImportRow(object):
    def __init__(self, search_id, fields_to_update, config, domain, user_id, owner_accessor):
        self.search_id = search_id
        self.fields_to_update = fields_to_update
        self.config = config
        self.domain = domain
        self.user_id = user_id
        self.owner_accessor = owner_accessor

        self.case_name = fields_to_update.pop('name', None)
        self.external_id = fields_to_update.pop('external_id', None)
        self.check_valid_external_id()
        self.parent_id = fields_to_update.pop('parent_id', None)
        self.parent_external_id = fields_to_update.pop('parent_external_id', None)
        self.parent_type = fields_to_update.pop('parent_type', self.config.case_type)
        self.parent_ref = fields_to_update.pop('parent_ref', 'parent')
        self.to_close = fields_to_update.pop('close', False)
        self.uploaded_owner_name = fields_to_update.pop('owner_name', None)
        self.uploaded_owner_id = fields_to_update.pop('owner_id', None)
        self.date_opened = fields_to_update.pop(CASE_TAG_DATE_OPENED, None)

    def check_valid_external_id(self):
        if self.config.search_field == 'external_id' and not self.search_id:
            # do not allow blank external id since we save this
            raise exceptions.BlankExternalId()

    def relies_on_uncreated_case(self, uncreated_external_ids):
        return any(lookup_id and lookup_id in uncreated_external_ids
                   for lookup_id in [self.search_id, self.parent_id, self.parent_external_id])

    @cached_property
    def existing_case(self):
        case, error = lookup_case(
            self.config.search_field,
            self.search_id,
            self.domain,
            self.config.case_type
        )
        _log_case_lookup(self.domain)
        if error == LookupErrors.MultipleResults:
            raise exceptions.TooManyMatches()
        return case

    @property
    def is_new_case(self):
        return not self.existing_case

    def _get_owner_id(self):
        if self.uploaded_owner_name:
            return self.owner_accessor.get_id_from_name(self.uploaded_owner_name)
        else:
            owner_id = self.uploaded_owner_id
            if owner_id:
                self.owner_accessor.check_owner_id(owner_id)
            # if they didn't supply an owner, default to current user
            return owner_id or self.user_id

    def _get_parent_index(self):
        for column, search_field, search_id in [
                ('parent_id', 'case_id', self.parent_id),
                ('parent_external_id', 'external_id', self.parent_external_id),
        ]:
            if search_id:
                parent_case, error = lookup_case(
                    search_field, search_id, self.domain, self.parent_type)
                _log_case_lookup(self.domain)
                if parent_case:
                    return {self.parent_ref: (parent_case.type, parent_case.case_id)}
                raise exceptions.InvalidParentId(column)

    def _get_date_opened(self):
        if self.date_opened and BULK_UPLOAD_DATE_OPENED.enabled(self.domain):
            return self.date_opened

    def _get_external_id(self):
        if self.is_new_case and self.config.search_field == 'external_id':
            return self.search_id
        return self.external_id

    def _get_caseblock_kwargs(self):
        return {
            'update': self.fields_to_update,
            'index': self._get_parent_index(),
            'date_opened': self._get_date_opened() or CaseBlock.undefined,
            'external_id': self._get_external_id() or CaseBlock.undefined,
        }

    def get_create_caseblock(self):
        return CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=self._get_owner_id(),
            user_id=self.user_id,
            case_type=self.config.case_type,
            case_name=self.case_name or '',
            **self._get_caseblock_kwargs()
        )

    def get_update_caseblock(self):
        extras = self._get_caseblock_kwargs()
        if self.uploaded_owner_id or self.uploaded_owner_name:
            extras['owner_id'] = self._get_owner_id()
        if self.case_name is not None:
            extras['case_name'] = self.case_name
        return CaseBlock(
            create=False,
            case_id=self.existing_case.case_id,
            close=self.to_close == 'yes',
            **extras
        )


def _log_case_lookup(domain):
    case_load_counter("case_importer", domain)


def _convert_custom_fields_to_struct(config):
    excel_fields = config.excel_fields
    case_fields = config.case_fields
    custom_fields = config.custom_fields

    field_map = {}
    for i, field in enumerate(excel_fields):
        if field:
            field_map[field] = {}

            if case_fields[i]:
                field_map[field]['field_name'] = case_fields[i]
            elif custom_fields[i]:
                # if we have configured this field for external_id populate external_id instead
                # of the default property name from the column
                if config.search_field == EXTERNAL_ID and field == config.search_column:
                    field_map[field]['field_name'] = EXTERNAL_ID
                else:
                    field_map[field]['field_name'] = custom_fields[i]
    # hack: make sure the external_id column ends up in the field_map if the user
    # didn't explicitly put it there
    if config.search_column not in field_map and config.search_field == EXTERNAL_ID:
        field_map[config.search_column] = {
            'field_name': EXTERNAL_ID
        }
    return field_map


class _ImportResults(object):
    CREATED = 'created'
    UPDATED = 'updated'
    FAILED = 'failed'

    def __init__(self):
        self._results = {}
        self._errors = defaultdict(dict)
        self.num_chunks = 0

    def add_error(self, row_num, error):
        self._results[row_num] = self.FAILED

        key = error.title
        column_name = error.column_name
        self._errors[key].setdefault(column_name, {})
        self._errors[key][column_name]['error'] = _(error.title)

        try:
            self._errors[key][column_name]['description'] = error.message
        except KeyError:
            self._errors[key][column_name]['description'] = exceptions.CaseGeneration.message

        if 'rows' not in self._errors[key][column_name]:
            self._errors[key][column_name]['rows'] = []

        self._errors[key][column_name]['rows'].append(row_num)

    def add_created(self, row_num):
        self._results[row_num] = self.CREATED

    def add_updated(self, row_num):
        self._results[row_num] = self.UPDATED

    def to_json(self):
        counts = Counter(self._results.values())
        return {
            'created_count': counts.get(self.CREATED, 0),
            'match_count': counts.get(self.UPDATED, 0),
            'failed_count': counts.get(self.FAILED, 0),
            'errors': dict(self._errors),
            'num_chunks': self.num_chunks,
        }


def _convert_field_value(value):
    # coerce to string unless it's a unicode string then we want that
    return value if isinstance(value, str) else str(value)


def _parse_search_id(config, row):
    """ Find and convert the search id in an Excel row """

    # Find index of user specified search column
    search_column = config.search_column
    search_id = row[search_column] or ''

    try:
        # if the spreadsheet gives a number, strip any decimals off
        # float(x) is more lenient in conversion from string so both
        # are used
        search_id = int(float(search_id))
    except (ValueError, TypeError, OverflowError):
        # if it's not a number that's okay too
        pass

    return _convert_field_value(search_id)


def _populate_updated_fields(config, row):
    """
    Returns a dict map of fields that were marked to be updated
    due to the import. This can be then used to pass to the CaseBlock
    to trigger updates.
    """
    field_map = _convert_custom_fields_to_struct(config)
    fields_to_update = {}
    for key in field_map:
        try:
            update_value = row[key]
        except Exception:
            continue

        if 'field_name' in field_map[key]:
            update_field_name = field_map[key]['field_name'].strip()
        else:
            # nothing was selected so don't add this value
            continue

        if update_field_name in RESERVED_FIELDS:
            raise exceptions.InvalidCustomFieldNameException(
                _('Field name "{}" is reserved').format(update_field_name))

        if isinstance(update_value, str) and update_value.strip() == SCALAR_NEVER_WAS:
            # If we find any instances of blanks ('---'), convert them to an
            # actual blank value without performing any data type validation.
            # This is to be consistent with how the case export works.
            update_value = ''
        elif update_value is not None:
            update_value = _convert_field_value(update_value)

        fields_to_update[update_field_name] = update_value

    return fields_to_update


class _OwnerAccessor(object):
    def __init__(self, domain, user):
        self.domain = domain
        self.user = user
        self.id_cache = {}
        self.name_cache = {}

    def get_id_from_name(self, name):
        return cached_function_call(self._get_id_from_name, name, self.name_cache)

    def _get_id_from_name(self, name):
        '''
        :param name: A username, group name, or location name/site_code
        :return: Looks for the given name and returns the corresponding id if the
        user or group exists and None otherwise. Searches for user first, then
        group, then location
        '''

        def get_user(name):
            try:
                name_as_address = name
                if '@' not in name_as_address:
                    name_as_address = format_username(name, self.domain)
                return CouchUser.get_by_username(name_as_address)
            except NoResultFound:
                return None

        def get_group(name):
            return Group.by_name(self.domain, name, one=True)

        def get_location(name):
            try:
                return SQLLocation.objects.get_from_user_input(self.domain, name)
            except SQLLocation.DoesNotExist:
                return None
            except SQLLocation.MultipleObjectsReturned:
                raise exceptions.DuplicateLocationName()

        owner = get_user(name) or get_group(name) or get_location(name)
        if not owner:
            raise exceptions.InvalidOwnerName('owner_name')
        self._check_owner(owner, 'owner_name')
        return owner._id

    def check_owner_id(self, owner_id):
        return cached_function_call(self._check_owner_id, owner_id, self.id_cache)

    def _check_owner_id(self, owner_id):
        """
        Raises InvalidOwner if the owner cannot own cases.
        Raises InvalidLocation if a location-restricted user tries to assign
            an owner outside their location hierarchy.
        Returns True if owner ID is valid.
        """
        owner = get_wrapped_owner(owner_id)
        self._check_owner(owner, 'owner_id')

    def _check_owner(self, owner, owner_field):
        is_valid_user = isinstance(owner, CouchUser) and owner.is_member_of(self.domain)
        is_valid_group = isinstance(owner, Group) and owner.case_sharing and owner.is_member_of(self.domain)
        is_valid_location = (isinstance(owner, SQLLocation)
                             and owner.domain == self.domain
                             and owner.location_type.shares_cases)
        if not (is_valid_user or is_valid_group or is_valid_location):
            raise exceptions.InvalidOwner(owner_field)
        if not self._location_is_accessible(owner):
            raise exceptions.InvalidLocation(owner_field)
        return True

    def _location_is_accessible(self, owner):
        return (
            self.user.has_permission(self.domain, 'access_all_locations')
            or (isinstance(owner, CouchUser)
                and owner.get_location_id(self.domain) in self._accessible_locations)
            or (isinstance(owner, SQLLocation)
                and owner.location_id in self._accessible_locations)
        )

    @cached_property
    def _accessible_locations(self):
        return set(
            SQLLocation.objects
            .accessible_to_user(self.domain, self.user)
            .values_list('location_id', flat=True)
        )


def cached_function_call(fn, param, cache):
    """Calls fn(param), storing the result in cache, including CaseRowErrors"""
    if param in cache:
        result = cache[param]
        if isinstance(result, CaseRowError):
            raise result
        return result

    try:
        result = fn(param)
    except CaseRowError as err:
        cache[param] = err
        raise
    else:
        cache[param] = result
        return result
