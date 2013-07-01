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
    match_count = created_count = too_many_matches = 0
    blank_external_ids = []
    invalid_dates = []
    prime_offset = 1  # used to prevent back-to-back priming

    user = CouchUser.get_by_user_id(config.couch_user_id, domain)
    username = user.username
    user_id = user._id

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

        case, error = importer_util.lookup_case(config.search_field,
                                                search_id, domain)

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
            match_count += 1
        elif error == LookupErrors.NotFound:
            if not config.create_new_cases:
                continue
            created_count += 1
        elif error == LookupErrors.MultipleResults:
            too_many_matches += 1
            continue


        owner_id = get_property(fields_to_update, 'owner_id') or user_id
        external_id = get_property(fields_to_update, 'external_id')

        if not case:
            id = uuid.uuid4().hex

            caseblock = CaseBlock(
                create=True,
                case_id=id,
                version=V2,
                user_id=user_id,
                owner_id=owner_id,
                case_type=config.case_type,
                external_id=search_id if config.search_field == 'external_id' else '',
                update=fields_to_update
            )
            submit_case_block(caseblock, domain, username, user_id)
        elif case and case.type == config.case_type:
            caseblock = CaseBlock(
                create=False,
                case_id=case._id,
                owner_id=owner_id,
                version=V2,
                update=fields_to_update
            )
            if external_id:
                caseblock['external_id'] = external_id

            submit_case_block(caseblock, domain, username, user_id)

    return {
        'created_count': created_count,
        'match_count': match_count,
        'too_many_matches': too_many_matches,
        'blank_externals': blank_external_ids,
        'invalid_dates': invalid_dates,
    }

def get_property(fields, property_name):
    if property_name in fields:
        prop = fields[property_name]
        del fields[property_name]
        return prop
    else:
        return None

def submit_case_block(caseblock, domain, username, user_id):
    """ Convert a CaseBlock object to xml and submit for creation/update """
    casexml = ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime))
    submit_case_blocks(casexml, domain, username, user_id)
