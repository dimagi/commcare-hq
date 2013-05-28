from celery.task import task
from xml.etree import ElementTree
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.importer.const import LookupErrors
import corehq.apps.importer.util as importer_util
from corehq.apps.users.models import CouchUser
from soil import DownloadBase
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
import uuid

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
    match_count = created_count = too_many_matches = 0

    for i in range(row_count):
        DownloadBase.set_progress(task, i, row_count)
        # skip first row if it is a header field
        if i == 0 and config.named_columns:
            continue

        row = spreadsheet.get_row(i)
        search_id = importer_util.parse_search_id(config, columns, row)
        case, error = importer_util.lookup_case(config.search_field,
                                                search_id, domain)

        if case:
            match_count += 1
        elif error == LookupErrors.NotFound:
            if not config.create_new_cases:
                continue
            created_count += 1
        elif error == LookupErrors.MultipleResults:
            too_many_matches += 1
            continue

        fields_to_update = importer_util.populate_updated_fields(config,
                                                                 columns, row)

        user = CouchUser.get_by_user_id(config.couch_user_id, domain)
        username = user.username
        user_id = user._id

        if not case:
            id = uuid.uuid4().hex
            owner_id = user_id

            caseblock = CaseBlock(
                create = True,
                case_id = id,
                version = V2,
                user_id = user_id,
                owner_id = owner_id,
                case_type = config.case_type,
                external_id = search_id if config.search_field == 'external_id' else '',
                update = fields_to_update
            )
            submit_case_block(caseblock, domain, username, user_id)
        elif case and case.type == config.case_type:
            caseblock = CaseBlock(
                create = False,
                case_id = case._id,
                version = V2,
                update = fields_to_update
            )
            submit_case_block(caseblock, domain, username, user_id)

    return {'created_count': created_count,
            'match_count': match_count,
            'too_many_matches': too_many_matches}

def submit_case_block(caseblock, domain, username, user_id):
    """ Convert a CaseBlock object to xml and submit for creation/update """
    casexml = ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime))
    submit_case_blocks(casexml, domain, username, user_id)
