from couchexport.exceptions import SchemaMismatchException, ExportRebuildError
from couchexport.models import GroupExportConfiguration, SavedBasicExport
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from datetime import datetime
import os
import json
from couchexport.tasks import rebuild_schemas
from dimagi.utils.logging import notify_exception


def export_for_group(export_id_or_group, last_access_cutoff=None):
    if isinstance(export_id_or_group, basestring):
        try:
            config = GroupExportConfiguration.get(export_id_or_group)
        except ResourceNotFound:
            raise Exception("Couldn't find an export with id %s" % export_id_or_group)
    else:
        config = export_id_or_group

    for subconfig, schema in config.all_exports:
        try:
            rebuild_export(subconfig, schema, last_access_cutoff=last_access_cutoff)
        except ExportRebuildError:
            continue
        except Exception, e:
            notify_exception(None, 'Problem building export {} in domain {}: {}'.format(
                subconfig.index, getattr(config, 'domain', 'unknown'), e
            ))


def rebuild_export(config, schema, last_access_cutoff=None, filter=None):

    saved_export = get_saved_export_and_delete_copies(config.index)
    if _should_not_rebuild_export(saved_export, last_access_cutoff):
        return

    try:
        files = schema.get_export_files(format=config.format, filter=filter)
    except SchemaMismatchException:
        # fire off a delayed force update to prevent this from happening again
        rebuild_schemas.delay(config.index)
        raise ExportRebuildError(u'Schema mismatch for {}. Rebuilding tables...'.format(config.filename))

    with files:
        _save_export_payload(files, saved_export, config, is_safe=schema.is_safe)


def _save_export_payload(files, saved_export, config, is_safe=False):
    payload = files.file.payload
    if not saved_export:
        saved_export = SavedBasicExport(configuration=config)
    else:
        saved_export.configuration = config
    saved_export.is_safe = is_safe

    if saved_export.last_accessed is None:
        saved_export.last_accessed = datetime.utcnow()
    saved_export.last_updated = datetime.utcnow()
    try:
        saved_export.save()
    except ResourceConflict:
        # task was executed concurrently, so let first to finish win and abort the rest
        pass
    else:
        saved_export.set_payload(payload)


def _should_not_rebuild_export(saved, last_access_cutoff):
    # Don't rebuild exports that haven't been accessed since last_access_cutoff
    return (
        last_access_cutoff
        and saved
        and saved.last_accessed
        and saved.last_accessed < last_access_cutoff
    )


def get_saved_export_and_delete_copies(index):
    matching = SavedBasicExport.by_index(index)
    if not matching:
        return None
    if len(matching) == 1:
        return matching[0]
    else:
        # delete all matches besides the last updated match
        matching = sorted(matching, key=lambda x: x.last_updated)
        for match in matching[:-1]:
            match.delete()
        return matching[-1]
