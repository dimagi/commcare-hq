from __future__ import absolute_import, unicode_literals

import uuid
from collections import namedtuple

from celery import states
from celery.exceptions import Ignore
from celery.schedules import crontab
from celery.task import task
from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.const import CASE_TAG_DATE_OPENED
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.const import ImportErrors, LookupErrors
from corehq.apps.case_importer.exceptions import ImporterError
from corehq.apps.case_importer.tracking.analytics import get_case_upload_files_total_bytes
from corehq.apps.case_importer.tracking.case_upload_tracker import CaseUpload
from corehq.apps.case_importer.util import get_importer_error_message
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.hqadmin.tasks import AbnormalUsageAlert, send_abnormal_usage_alert
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import BULK_UPLOAD_DATE_OPENED
from corehq.util.datadog.gauges import datadog_gauge_task
from corehq.util.datadog.utils import case_load_counter
from corehq.util.soft_assert import soft_assert
from soil.progress import set_task_progress, update_task_state

POOL_SIZE = 10
PRIME_VIEW_FREQUENCY = 500
CASEBLOCK_CHUNKSIZE = 100

RowAndCase = namedtuple('RowAndCase', ['row', 'case'])


@task(serializer='pickle', queue='case_import_queue')
def bulk_import_async(config, domain, excel_id):
    case_upload = CaseUpload.get(excel_id)
    try:
        case_upload.check_file()
    except ImporterError as e:
        update_task_state(bulk_import_async, states.FAILURE, {'errors': get_importer_error_message(e)})
        raise Ignore()

    try:
        with case_upload.get_spreadsheet() as spreadsheet:
            result = do_import(spreadsheet, config, domain, task=bulk_import_async,
                               record_form_callback=case_upload.record_form)

        _alert_on_result(result, domain)

        # return compatible with soil
        return {
            'messages': result
        }
    except ImporterError as e:
        update_task_state(bulk_import_async, states.FAILURE, {'errors': get_importer_error_message(e)})
        raise Ignore()
    finally:
        store_task_result.delay(excel_id)


@task(serializer='pickle', queue='case_import_queue')
def store_task_result(upload_id):
    case_upload = CaseUpload.get(upload_id)
    case_upload.store_task_result()


def do_import(spreadsheet, config, domain, task=None, chunksize=CASEBLOCK_CHUNKSIZE,
              record_form_callback=None):
    match_count = created_count = too_many_matches = num_chunks = 0
    errors = importer_util.ImportErrorDetail()

    user = CouchUser.get_by_user_id(config.couch_user_id, domain)
    username = user.username
    user_id = user._id

    # keep a cache of id lookup successes to help performance
    id_cache = {}
    name_cache = {}
    caseblocks = []
    ids_seen = set()
    track_load = case_load_counter("case_importer", domain)

    def _submit_caseblocks(domain, case_type, caseblocks):
        err = False
        if caseblocks:
            try:
                form, cases = submit_case_blocks(
                    [cb.case.as_string().decode('utf-8') for cb in caseblocks],
                    domain,
                    username,
                    user_id,
                    device_id=__name__ + ".do_import",
                )

                if form.is_error:
                    errors.add(
                        error=ImportErrors.ImportErrorMessage,
                        row_number=form.problem
                    )
            except Exception:
                err = True
                for row_number, case in caseblocks:
                    errors.add(
                        error=ImportErrors.ImportErrorMessage,
                        row_number=row_number
                    )
            else:
                if record_form_callback:
                    record_form_callback(form.form_id)
                properties = set().union(*[set(c.dynamic_case_properties().keys()) for c in cases])
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
    for i, row in enumerate(spreadsheet.iter_row_dicts()):
        if task:
            set_task_progress(task, i, row_count)

        # skip first row (header row)
        if i == 0:
            continue

        search_id = importer_util.parse_search_id(config, row)

        fields_to_update = importer_util.populate_updated_fields(config, row)
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
        track_load()

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
                track_load()

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
            track_load()
            if parent_case:
                extras['index'] = {
                    parent_ref: (parent_type, parent_case.case_id)
                }

        case_name = fields_to_update.pop('name', None)

        if BULK_UPLOAD_DATE_OPENED.enabled(domain):
            date_opened = fields_to_update.pop(CASE_TAG_DATE_OPENED, None)
            if date_opened:
                extras['date_opened'] = date_opened

        if not case:
            id = uuid.uuid4().hex

            if config.search_field == 'external_id':
                extras['external_id'] = search_id
            elif external_id:
                extras['external_id'] = external_id

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
                caseblocks.append(RowAndCase(i, caseblock))
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
                caseblocks.append(RowAndCase(i, caseblock))
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


def _alert_on_result(result, domain):
    """ Check import result and send internal alerts based on result

    :param result: dict that should include key "created_count" pointing to an int
    """

    if result['created_count'] > 10000:
        message = "A case import just uploaded {num} new cases to HQ. {domain} might be scaling operations".format(
            num=result['created_count'],
            domain=domain
        )
        alert = AbnormalUsageAlert(source="case importer", domain=domain, message=message)
        send_abnormal_usage_alert.delay(alert)


total_bytes = datadog_gauge_task(
    'commcare.case_importer.files.total_bytes',
    get_case_upload_files_total_bytes,
    run_every=crontab(minute=0)
)
