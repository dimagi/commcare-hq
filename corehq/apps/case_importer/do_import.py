from __future__ import annotations

import uuid
from collections import Counter, defaultdict, namedtuple

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from couchdbkit import NoResultFound

from casexml.apps.case.const import CASE_TAG_DATE_OPENED
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from couchexport.export import SCALAR_NEVER_WAS
from dimagi.utils.logging import notify_exception
from soil.progress import TaskProgressManager

from corehq.apps.data_dictionary.util import fields_to_validate
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.receiverwrapper.rate_limiter import rate_limit_submission
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.form_processor.models import STANDARD_CHARFIELD_LENGTH
from corehq.toggles import (
    BULK_UPLOAD_DATE_OPENED,
    CASE_IMPORT_DATA_DICTIONARY_VALIDATION,
    DOMAIN_PERMISSIONS_MIRROR,
)
from corehq.util.metrics import metrics_counter, metrics_histogram
from corehq.util.metrics.load_counters import case_load_counter
from corehq.util.soft_assert import soft_assert
from corehq.util.timer import TimingContext

from .const import LookupErrors
from .exceptions import (
    BlankExternalId,
    CaseGeneration,
    CaseNameTooLong,
    CaseRowError,
    CaseRowErrorList,
    DuplicateLocationName,
    ExternalIdTooLong,
    ImportErrorMessage,
    InvalidCustomFieldNameException,
    InvalidLocation,
    InvalidOwner,
    InvalidOwnerName,
    InvalidParentId,
    TooManyMatches,
    UnexpectedError,
)
from .extension_points import custom_case_import_operations
from .util import EXTERNAL_ID, RESERVED_FIELDS, lookup_case

RowAndCase = namedtuple('RowAndCase', ['row', 'case'])
ALL_LOCATIONS = 'ALL_LOCATIONS'


def do_import(spreadsheet, config, domain, task=None, record_form_callback=None):
    has_domain_column = 'domain' in [c.lower() for c in spreadsheet.get_header_columns()]
    if has_domain_column and DOMAIN_PERMISSIONS_MIRROR.enabled(domain):
        allowed_domains = EnterprisePermissions.get_domains(domain)
        sub_domains = set()
        import_results = _ImportResults()
        for row_num, row in enumerate(spreadsheet.iter_row_dicts(), start=1):
            if row_num == 1:
                continue  # skip first row (header row)
            sheet_domain = row.get('domain')
            if sheet_domain != domain and sheet_domain not in allowed_domains:
                err = CaseRowError(column_name='domain')
                err.title = _('Invalid domain')
                err.message = _('Following rows contain invalid value for domain column.')
                import_results.add_error(row_num, err)
            else:
                sub_domains.add(sheet_domain)
        for sub_domain in sub_domains:
            importer = _TimedAndThrottledImporter(
                sub_domain,
                config,
                task,
                record_form_callback,
                import_results,
                multi_domain=True
            )
            importer.do_import(spreadsheet)
        return import_results.to_json()
    else:
        importer = _TimedAndThrottledImporter(
            domain,
            config,
            task,
            record_form_callback,
            multi_domain=False,
        )
        return importer.do_import(spreadsheet)


class _TimedAndThrottledImporter:

    def __init__(
        self,
        domain,
        config,
        task,
        record_form_callback,
        import_results=None,
        multi_domain=False,
    ):
        self.domain = domain
        self.task = task
        self.record_form_callback = record_form_callback
        self.results = import_results or _ImportResults()
        self.config = config
        self.submission_handler = SubmitCaseBlockHandler(
            domain,
            import_results=self.results,
            case_type=self.config.case_type,
            user=self.user,
            record_form_callback=record_form_callback,
            throttle=True,
        )
        self.owner_accessor = _OwnerAccessor(domain, self.user)
        self._unsubmitted_caseblocks = []
        self.multi_domain = multi_domain
        if CASE_IMPORT_DATA_DICTIONARY_VALIDATION.enabled(self.domain):
            self.fields_to_validate = fields_to_validate(domain, config.case_type)
        else:
            self.fields_to_validate = {}
        self.field_map = self._create_field_map()

    def do_import(self, spreadsheet):
        with TimingContext() as timer:
            results = self._do_import(spreadsheet)
        try:
            self._report_import_timings(timer, results)
        except Exception:
            notify_exception(None, "Error reporting case import timings")
        finally:
            return results

    def _do_import(self, spreadsheet):
        with TaskProgressManager(self.task, src="case_importer") as progress_manager:
            # context to be used by extensions to keep during import
            import_context = {}
            for row_num, row in enumerate(spreadsheet.iter_row_dicts(), start=1):
                progress_manager.set_progress(row_num - 1, spreadsheet.max_row)
                if row_num == 1:
                    continue  # skip first row (header row)

                try:
                    # check if there's a domain column, if true it's value should
                    # match the current domain, else skip the row.
                    if self.multi_domain:
                        if self.domain != row.get('domain'):
                            continue
                    self.import_row(row_num, row, import_context)
                except CaseRowErrorList as errors:
                    self.results.add_errors(row_num, errors)
                except CaseRowError as error:
                    self.results.add_error(row_num, error)

            self.submission_handler.commit_caseblocks()
            return self.results.to_json()

    def import_row(self, row_num, raw_row, import_context):
        search_id = self._parse_search_id(raw_row)
        fields_to_update = self._populate_updated_fields(raw_row)
        if self._has_custom_case_import_operations():
            fields_to_update = self._perform_custom_case_import_operations(
                row_num,
                raw_row,
                fields_to_update,
                import_context,
            )
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
        if row.relies_on_uncreated_case(self.submission_handler.uncreated_external_ids):
            self.submission_handler.commit_caseblocks()
        if row.is_new_case and not self.config.create_new_cases:
            return

        try:
            if row.is_new_case:
                if row.external_id:
                    self.submission_handler.uncreated_external_ids.add(row.external_id)
                caseblock = row.get_create_caseblock()
                self.results.add_created(row_num)
            else:
                caseblock = row.get_update_caseblock()
                self.results.add_updated(row_num)
        except CaseBlockError as e:
            raise CaseGeneration(message=str(e))

        self.submission_handler.add_caseblock(RowAndCase(row_num, caseblock))

    def _has_custom_case_import_operations(self):
        return any(
            extension.should_call_for_domain(self.domain)
            for extension in custom_case_import_operations.extensions
        )

    def _perform_custom_case_import_operations(self, row_num, raw_row, fields_to_update, import_context):
        extensions_response = custom_case_import_operations(self.domain, row_num, raw_row,
                                                            fields_to_update, import_context)
        if not extensions_response:
            raise UnexpectedError()
        fields_to_update, custom_errors = extensions_response
        if custom_errors:
            raise CaseRowErrorList(custom_errors)
        return fields_to_update

    @cached_property
    def user(self):
        return CouchUser.get_by_user_id(self.config.couch_user_id)

    def _parse_search_id(self, row):
        """ Find and convert the search id in an Excel row """

        # Find index of user specified search column
        search_column = self.config.search_column
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

    def _populate_updated_fields(self, row):
        """
        Returns a dict map of fields that were marked to be updated
        due to the import. This can be then used to pass to the CaseBlock
        to trigger updates.
        """
        field_map = self.field_map
        fields_to_update = {}
        errors = []
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
                if update_field_name == 'parent_ref':
                    raise InvalidCustomFieldNameException(
                        _('Field name "{}" is deprecated. Please use "parent_identifier" instead.'))
                else:
                    raise InvalidCustomFieldNameException(
                        _('Field name "{}" is reserved').format(update_field_name))

            if isinstance(update_value, str) and update_value.strip() == SCALAR_NEVER_WAS:
                # If we find any instances of blanks ('---'), convert them to an
                # actual blank value without performing any data type validation.
                # This is to be consistent with how the case export works.
                update_value = ''
            elif update_value is not None:
                update_value = _convert_field_value(update_value)

            if update_field_name in self.fields_to_validate:
                case_property = self.fields_to_validate[update_field_name]
                try:
                    case_property.check_validity(update_value)
                except CaseRowError as error:
                    error.column_name = update_field_name
                    errors.append(error)

            fields_to_update[update_field_name] = update_value

        if errors:
            raise CaseRowErrorList(errors)

        return fields_to_update

    def _create_field_map(self):
        config = self.config
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
                    # if we have configured this field for external_id
                    # populate external_id instead of the default
                    # property name from the column
                    if config.search_field == EXTERNAL_ID and field == config.search_column:
                        field_map[field]['field_name'] = EXTERNAL_ID
                    else:
                        field_map[field]['field_name'] = custom_fields[i]
        # hack: make sure the external_id column ends up in the
        # field_map if the user didn't explicitly put it there
        if config.search_column not in field_map and config.search_field == EXTERNAL_ID:
            field_map[config.search_column] = {
                'field_name': EXTERNAL_ID
            }
        return field_map

    def _report_import_timings(self, timer, results):
        active_duration = timer.duration - self.submission_handler._total_delayed_duration
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


class SubmitCaseBlockHandler:
    """
    ``SubmitCaseBlockHandler`` can handle the submission of large
    numbers of case blocks. It supports throttling.

    Used by this module, ``corehq.apps.data_interfaces.tasks`` and
    ``corehq.apps.reports.filters.api``.
    """

    def __init__(
        self,
        domain,
        *,
        import_results,
        case_type,
        user,
        record_form_callback=None,
        throttle=False,
        add_inferred_props_to_schema=True,
    ):
        """
        Initialize ``SubmitCaseBlockHandler``.

        :param domain: Domain name
        :param import_results: Used for storing success and error
            results of an import.
        :param case_type: Used for adding inferred properties to schema.
        :param user: A CouchUser, or an object with ``user_id`` and
            ``username`` properties.
        :param record_form_callback: Only used in one place, which uses
            ``CaseUpload.record_form()``. It takes a form ID.
        :param throttle: If ``True``, uses heuristics to rate-limit
            caseblock submissions.
        :param add_inferred_props_to_schema: If ``True``, add inferred
            properties to schema of ``case_type``
        """
        self.domain = domain
        self._unsubmitted_caseblocks: list[RowAndCase] = []
        self.results = import_results or _ImportResults()
        self.uncreated_external_ids = set()
        self.record_form_callback = record_form_callback
        self._last_submission_duration = 1  # duration in seconds; start with a value of 1s
        self._total_delayed_duration = 0  # sum of all rate limiter delays, in seconds
        self.throttle = throttle
        self.add_inferred_props_to_schema = add_inferred_props_to_schema
        self.case_type = case_type
        self.user = user

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
                self.results.add_error(row_number, ImportErrorMessage())
        else:
            if self.record_form_callback:
                self.record_form_callback(form.form_id)
            if self.add_inferred_props_to_schema:
                properties = {
                    p for c in cases
                    for p in c.dynamic_case_properties().keys()
                }
                if self.case_type and len(properties):
                    add_inferred_export_properties.delay(
                        'CaseImporter',
                        self.domain,
                        self.case_type,
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
        if not self.throttle:
            return
        if rate_limit_submission(
            self.domain,
            delay_rather_than_reject=True,
            max_wait=self._last_submission_duration
        ):
            # The duration of the last submission is a combined
            # heuristic for the amount of load on the databases and the
            # amount of load that the requests from this import put on
            # the databases. The amount of time to wait, during a high
            # submission period and while this project is using up more
            # than its fair share should be proportional to this
            # heuristic. For a fully throttled domain, this will up to
            # double the amount of time the case import takes
            metrics_histogram(
                'commcare.case_importer.import_delays',
                self._last_submission_duration,
                buckets=[5, 7, 10, 15, 25, 35, 50],
                bucket_tag='duration',
                bucket_unit='s',
                tags={'domain': self.domain}
            )
            self._total_delayed_duration += self._last_submission_duration

    def submit_case_blocks(self, caseblocks):
        if not self.throttle:
            return self._submit_case_blocks(caseblocks)
        timer = None
        try:
            with TimingContext() as timer:
                return self._submit_case_blocks(caseblocks)
        finally:
            if timer:
                self._last_submission_duration = timer.duration

    def _submit_case_blocks(self, caseblocks):
        return submit_case_blocks(
            [cb.case.as_text() for cb in caseblocks],
            self.domain,
            self.user.username,
            self.user.user_id,
            device_id=__name__ + ".do_import",
            # Skip the rate-limiting because this importing code will
            # take care of any rate-limiting
            max_wait=None,
        )


class _CaseImportRow(object):
    def __init__(self, search_id, fields_to_update, config, domain, user_id, owner_accessor):
        self.search_id = search_id
        self.fields_to_update = fields_to_update
        self.config = config
        self.domain = domain
        self.user_id = user_id
        self.owner_accessor = owner_accessor

        self.case_name = fields_to_update.pop('name', None)
        self._check_case_name()
        self.external_id = fields_to_update.pop('external_id', None)
        self._check_valid_external_id()
        self.parent_id = fields_to_update.pop('parent_id', None)
        self.parent_external_id = fields_to_update.pop('parent_external_id', None)
        self.parent_type = fields_to_update.pop('parent_type', self.config.case_type)
        self.parent_relationship_type = fields_to_update.pop('parent_relationship_type', 'child')
        self.parent_identifier = fields_to_update.pop('parent_identifier', None)
        self.to_close = fields_to_update.pop('close', False)
        self.uploaded_owner_name = fields_to_update.pop('owner_name', None)
        self.uploaded_owner_id = fields_to_update.pop('owner_id', None)
        self.date_opened = fields_to_update.pop(CASE_TAG_DATE_OPENED, None)

    def _check_case_name(self):
        if self.case_name and len(self.case_name) > STANDARD_CHARFIELD_LENGTH:
            raise CaseNameTooLong('name')

    def _check_valid_external_id(self):
        if self.external_id and len(self.external_id) > STANDARD_CHARFIELD_LENGTH:
            raise ExternalIdTooLong('external_id')

        if self.config.search_field == 'external_id' and not self.search_id:
            # do not allow blank external id since we save this
            raise BlankExternalId()

    def validate_parent_column(self):
        # host_id column is used to create extension cases. Run below validations
        #   when user tries to create extension cases

        if self.parent_relationship_type == 'child':
            return
        elif self.parent_relationship_type == 'extension':
            if not self.parent_identifier:
                raise InvalidParentId(_(
                    "'parent_identifier' column must be provided "
                    "when 'parent_relationship_type' column is set to 'extension'"
                ))
        else:
            raise InvalidParentId(_("Invalid value for 'parent_relationship_type' column"))

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
            raise TooManyMatches()
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
                    self.validate_parent_column()
                    if self.parent_relationship_type == 'child':
                        identifier = self.parent_identifier or 'parent'
                        return {identifier: (parent_case.type, parent_case.case_id)}
                    elif self.parent_relationship_type == 'extension':
                        identifier = self.parent_identifier
                        return {identifier: (parent_case.type, parent_case.case_id, "extension")}
                raise InvalidParentId(column)

    def _get_date_opened(self):
        if self.date_opened and BULK_UPLOAD_DATE_OPENED.enabled(self.domain):
            return self.date_opened

    def _get_external_id(self):
        if self.is_new_case and self.config.search_field == 'external_id':
            return self.search_id
        return self.external_id

    def _get_caseblock_kwargs(self):
        kwargs = {
            'update': self.fields_to_update,
            'index': self._get_parent_index(),
        }
        if date_opened := self._get_date_opened():
            kwargs['date_opened'] = date_opened
        if external_id := self._get_external_id():
            kwargs['external_id'] = external_id
        return kwargs

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
            self._errors[key][column_name]['description'] = CaseGeneration.message

        if 'rows' not in self._errors[key][column_name]:
            self._errors[key][column_name]['rows'] = []

        if row_num not in self._errors[key][column_name]['rows']:
            self._errors[key][column_name]['rows'].append(row_num)

        if 'sample' not in self._errors[key][column_name] and hasattr(error, 'sample'):
            self._errors[key][column_name]['sample'] = _(
                'Sample: Cell in row {row_num} contains "{sample}"').format(
                row_num=row_num, sample=error.sample)

    def add_errors(self, row_num, errors):
        for error in errors:
            self.add_error(row_num, error)

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
                raise DuplicateLocationName()

        owner = get_user(name) or get_group(name) or get_location(name)
        if not owner:
            raise InvalidOwnerName('owner_name')
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
            raise InvalidOwner(owner_field)
        if not self._location_is_accessible(owner):
            raise InvalidLocation(owner_field)
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
