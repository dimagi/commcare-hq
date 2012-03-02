from django.core.management.base import LabelCommand, CommandError
from couchexport.models import GroupExportConfiguration, SavedBasicExport
from couchdbkit.exceptions import ResourceNotFound
from couchexport.export import export
from datetime import datetime
import os
import json
import tempfile

class Command(LabelCommand):
    help = "Runs an export based on a supplied configuration."
    args = "<id>, <output_location>"
    label = "Id of the saved export h, output directory for export files (use 'couch' for couch-based storage)."
     
    def handle(self, *args, **options):
        if len(args) < 2: raise CommandError('Please specify %s.' % self.label)
            
        export_id = args[0]
        output_dir = args[1]
        try:
            config = GroupExportConfiguration.get(export_id)
        except ResourceNotFound:
            raise CommandError("Couldn't find an export with id %s" % export_id)
        
        for export_config in config.full_exports:
            print "exporting %s to %s" % (export_config.name, output_dir)
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
                