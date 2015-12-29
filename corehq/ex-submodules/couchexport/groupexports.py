from couchexport.exceptions import SchemaMismatchException, ExportRebuildError
from couchexport.models import GroupExportConfiguration, SavedBasicExport
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from datetime import datetime
import os
import json
from couchexport.tasks import rebuild_schemas
from dimagi.utils.logging import notify_exception


def export_for_group(export_id_or_group, output_dir, last_access_cutoff=None):
    if isinstance(export_id_or_group, basestring):
        try:
            config = GroupExportConfiguration.get(export_id_or_group)
        except ResourceNotFound:
            raise Exception("Couldn't find an export with id %s" % export_id_or_group)
    else:
        config = export_id_or_group

    for subconfig, schema in config.all_exports:
        try:
            rebuild_export(subconfig, schema, output_dir, last_access_cutoff=last_access_cutoff)
        except ExportRebuildError:
            continue
        except Exception, e:
            notify_exception(None, 'Problem building export {} in domain {}: {}'.format(
                subconfig.index, getattr(config, 'domain', 'unknown'), e
            ))


def rebuild_export(config, schema, output_dir, last_access_cutoff=None, filter=None):
    if output_dir == "couch":
        saved = get_saved_export_and_delete_copies(config.index)
        if last_access_cutoff and saved and saved.last_accessed and \
                saved.last_accessed < last_access_cutoff:
            # ignore exports that haven't been accessed since last_access_cutoff
            return

    try:
        files = schema.get_export_files(format=config.format, filter=filter)
    except SchemaMismatchException:
        # fire off a delayed force update to prevent this from happening again
        rebuild_schemas.delay(config.index)
        raise ExportRebuildError(u'Schema mismatch for {}. Rebuilding tables...'.format(config.filename))

    with files:
        payload = files.file.payload
        if output_dir == "couch":
            if not saved:
                saved = SavedBasicExport(configuration=config)
            else:
                saved.configuration = config

            if saved.last_accessed is None:
                saved.last_accessed = datetime.utcnow()
            saved.last_updated = datetime.utcnow()
            try:
                saved.save()
            except ResourceConflict:
                return
            saved.set_payload(payload)
        else:
            with open(os.path.join(output_dir, config.filename), "wb") as f:
                f.write(payload)


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
