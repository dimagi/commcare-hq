from celery.schedules import crontab
from celery.task import task
from corehq.apps.case_importer.exceptions import ImporterError
from corehq.apps.case_importer.tracking.analytics import \
    get_case_upload_files_total_bytes
from corehq.apps.case_importer.tracking.case_upload_tracker import CaseUpload
from corehq.apps.case_importer.util import get_importer_error_message
from corehq.util.datadog.gauges import datadog_gauge_task
from dimagi.utils.couch.database import is_bigcouch
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.case_importer.const import LookupErrors, ImportErrors
from corehq.apps.case_importer import util as importer_util
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dimagi.utils.prime_views import prime_views
from couchdbkit.exceptions import ResourceNotFound
from corehq.util.soft_assert import soft_assert
import uuid
from soil.progress import set_task_progress

POOL_SIZE = 10
PRIME_VIEW_FREQUENCY = 500
CASEBLOCK_CHUNKSIZE = 100


@task
def bulk_import_async(config, domain, excel_id):
    case_upload = CaseUpload.get(excel_id)
    try:
        case_upload.check_file()
    except ImporterError as e:
        return {'errors': get_importer_error_message(e)}

    try:
        with case_upload.get_spreadsheet() as spreadsheet:
            result = do_import(spreadsheet, config, domain, task=bulk_import_async,
                               record_form_callback=case_upload.record_form)
        # return compatible with soil
        return {
            'messages': result
        }
    except ImporterError as e:
        return {'errors': get_importer_error_message(e)}
    finally:
        store_task_result.delay(excel_id)


@task
def store_task_result(upload_id):
    case_upload = CaseUpload.get(upload_id)
    case_upload.store_task_result()


def do_import(spreadsheet, config, domain, task=None, chunksize=CASEBLOCK_CHUNKSIZE,
              record_form_callback=None):
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

    def _submit_caseblocks(domain, case_type, caseblocks):
        err = False
        if caseblocks:
            try:
                form, cases = submit_case_blocks(
                    [cb.as_string() for cb in caseblocks],
                    domain,
                    username,
                    user_id,
                )

                if form.is_error:
                    errors.add(
                        error=ImportErrors.ImportErrorMessage,
                        row_number=form.problem
                    )
            except Exception:
                err = True
                errors.add(
                    error=ImportErrors.ImportErrorMessage,
                    row_number=caseblocks[0].case_id
                )
            else:
                if record_form_callback:
                    record_form_callback(form.form_id)
                properties = set().union(*map(lambda c: set(c.dynamic_case_properties().keys()), cases))
                if case_type and len(properties):
                    add_inferred_export_properties.delay(
                        'CaseImporter',
                        domain,
                        case_type,
                        properties,
                    )
                else:
                    _soft_assert = soft_assert(notify_admins=True)
                    _soft_assert(
                        len(properties) == 0,
                        'error adding inferred export properties in domain '
                        '({}): {}'.format(domain, ", ".join(properties))
                    )
        return err

    row_count = spreadsheet.max_row
    for i, row in enumerate(spreadsheet.iter_rows()):
        if task:
            set_task_progress(task, i, row_count)

        # skip first row (header row)
        if i == 0:
            continue

        if not is_bigcouch():
            priming_progress = match_count + created_count + prime_offset
            if priming_progress % PRIME_VIEW_FREQUENCY == 0:
                prime_views(POOL_SIZE)
                # increment so we can't possibly prime on next iteration
                prime_offset += 1

        search_id = importer_util.parse_search_id(config, columns, row)

        fields_to_update = importer_util.populate_updated_fields(config, columns, row)
        if not any(fields_to_update.values()):
            # if the row was blank, just skip it, no errors
            continue

        if config.search_field == 'external_id' and not search_id:
            # do not allow blank external id since we save this
            errors.add(ImportErrors.BlankExternalId, i + 1)
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
            _submit_caseblocks(domain, config.case_type, caseblocks)
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
                errors.add(ImportErrors.InvalidOwnerName, i + 1, 'owner_name')
                continue
        if uploaded_owner_id:
            # If an owner_id mapping exists, verify it is a valid user
            # or case sharing group
            if importer_util.is_valid_id(uploaded_owner_id, domain, id_cache):
                owner_id = uploaded_owner_id
                id_cache[uploaded_owner_id] = True
            else:
                errors.add(ImportErrors.InvalidOwnerId, i + 1, 'owner_id')
                id_cache[uploaded_owner_id] = False
                continue
        else:
            # if they didn't supply an owner_id mapping, default to current
            # user
            owner_id = user_id

        extras = {}
        if parent_id:
            try:
                parent_case = CaseAccessors(domain).get_case(parent_id)

                if parent_case.domain == domain:
                    extras['index'] = {
                        parent_ref: (parent_case.type, parent_id)
                    }
            except ResourceNotFound:
                errors.add(ImportErrors.InvalidParentId, i + 1, 'parent_id')
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
                    parent_ref: (parent_type, parent_case.case_id)
                }

        case_name = fields_to_update.pop('name', None)
        if not case:
            id = uuid.uuid4().hex

            if config.search_field == 'external_id':
                extras['external_id'] = search_id

            try:
                caseblock = CaseBlock(
                    create=True,
                    case_id=id,
                    owner_id=owner_id,
                    user_id=user_id,
                    case_type=config.case_type,
                    case_name=case_name or '',
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
            if case_name is not None:
                extras['case_name'] = case_name

            try:
                caseblock = CaseBlock(
                    create=False,
                    case_id=case.case_id,
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
            _submit_caseblocks(domain, config.case_type, caseblocks)
            num_chunks += 1
            caseblocks = []

    # final purge of anything left in the queue
    if _submit_caseblocks(domain, config.case_type, caseblocks):
        match_count -= 1
    num_chunks += 1
    return {
        'created_count': created_count,
        'match_count': match_count,
        'too_many_matches': too_many_matches,
        'errors': errors.as_dict(),
        'num_chunks': num_chunks,
    }


total_bytes = datadog_gauge_task(
    'commcare.case_importer.files.total_bytes',
    get_case_upload_files_total_bytes,
    run_every=crontab(minute=0)
)
