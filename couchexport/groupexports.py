from couchexport.models import GroupExportConfiguration, SavedBasicExport
from couchdbkit.exceptions import ResourceNotFound
from couchexport.export import export
from datetime import datetime
import os
import json
import tempfile

def export_for_group(export_id, output_dir):
    try:
        config = GroupExportConfiguration.get(export_id)
    except ResourceNotFound:
        raise Exception("Couldn't find an export with id %s" % export_id)
    
    for export_config in config.full_exports:
        # special case couch storage
        if output_dir == "couch":
            fd, path = tempfile.mkstemp()
            with os.fdopen(fd, 'wb') as f:
                export(export_config.index, f, format=export_config.format)
            # got the file, now rewrite it to couch
            saved = SavedBasicExport.view("couchexport/saved_exports", 
                                          key=json.dumps(export_config.index),
                                          include_docs=True,
                                          reduce=False).one()
            if not saved: 
                saved = SavedBasicExport(configuration=export_config)
                saved.save()
            with open(path, "rb") as f:
                saved.put_attachment(f.read(), export_config.filename)
                saved.last_updated = datetime.utcnow()
                saved.save()
            os.remove(path)
        else:
            with open(os.path.join(output_dir, export_config.filename), "wb") as f:
                export(export_config.index, f, format=export_config.format)
    