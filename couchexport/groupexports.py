from couchexport.models import GroupExportConfiguration, SavedBasicExport
from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime
import os
import json
from couchexport.tasks import rebuild_schemas
from couchexport.export import SchemaMismatchException


def export_for_group(export_id_or_group, output_dir):
    if isinstance(export_id_or_group, basestring):
        try:
            config = GroupExportConfiguration.get(export_id_or_group)
        except ResourceNotFound:
            raise Exception("Couldn't find an export with id %s" % export_id_or_group)
    else:
        config = export_id_or_group

    for config, schema in config.all_exports:
        try:
            files = schema.get_export_files(format=config.format)
        except SchemaMismatchException, e:
            # fire off a delayed force update to prevent this from happening again
            rebuild_schemas.delay(config.index)
            continue

        payload = files.file.payload
        if output_dir == "couch":
            saved = SavedBasicExport.view("couchexport/saved_exports",
                                          key=json.dumps(config.index),
                                          include_docs=True,
                                          reduce=False).one()
            if not saved:
                saved = SavedBasicExport(configuration=config)
            else:
                saved.configuration = config
            saved.last_updated = datetime.utcnow()
            saved.save()
            saved.set_payload(payload)

        else:
            with open(os.path.join(output_dir, config.filename), "wb") as f:
                f.write(payload)
