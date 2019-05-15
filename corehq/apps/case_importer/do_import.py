from __future__ import absolute_import, unicode_literals

import uuid
from collections import namedtuple

from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.const import CASE_TAG_DATE_OPENED
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from soil.progress import set_task_progress

from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import BULK_UPLOAD_DATE_OPENED
from corehq.util.datadog.utils import case_load_counter
from corehq.util.soft_assert import soft_assert

from . import util as importer_util
from .const import ImportErrors, LookupErrors

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
        self.too_many_matches = 0
        self.num_chunks = 0
        self.errors = importer_util.ImportErrorDetail()

    def do_import(self, spreadsheet):
        user = CouchUser.get_by_user_id(self.config.couch_user_id, self.domain)
        username = user.username
        user_id = user._id

        # keep a cache of id lookup successes to help performance
        id_cache = {}
        name_cache = {}
        caseblocks = []
        ids_seen = set()
        track_load = case_load_counter("case_importer", self.domain)

        def _submit_caseblocks(case_type, caseblocks):
            err = False
            if caseblocks:
                try:
                    form, cases = submit_case_blocks(
                        [cb.case.as_string().decode('utf-8') for cb in caseblocks],
                        self.domain,
                        username,
                        user_id,
                        device_id=__name__ + ".do_import",
                    )

                    if form.is_error:
                        self.errors.add(
                            error=ImportErrors.ImportErrorMessage,
                            row_number=form.problem
                        )
                except Exception:
                    err = True
                    for row_number, case in caseblocks:
                        self.errors.add(
                            error=ImportErrors.ImportErrorMessage,
                            row_number=row_number
                        )
                else:
                    self.record_form(form.form_id)
                    properties = set().union(*[set(c.dynamic_case_properties().keys()) for c in cases])
                    if case_type and len(properties):
                        add_inferred_export_properties.delay(
                            'CaseImporter',
                            self.domain,
                            case_type,
                            properties,
                        )
                    else:
                        _soft_assert = soft_assert(notify_admins=True)
                        _soft_assert(
                            len(properties) == 0,
                            'error adding inferred export properties in domain '
                            '({}): {}'.format(self.domain, ", ".join(properties))
                        )
            return err

        row_count = spreadsheet.max_row
        for i, row in enumerate(spreadsheet.iter_row_dicts()):
            set_task_progress(self.task, i, row_count)

            # skip first row (header row)
            if i == 0:
                continue

            search_id = importer_util.parse_search_id(self.config, row)

            fields_to_update = importer_util.populate_updated_fields(self.config, row)
            if not any(fields_to_update.values()):
                # if the row was blank, just skip it, no errors
                continue

            if self.config.search_field == 'external_id' and not search_id:
                # do not allow blank external id since we save this
                self.errors.add(ImportErrors.BlankExternalId, i + 1)
                continue

            external_id = fields_to_update.pop('external_id', None)
            parent_id = fields_to_update.pop('parent_id', None)
            parent_external_id = fields_to_update.pop('parent_external_id', None)
            parent_type = fields_to_update.pop('parent_type', self.config.case_type)
            parent_ref = fields_to_update.pop('parent_ref', 'parent')
            to_close = fields_to_update.pop('close', False)

            if any([lookup_id and lookup_id in ids_seen for lookup_id in [search_id, parent_id, parent_external_id]]):
                # clear out the queue to make sure we've processed any potential
                # cases we want to look up
                # note: these three lines are repeated a few places, and could be converted
                # to a function that makes use of closures (and globals) to do the same thing,
                # but that seems sketchier than just beeing a little RY
                _submit_caseblocks(self.config.case_type, caseblocks)
                self.num_chunks += 1
                caseblocks = []
                ids_seen = set()  # also clear ids_seen, since all the cases will now be in the database

            case, error = importer_util.lookup_case(
                self.config.search_field,
                search_id,
                self.domain,
                self.config.case_type
            )
            track_load()

            if case:
                if case.type != self.config.case_type:
                    continue
            elif error == LookupErrors.NotFound:
                if not self.config.create_new_cases:
                    continue
            elif error == LookupErrors.MultipleResults:
                self.too_many_matches += 1
                continue

            uploaded_owner_name = fields_to_update.pop('owner_name', None)
            uploaded_owner_id = fields_to_update.pop('owner_id', None)

            if uploaded_owner_name:
                # If an owner name was provided, replace the provided
                # uploaded_owner_id with the id of the provided group or owner
                try:
                    uploaded_owner_id = importer_util.get_id_from_name(uploaded_owner_name, self.domain, name_cache)
                except SQLLocation.MultipleObjectsReturned:
                    self.errors.add(ImportErrors.DuplicateLocationName, i + 1)
                    continue

                if not uploaded_owner_id:
                    self.errors.add(ImportErrors.InvalidOwnerName, i + 1, 'owner_name')
                    continue
            if uploaded_owner_id:
                # If an owner_id mapping exists, verify it is a valid user
                # or case sharing group
                if importer_util.is_valid_id(uploaded_owner_id, self.domain, id_cache):
                    owner_id = uploaded_owner_id
                    id_cache[uploaded_owner_id] = True
                else:
                    self.errors.add(ImportErrors.InvalidOwnerId, i + 1, 'owner_id')
                    id_cache[uploaded_owner_id] = False
                    continue
            else:
                # if they didn't supply an owner_id mapping, default to current
                # user
                owner_id = user_id

            extras = {}
            if parent_id:
                try:
                    parent_case = CaseAccessors(self.domain).get_case(parent_id)
                    track_load()

                    if parent_case.domain == self.domain:
                        extras['index'] = {
                            parent_ref: (parent_case.type, parent_id)
                        }
                except ResourceNotFound:
                    self.errors.add(ImportErrors.InvalidParentId, i + 1, 'parent_id')
                    continue
            elif parent_external_id:
                parent_case, error = importer_util.lookup_case(
                    'external_id',
                    parent_external_id,
                    self.domain,
                    parent_type
                )
                track_load()
                if parent_case:
                    extras['index'] = {
                        parent_ref: (parent_type, parent_case.case_id)
                    }

            case_name = fields_to_update.pop('name', None)

            if BULK_UPLOAD_DATE_OPENED.enabled(self.domain):
                date_opened = fields_to_update.pop(CASE_TAG_DATE_OPENED, None)
                if date_opened:
                    extras['date_opened'] = date_opened

            if not case:
                id = uuid.uuid4().hex

                if self.config.search_field == 'external_id':
                    extras['external_id'] = search_id
                elif external_id:
                    extras['external_id'] = external_id

                try:
                    caseblock = CaseBlock(
                        create=True,
                        case_id=id,
                        owner_id=owner_id,
                        user_id=user_id,
                        case_type=self.config.case_type,
                        case_name=case_name or '',
                        update=fields_to_update,
                        **extras
                    )
                    caseblocks.append(RowAndCase(i, caseblock))
                    self.created_count += 1
                    if external_id:
                        ids_seen.add(external_id)
                except CaseBlockError:
                    self.errors.add(ImportErrors.CaseGeneration, i + 1)
            else:
                if external_id:
                    extras['external_id'] = external_id
                if uploaded_owner_id:
                    extras['owner_id'] = owner_id
                if to_close == 'yes':
                    extras['close'] = True
                if case_name is not None:
                    extras['case_name'] = case_name

                try:
                    caseblock = CaseBlock(
                        create=False,
                        case_id=case.case_id,
                        update=fields_to_update,
                        **extras
                    )
                    caseblocks.append(RowAndCase(i, caseblock))
                    self.match_count += 1
                except CaseBlockError:
                    self.errors.add(ImportErrors.CaseGeneration, i + 1)

            # check if we've reached a reasonable chunksize
            # and if so submit
            if len(caseblocks) >= CASEBLOCK_CHUNKSIZE:
                _submit_caseblocks(self.config.case_type, caseblocks)
                self.num_chunks += 1
                caseblocks = []

        # final purge of anything left in the queue
        if _submit_caseblocks(self.config.case_type, caseblocks):
            self.match_count -= 1
        self.num_chunks += 1

    def record_form(self, form_id):
        if self._record_form_callback:
            self._record_form_callback(form_id)

    @property
    def outcome(self):
        return {
            'created_count': self.created_count,
            'match_count': self.match_count,
            'too_many_matches': self.too_many_matches,
            'errors': self.errors.as_dict(),
            'num_chunks': self.num_chunks,
        }


def do_import(spreadsheet, config, domain, task=None, record_form_callback=None):
    importer = _Importer(domain, config, task, record_form_callback)
    importer.do_import(spreadsheet)
    return importer.outcome
