from unidecode import unidecode
from celery.decorators import task
from couchexport.shortcuts import get_export_files
from django.core.cache import cache
import uuid
from soil import CachedDownload, FileDownload
from couchexport.models import Format
import tempfile
import os
import stat



@task
def export_async(download_id, export_tag, format=None, filename=None,
                 previous_export_id=None, filter=None, 
                 expiry=10*60*60):
    
    if not filename:
        filename = export_tag
    
    (tmp, checkpoint) = get_export_files(export_tag, format, previous_export_id, filter)
    if checkpoint:
        temp_id = uuid.uuid4().hex
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:
            file.write(tmp.getvalue())
        # make file globally read/writeable in case celery runs as root
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | \
                 stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH) 
        format = Format.from_format(format)
        try:
            filename = unidecode(filename)
        except Exception: 
            pass
        cache.set(download_id, FileDownload(path, mimetype=format.mimetype,
                                            content_disposition='attachment; filename=%s.%s' % \
                                            (filename, format.extension),
                                            extras={'X-CommCareHQ-Export-Token': checkpoint.get_id}),
                                            expiry)
    else:
        temp_id = uuid.uuid4().hex
        cache.set(temp_id, "Sorry, there wasn't any data.", expiry)
        cache.set(download_id, CachedDownload(temp_id,content_disposition="", 
                                              mimetype="text/html"), expiry)
        
