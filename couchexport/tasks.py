from unidecode import unidecode
from celery.decorators import task
from couchexport.shortcuts import get_export_files
from django.core.cache import cache
import uuid
from soil import CachedDownload
from couchexport.models import Format



@task
def export_async(download_id, export_tag, format=None, filename=None,
                 previous_export_id=None, filter=None, 
                 expiry=10*60*60):
    
    (tmp, checkpoint) = get_export_files(export_tag, format, previous_export_id, filter)
    if checkpoint:
        temp_id = uuid.uuid4().hex
        cache.set(temp_id, tmp.getvalue(), expiry)
        format = Format.from_format(format)
        cache.set(download_id, CachedDownload(temp_id, mimetype=format.mimetype,
                                              content_disposition='attachment; filename=%s.%s' % \
                                              (unidecode(filename), format.extension),
                                               extras={'X-CommCareHQ-Export-Token': checkpoint.get_id}))
    else:
        temp_id = uuid.uuid4().hex
        cache.set(temp_id, "Sorry, there wasn't any data.", expiry)
        cache.set(download_id, CachedDownload(temp_id,content_disposition="", 
                                              mimetype="text/html"), expiry)
        
