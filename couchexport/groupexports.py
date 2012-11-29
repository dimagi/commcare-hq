from couchexport.models import GroupExportConfiguration, SavedBasicExport,\
    SavedExportSchema
from couchdbkit.exceptions import ResourceNotFound
from couchexport.export import export
from datetime import datetime
import os
import json
from couchexport.tasks import Temp

def export_for_group(export_id, output_dir):
    try:
        config = GroupExportConfiguration.get(export_id)
    except ResourceNotFound:
        raise Exception("Couldn't find an export with id %s" % export_id)
    
    for config, schema in config.all_exports:
        tmp, _ = schema.get_export_files(format=config.format)
        payload = Temp(tmp).payload
        if output_dir == "couch":
            saved = SavedBasicExport.view("couchexport/saved_exports", 
                                          key=json.dumps(config.index),
                                          include_docs=True,
                                          reduce=False).one()
            if not saved: 
                saved = SavedBasicExport(configuration=config)
                saved.save()
        
            saved.put_attachment(payload, config.filename)
            saved.last_updated = datetime.utcnow()
            saved.save()
        else:
            with open(os.path.join(output_dir, config.filename), "wb") as f:
                f.write(payload)