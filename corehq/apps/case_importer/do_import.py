from __future__ import absolute_import, unicode_literals

import uuid
from collections import Counter, defaultdict, namedtuple

from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

import six
from couchdbkit import NoResultFound

from casexml.apps.case.const import CASE_TAG_DATE_OPENED
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from couchexport.export import SCALAR_NEVER_WAS
from dimagi.utils.logging import notify_exception
from soil.progress import set_task_progress

from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.toggles import BULK_UPLOAD_DATE_OPENED
from corehq.util.datadog.utils import case_load_counter
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.soft_assert import soft_assert

from . import exceptions
from .const import LookupErrors
from .util import EXTERNAL_ID, RESERVED_FIELDS, lookup_case

CASEBLOCK_CHUNKSIZE = 100
RowAndCase = namedtuple('RowAndCase', ['row', 'case'])
ALL_LOCATIONS = 'ALL_LOCATIONS'


def do_import(spreadsheet, config, domain, task=None, record_form_callback=None):
    importer = _Importer(domain, config, task, record_form_callback)
    return importer.do_import(spreadsheet)


class _Importer(object):
    def __init__(self, domain, config, task, record_form_callback):
        self.domain = domain
        self.config = config
        self.task = task
        self.record_form_callback = record_form_callback

        self.results = _ImportResults()

        self.id_cache = {}
        self.name_cache = {}
        self.uncreated_external_ids = set()
        self._unsubmitted_caseblocks = []

    def do_import(self, spreadsheet):
        for row_num, row in enumerate(spreadsheet.iter_row_dicts(), start=1):
            set_task_progress(self.task, row_num - 1, spreadsheet.max_row)
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
            name_cache=self.name_cache,
            id_cache=self.id_cache,
            locations=self.locations_accessible_to_user,
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
        return CouchUser.get_by_user_id(self.config.couch_user_id, self.domain)

    @cached_property
    def locations_accessible_to_user(self):
        if self.user.has_permission(self.domain, 'access_all_locations'):
            return ALL_LOCATIONS
        return set(
            SQLLocation.objects
            .accessible_to_user(self.domain, self.user)
            .values_list('location_id', flat=True)
        )

    def add_caseblock(self, caseblock):
        self._unsubmitted_caseblocks.append(caseblock)
        # check if we've reached a reasonable chunksize and if so, submit
        if len(self._unsubmitted_caseblocks) >= CASEBLOCK_CHUNKSIZE:
            self.commit_caseblocks()

    def commit_caseblocks(self):
        if self._unsubmitted_caseblocks:
            self.submit_caseblocks(self._unsubmitted_caseblocks)
            self.results.num_chunks += 1
            self._unsubmitted_caseblocks = []
            self.uncreated_external_ids = set()

    def submit_caseblocks(self, caseblocks):
        if not caseblocks:
            return

        try:
            form, cases = submit_case_blocks(
                [cb.case.as_string().decode('utf-8') for cb in caseblocks],
                self.domain,
                self.user.username,
                self.user.user_id,
                device_id=__name__ + ".do_import",
            )
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


class _CaseImportRow(object):
    def __init__(self, search_id, fields_to_update, config, domain, user_id, name_cache, id_cache, locations):
        self.search_id = search_id
        self.fields_to_update = fields_to_update
        self.config = config
        self.domain = domain
        self.user_id = user_id
        self.name_cache = name_cache
        self.id_cache = id_cache
        self.accessible_locations = locations

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
        owner_id = self.uploaded_owner_id
        if self.uploaded_owner_name:
            # If an owner name was provided, use the id of the provided or
            # owner rather than the uploaded_owner_id
            try:
                owner_id = _get_id_from_name(
                    self.uploaded_owner_name, self.domain, self.name_cache
                )
            except SQLLocation.MultipleObjectsReturned:
                raise exceptions.DuplicateLocationName()

            if not owner_id:
                raise exceptions.InvalidOwnerName('owner_name')

        if owner_id:
            # If an owner_id mapping exists, verify it is a valid user
            # or case sharing group
            if _is_valid_id(owner_id, self.domain, self.id_cache, self.user_id, self.accessible_locations):
                self.id_cache[owner_id] = True
            else:
                self.id_cache[owner_id] = False
                raise exceptions.InvalidOwnerId('owner_id')

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
        counts = Counter(six.itervalues(self._results))
        return {
            'created_count': counts.get(self.CREATED, 0),
            'match_count': counts.get(self.UPDATED, 0),
            'errors': dict(self._errors),
            'num_chunks': self.num_chunks,
        }


def _convert_field_value(value):
    # coerce to string unless it's a unicode string then we want that
    if isinstance(value, six.text_type):
        return value
    else:
        return str(value)


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

        if isinstance(update_value, six.string_types) and update_value.strip() == SCALAR_NEVER_WAS:
            soft_assert_type_text(update_value)
            # If we find any instances of blanks ('---'), convert them to an
            # actual blank value without performing any data type validation.
            # This is to be consistent with how the case export works.
            update_value = ''
        elif update_value is not None:
            update_value = _convert_field_value(update_value)

        fields_to_update[update_field_name] = update_value

    return fields_to_update


def _is_valid_id(uploaded_id, domain, cache, user_id, locations):
    if uploaded_id in cache:
        return cache[uploaded_id]

    owner = get_wrapped_owner(uploaded_id)
    return _is_valid_owner(owner, domain, user_id, locations)


def _is_valid_owner(owner, domain, user_id=None, locations=ALL_LOCATIONS):
    owner_is_user = isinstance(owner, CouchUser) and owner.is_member_of(domain)
    owner_is_casesharing_group = isinstance(owner, Group) and owner.case_sharing and owner.is_member_of(domain)
    return (
        (owner_is_user or owner_is_casesharing_group or _is_valid_location_owner(owner, domain))
        and _is_owner_location_accessible_to_user(owner, domain, user_id, locations)
    )


def _is_valid_location_owner(owner, domain):
    return (
        isinstance(owner, SQLLocation) and
        owner.domain == domain and
        owner.location_type.shares_cases
    )


def _is_owner_location_accessible_to_user(owner, domain, user_id, locations_accessible_to_user):
    return (
        owner._id == user_id or
        locations_accessible_to_user == ALL_LOCATIONS or
        owner._id in locations_accessible_to_user or
        (
            hasattr(owner, 'get_location_id')  # is a user, not a location
            and owner.get_location_id(domain) in locations_accessible_to_user
        )
    )


def _get_id_from_name(name, domain, cache):
    '''
    :param name: A username, group name, or location name/site_code
    :param domain:
    :param cache:
    :return: Looks for the given name and returns the corresponding id if the
    user or group exists and None otherwise. Searches for user first, then
    group, then location
    '''
    if name in cache:
        return cache[name]

    def get_from_user(name):
        try:
            name_as_address = name
            if '@' not in name_as_address:
                name_as_address = format_username(name, domain)
            user = CouchUser.get_by_username(name_as_address)
            return getattr(user, 'couch_id', None)
        except NoResultFound:
            return None

    def get_from_group(name):
        group = Group.by_name(domain, name, one=True)
        return getattr(group, 'get_id', None)

    def get_from_location(name):
        try:
            return SQLLocation.objects.get_from_user_input(domain, name).location_id
        except SQLLocation.DoesNotExist:
            return None

    id = get_from_user(name) or get_from_group(name) or get_from_location(name)
    cache[name] = id
    return id
