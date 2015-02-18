from couchexport.exceptions import SchemaMismatchException, ExportRebuildError
from couchexport.models import GroupExportConfiguration, SavedBasicExport
from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime
import os
import json
from couchexport.tasks import rebuild_schemas


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


def rebuild_export(config, schema, output_dir, last_access_cutoff=None):
    if output_dir == "couch":
        saved = SavedBasicExport.view("couchexport/saved_exports",
                                      key=json.dumps(config.index),
                                      include_docs=True,
                                      reduce=False).one()
        if last_access_cutoff and saved and saved.last_accessed and \
                saved.last_accessed < last_access_cutoff:
            # ignore exports that haven't been accessed since last_access_cutoff
            return

    try:
        files = schema.get_export_files(format=config.format)
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
            saved.save()
            saved.set_payload(payload)
        else:
            with open(os.path.join(output_dir, config.filename), "wb") as f:
                f.write(payload)
