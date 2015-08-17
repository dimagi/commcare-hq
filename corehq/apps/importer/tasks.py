from celery.task import task
from xml.etree import ElementTree
from dimagi.utils.couch.database import is_bigcouch
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.importer.const import LookupErrors, ImportErrors
from corehq.apps.importer import util as importer_util
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from soil import DownloadBase
from casexml.apps.case.xml import V2
from dimagi.utils.prime_views import prime_views
from couchdbkit.exceptions import ResourceNotFound
import uuid

POOL_SIZE = 10
PRIME_VIEW_FREQUENCY = 500
CASEBLOCK_CHUNKSIZE = 100


@task
def bulk_import_async(import_id, config, domain, excel_id):
    excel_ref = DownloadBase.get(excel_id)
    spreadsheet = importer_util.get_spreadsheet(excel_ref, config.named_columns)
    return do_import(spreadsheet, config, domain, task=bulk_import_async)


def do_import(spreadsheet, config, domain, task=None, chunksize=CASEBLOCK_CHUNKSIZE):
    if not spreadsheet:
        return {'error': 'EXPIRED'}
    if spreadsheet.has_errors:
        return {'error': 'HAS_ERRORS'}

    row_count = spreadsheet.get_num_rows()
    columns = spreadsheet.get_header_columns()
    match_count = created_count = too_many_matches = num_chunks = 0
    errors = importer_util.ImportErrorDetail()
    prime_offset = 1  # used to prevent back-to-back priming

    user = CouchUser.get_by_user_id(config.couch_user_id, domain)
    username = user.username
    user_id = user._id

    # keep a cache of id lookup successes to help performance
    id_cache = {}
    name_cache = {}
    caseblocks = []
    ids_seen = set()

    def _submit_caseblocks(caseblocks):
        if caseblocks:
            submit_case_blocks(
                [ElementTree.tostring(cb.as_xml()) for cb in caseblocks],
                domain,
                username,
                user_id,
            )

    for i in range(row_count):
        if task:
            DownloadBase.set_progress(task, i, row_count)

        # skip first row if it is a header field
        if i == 0 and config.named_columns:
            continue

        if not is_bigcouch():
            priming_progress = match_count + created_count + prime_offset
            if priming_progress % PRIME_VIEW_FREQUENCY == 0:
                prime_views(POOL_SIZE)
                # increment so we can't possibly prime on next iteration
                prime_offset += 1

        row = spreadsheet.get_row(i)
        search_id = importer_util.parse_search_id(config, columns, row)
        if config.search_field == 'external_id' and not search_id:
            # do not allow blank external id since we save this
            errors.add(ImportErrors.BlankExternalId, i + 1)
            continue

        try:
            fields_to_update = importer_util.populate_updated_fields(
                config,
                columns,
                row,
                spreadsheet.workbook.datemode
            )
            if not any(fields_to_update.values()):
                # if the row was blank, just skip it, no errors
                continue
        except importer_util.InvalidDateException:
            errors.add(ImportErrors.InvalidDate, i + 1)
            continue

        external_id = fields_to_update.pop('external_id', None)
        parent_id = fields_to_update.pop('parent_id', None)
        parent_external_id = fields_to_update.pop('parent_external_id', None)
        parent_type = fields_to_update.pop('parent_type', config.case_type)
        parent_ref = fields_to_update.pop('parent_ref', 'parent')
        to_close = fields_to_update.pop('close', False)

        if any([lookup_id and lookup_id in ids_seen for lookup_id in [search_id, parent_id, parent_external_id]]):
            # clear out the queue to make sure we've processed any potential
            # cases we want to look up
            # note: these three lines are repeated a few places, and could be converted
            # to a function that makes use of closures (and globals) to do the same thing,
            # but that seems sketchier than just beeing a little RY
            _submit_caseblocks(caseblocks)
            num_chunks += 1
            caseblocks = []
            ids_seen = set()  # also clear ids_seen, since all the cases will now be in the database

        case, error = importer_util.lookup_case(
            config.search_field,
            search_id,
            domain,
            config.case_type
        )

        if case:
            if case.type != config.case_type:
                continue
        elif error == LookupErrors.NotFound:
            if not config.create_new_cases:
                continue
        elif error == LookupErrors.MultipleResults:
            too_many_matches += 1
            continue

        uploaded_owner_name = fields_to_update.pop('owner_name', None)
        uploaded_owner_id = fields_to_update.pop('owner_id', None)

        if uploaded_owner_name:
            # If an owner name was provided, replace the provided
            # uploaded_owner_id with the id of the provided group or owner
            try:
                uploaded_owner_id = importer_util.get_id_from_name(uploaded_owner_name, domain, name_cache)
            except SQLLocation.MultipleObjectsReturned:
                errors.add(ImportErrors.DuplicateLocationName, i + 1)
                continue

            if not uploaded_owner_id:
                errors.add(ImportErrors.InvalidOwnerName, i + 1)
                continue
        if uploaded_owner_id:
            # If an owner_id mapping exists, verify it is a valid user
            # or case sharing group
            if importer_util.is_valid_id(uploaded_owner_id, domain, id_cache):
                owner_id = uploaded_owner_id
                id_cache[uploaded_owner_id] = True
            else:
                errors.add(ImportErrors.InvalidOwnerId, i + 1)
                id_cache[uploaded_owner_id] = False
                continue
        else:
            # if they didn't supply an owner_id mapping, default to current
            # user
            owner_id = user_id

        extras = {}
        if parent_id:
            try:
                parent_case = CommCareCase.get(parent_id)

                if parent_case.domain == domain:
                    extras['index'] = {
                        parent_ref: (parent_case.type, parent_id)
                    }
            except ResourceNotFound:
                errors.add(ImportErrors.InvalidParentId, i + 1)
                continue
        elif parent_external_id:
            parent_case, error = importer_util.lookup_case(
                'external_id',
                parent_external_id,
                domain,
                parent_type
            )
            if parent_case:
                extras['index'] = {
                    parent_ref: (parent_type, parent_case._id)
                }

        if not case:
            id = uuid.uuid4().hex

            if config.search_field == 'external_id':
                extras['external_id'] = search_id

            try:
                caseblock = CaseBlock(
                    create=True,
                    case_id=id,
                    version=V2,
                    owner_id=owner_id,
                    user_id=user_id,
                    case_type=config.case_type,
                    update=fields_to_update,
                    **extras
                )
                caseblocks.append(caseblock)
                created_count += 1
                if external_id:
                    ids_seen.add(external_id)
            except CaseBlockError:
                errors.add(ImportErrors.CaseGeneration, i + 1)
        else:
            if external_id:
                extras['external_id'] = external_id
            if uploaded_owner_id:
                extras['owner_id'] = owner_id
            if to_close == 'yes':
                extras['close'] = True

            try:
                caseblock = CaseBlock(
                    create=False,
                    case_id=case._id,
                    version=V2,
                    update=fields_to_update,
                    **extras
                )
                caseblocks.append(caseblock)
                match_count += 1
            except CaseBlockError:
                errors.add(ImportErrors.CaseGeneration, i + 1)

        # check if we've reached a reasonable chunksize
        # and if so submit
        if len(caseblocks) >= chunksize:
            _submit_caseblocks(caseblocks)
            num_chunks += 1
            caseblocks = []

    # final purge of anything left in the queue
    _submit_caseblocks(caseblocks)
    num_chunks += 1
    return {
        'created_count': created_count,
        'match_count': match_count,
        'too_many_matches': too_many_matches,
        'errors': errors.as_dict(),
        'num_chunks': num_chunks,
    }
