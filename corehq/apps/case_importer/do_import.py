from __future__ import absolute_import, unicode_literals

import uuid
from collections import namedtuple

from django.utils.functional import cached_property

from casexml.apps.case.const import CASE_TAG_DATE_OPENED
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from dimagi.utils.logging import notify_exception
from soil.progress import set_task_progress

from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.toggles import BULK_UPLOAD_DATE_OPENED
from corehq.util.datadog.utils import case_load_counter
from corehq.util.soft_assert import soft_assert

from . import exceptions
from . import util as importer_util
from .const import LookupErrors

CASEBLOCK_CHUNKSIZE = 100
RowAndCase = namedtuple('RowAndCase', ['row', 'case'])


class _Importer(object):
    def __init__(self, domain, config, task, record_form_callback):
        self.domain = domain
        self.config = config
        self.task = task
        self._record_form_callback = record_form_callback

        self.created_count = 0
        self.match_count = 0
        self.num_chunks = 0
        self.errors = importer_util.ImportErrorDetail()

        self.id_cache = {}
        self.name_cache = {}
        self.uncreated_external_ids = set()
        self._caseblocks = []

    @cached_property
    def user(self):
        return CouchUser.get_by_user_id(self.config.couch_user_id, self.domain)

    def log_case_lookup(self):
        case_load_counter("case_importer", self.domain)

    def do_import(self, spreadsheet):
        row_count = spreadsheet.max_row
        for row_num, row in enumerate(spreadsheet.iter_row_dicts(), start=1):
            set_task_progress(self.task, row_num, row_count)

            # skip first row (header row)
            if row_num == 1:
                continue

            try:
                self.import_row(row_num, row)
            except exceptions.CaseRowError as error:
                self.errors.add(error, row_num)

        self.commit_caseblocks()

    def import_row(self, row_num, raw_row):
        search_id = importer_util.parse_search_id(self.config, raw_row)
        fields_to_update = importer_util.populate_updated_fields(self.config, raw_row)
        if not any(fields_to_update.values()):
            # if the row was blank, just skip it, no errors
            return

        row = CaseImportRow(search_id, fields_to_update, self.config, self.domain, self.user.user_id)
        row.check_valid_external_id()
        if row.relies_on_uncreated_case(self.uncreated_external_ids):
            self.commit_caseblocks()

        case, error = importer_util.lookup_case(
            self.config.search_field,
            row.search_id,
            self.domain,
            self.config.case_type
        )
        self.log_case_lookup()

        if case:
            if case.type != self.config.case_type:
                return  # TODO Add error message about skipped row
        elif error == LookupErrors.NotFound:
            if not self.config.create_new_cases:
                return
        elif error == LookupErrors.MultipleResults:
            raise exceptions.TooManyMatches()

        row.set_owner_id(self.name_cache, self.id_cache)
        row.set_parent_id(self.log_case_lookup)
        row.set_date_opened()
        row.set_external_id(is_new_case=not case)

        try:
            if not case:
                if row.external_id:
                    self.uncreated_external_ids.add(row.external_id)
                caseblock = row.get_create_caseblock()
                self.created_count += 1
            else:
                caseblock = row.get_update_caseblock(case)
                self.match_count += 1
        except CaseBlockError:
            raise exceptions.CaseGeneration()

        self.add_caseblock(RowAndCase(row_num, caseblock))

    def add_caseblock(self, caseblock):
        self._caseblocks.append(caseblock)
        # check if we've reached a reasonable chunksize and if so, submit
        if len(self._caseblocks) >= CASEBLOCK_CHUNKSIZE:
            self.commit_caseblocks()

    def commit_caseblocks(self):
        if self._caseblocks:
            self._submit_caseblocks(self._caseblocks)
            self.num_chunks += 1
            self._caseblocks = []
            self.uncreated_external_ids = set()

    def _submit_caseblocks(self, caseblocks):
        if caseblocks:
            try:
                form, cases = submit_case_blocks(
                    [cb.case.as_string().decode('utf-8') for cb in caseblocks],
                    self.domain,
                    self.user.username,
                    self.user.user_id,
                    device_id=__name__ + ".do_import",
                )
            except Exception:
                notify_exception(None, "Case Importer: Uncaught failure submitting caseblocks")
                for row_number, case in caseblocks:
                    self.errors.add(exceptions.ImportErrorMessage(), row_number)
            else:
                if form.is_error:
                    self.errors.add(exceptions.ImportErrorMessage(), form.problem)
                self.record_form(form.form_id)
                properties = set().union(*[set(c.dynamic_case_properties().keys()) for c in cases])
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

    def record_form(self, form_id):
        if self._record_form_callback:
            self._record_form_callback(form_id)

    @property
    def outcome(self):
        return {
            'created_count': self.created_count,
            'match_count': self.match_count,
            'errors': self.errors.as_dict(),
            'num_chunks': self.num_chunks,
        }


class CaseImportRow(object):
    def __init__(self, search_id, fields_to_update, config, domain, user_id):
        self.search_id = search_id
        self.fields_to_update = fields_to_update
        self.config = config
        self.domain = domain
        self.user_id = user_id

        self.case_name = fields_to_update.pop('name', None)
        self.external_id = fields_to_update.pop('external_id', None)
        self.parent_id = fields_to_update.pop('parent_id', None)
        self.parent_external_id = fields_to_update.pop('parent_external_id', None)
        self.parent_type = fields_to_update.pop('parent_type', self.config.case_type)
        self.parent_ref = fields_to_update.pop('parent_ref', 'parent')
        self.to_close = fields_to_update.pop('close', False)
        self.uploaded_owner_name = fields_to_update.pop('owner_name', None)
        self.uploaded_owner_id = fields_to_update.pop('owner_id', None)
        self.date_opened = fields_to_update.pop(CASE_TAG_DATE_OPENED, None)

        self.owner_id = None
        self.extras = {}

    def check_valid_external_id(self):
        if self.config.search_field == 'external_id' and not self.search_id:
            # do not allow blank external id since we save this
            raise exceptions.BlankExternalId()

    def relies_on_uncreated_case(self, uncreated_external_ids):
        return any(lookup_id and lookup_id in uncreated_external_ids
                   for lookup_id in [self.search_id, self.parent_id, self.parent_external_id])

    def set_owner_id(self, name_cache, id_cache):
        owner_id = self.uploaded_owner_id
        if self.uploaded_owner_name:
            # If an owner name was provided, use the id of the provided or
            # owner rather than the uploaded_owner_id
            try:
                owner_id = importer_util.get_id_from_name(
                    self.uploaded_owner_name, self.domain, name_cache
                )
            except SQLLocation.MultipleObjectsReturned:
                raise exceptions.DuplicateLocationName()

            if not owner_id:
                raise exceptions.InvalidOwnerName('owner_name')

        if owner_id:
            # If an owner_id mapping exists, verify it is a valid user
            # or case sharing group
            if importer_util.is_valid_id(owner_id, self.domain, id_cache):
                id_cache[owner_id] = True
            else:
                id_cache[owner_id] = False
                raise exceptions.InvalidOwnerId('owner_id')

        # if they didn't supply an owner, default to current user
        self.owner_id = owner_id or self.user_id

    def set_parent_id(self, log_case_lookup):
        for column, search_field, search_id  in [
                ('parent_id', 'case_id', self.parent_id),
                ('parent_external_id', 'external_id', self.parent_external_id),
        ]:
            if search_id:
                parent_case, error = importer_util.lookup_case(
                    search_field, search_id, self.domain, self.parent_type)
                log_case_lookup()
                if parent_case:
                    self.extras['index'] = {
                        self.parent_ref: (parent_case.type, parent_case.case_id)
                    }
                    return
                else:
                    raise exceptions.InvalidParentId(column)

    def set_date_opened(self):
        if self.date_opened and BULK_UPLOAD_DATE_OPENED.enabled(self.domain):
            self.extras['date_opened'] = self.date_opened

    def set_external_id(self, is_new_case):
        # This can almost certainly be simplified, will worry about that later
        if is_new_case:
            if self.config.search_field == 'external_id':
                self.extras['external_id'] = self.search_id
            elif self.external_id:
                self.extras['external_id'] = self.external_id
        else:
            if self.external_id:
                self.extras['external_id'] = self.external_id

    def get_create_caseblock(self):
        return CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=self.owner_id,
            user_id=self.user_id,
            case_type=self.config.case_type,
            case_name=self.case_name or '',
            update=self.fields_to_update,
            **self.extras
        )

    def get_update_caseblock(self, case):
        if self.uploaded_owner_id or self.uploaded_owner_name:
            self.extras['owner_id'] = self.owner_id
        if self.to_close == 'yes':
            self.extras['close'] = True
        if self.case_name is not None:
            self.extras['case_name'] = self.case_name
        return CaseBlock(
            create=False,
            case_id=case.case_id,
            update=self.fields_to_update,
            **self.extras
        )


def do_import(spreadsheet, config, domain, task=None, record_form_callback=None):
    importer = _Importer(domain, config, task, record_form_callback)
    importer.do_import(spreadsheet)
    return importer.outcome
