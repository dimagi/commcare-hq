from celery.task import task
from xml.etree import ElementTree
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.importer.const import LookupErrors
import corehq.apps.importer.util as importer_util
from corehq.apps.users.models import CouchUser
from soil import DownloadBase
from casexml.apps.case.tests.util import CaseBlock, CaseBlockError
from casexml.apps.case.xml import V2
from dimagi.utils.prime_views import prime_views
import uuid

POOL_SIZE = 10
PRIME_VIEW_FREQUENCY = 500

@task
def bulk_import_async(import_id, config, domain, excel_id):
    task = bulk_import_async

    excel_ref = DownloadBase.get(excel_id)

    spreadsheet = importer_util.get_spreadsheet(excel_ref, config.named_columns)

    if not spreadsheet:
        return {'error': 'EXPIRED'}
    if spreadsheet.has_errors:
        return {'error': 'HAS_ERRORS'}

    row_count = spreadsheet.get_num_rows()
    columns = spreadsheet.get_header_columns()
    match_count = created_count = too_many_matches = errors = 0
    blank_external_ids = []
    invalid_dates = []
    owner_id_errors = []
    prime_offset = 1  # used to prevent back-to-back priming

    user = CouchUser.get_by_user_id(config.couch_user_id, domain)
    username = user.username
    user_id = user._id

    # keep a cache of id lookup successes to help performance
    id_cache = {}

    for i in range(row_count):
        DownloadBase.set_progress(task, i, row_count)
        # skip first row if it is a header field
        if i == 0 and config.named_columns:
            continue

        priming_progress = match_count + created_count + prime_offset
        if priming_progress % PRIME_VIEW_FREQUENCY == 0:
            prime_views(POOL_SIZE)
            # increment so we can't possibly prime on next iteration
            prime_offset += 1

        row = spreadsheet.get_row(i)
        search_id = importer_util.parse_search_id(config, columns, row)
        if config.search_field == 'external_id' and not search_id:
            # do not allow blank external id since we save this
            blank_external_ids.append(i + 1)
            continue

        case, error = importer_util.lookup_case(
            config.search_field,
            search_id,
            domain,
            config.case_type
        )

        try:
            fields_to_update = importer_util.populate_updated_fields(
                config,
                columns,
                row
            )
        except importer_util.InvalidDateException:
            invalid_dates.append(i + 1)
            continue

        if case:
            pass
        elif error == LookupErrors.NotFound:
            if not config.create_new_cases:
                continue
        elif error == LookupErrors.MultipleResults:
            too_many_matches += 1
            continue

        uploaded_owner_id = fields_to_update.pop('owner_id', None)
        if uploaded_owner_id:
            # If an owner_id mapping exists, verify it is a valid user
            # or case sharing group
            if importer_util.is_valid_id(uploaded_owner_id, domain, id_cache):
                owner_id = uploaded_owner_id
                id_cache[uploaded_owner_id] = True
            else:
                owner_id_errors.append(i + 1)
                id_cache[uploaded_owner_id] = False
                continue
        else:
            # if they didn't supply an owner_id mapping, default to current
            # user
            owner_id = user_id

        external_id = fields_to_update.pop('external_id', None)
        parent_id = fields_to_update.pop('parent_id', None)
        parent_external_id = fields_to_update.pop('parent_external_id', None)

        extras = {}
        if parent_id:
            extras['index'] = {
                'parent': (config.case_type, parent_id)
            }
        elif parent_external_id:
            parent_case, error = importer_util.lookup_case(
                'external_id',
                parent_external_id,
                domain,
                config.case_type
            )
            if parent_case:
                extras['index'] = {
                    'parent': (config.case_type, parent_case._id)
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
                    user_id=user_id,
                    owner_id=owner_id,
                    case_type=config.case_type,
                    update=fields_to_update,
                    **extras
                )

                submit_case_block(caseblock, domain, username, user_id)
                created_count += 1
            except CaseBlockError:
                errors += 1
        elif case and case.type == config.case_type:
            if external_id:
                extras['external_id'] = external_id

            try:
                caseblock = CaseBlock(
                    create=False,
                    case_id=case._id,
                    owner_id=owner_id,
                    version=V2,
                    update=fields_to_update,
                    **extras
                )
                submit_case_block(caseblock, domain, username, user_id)
                match_count += 1
            except CaseBlockError:
                errors += 1

    return {
        'created_count': created_count,
        'match_count': match_count,
        'too_many_matches': too_many_matches,
        'blank_externals': blank_external_ids,
        'invalid_dates': invalid_dates,
        'owner_id_errors': owner_id_errors,
        'errors': errors,
    }

def submit_case_block(caseblock, domain, username, user_id):
    """ Convert a CaseBlock object to xml and submit for creation/update """
    casexml = ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime))
    submit_case_blocks(casexml, domain, username, user_id)
