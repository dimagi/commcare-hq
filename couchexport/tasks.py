from celery.log import get_task_logger
from unidecode import unidecode
from celery.decorators import task
from django.core.cache import cache
import uuid
import zipfile
from soil import CachedDownload, FileDownload
from couchexport.models import Format, FakeCheckpoint
import tempfile
import os
import stat

logging = get_task_logger()

GLOBAL_RW = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH

@task
def export_async(custom_export, download_id, format=None, filename=None, **kwargs):
    tmp, checkpoint = custom_export.get_export_files(format=format, process=export_async, **kwargs)
    try:
        format = tmp.format
    except AttributeError:
        pass
    if not filename:
        filename = custom_export.name
    return cache_file_to_be_served(tmp, checkpoint, download_id, format, filename)

@task
def bulk_export_async(bulk_export_helper, download_id,
                      filename="bulk_export", expiry=10*60*60, domain=None):
    filename = "%s_%s"% (domain, filename) if domain else filename
    fd, path = tempfile.mkstemp()


    if bulk_export_helper.zip_export:
        zf = zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED)
        for file in bulk_export_helper.bulk_files:
            try:
                bulk = file.generate_bulk_file()
                zf.writestr("%s/%s" %(filename, file.filename), bulk.getvalue())
            except Exception as e:
                logging.error("FAILED to add file to bulk export archive. %s" % e)
        zf.close()

        os.chmod(path, GLOBAL_RW)

        cache.set(download_id, FileDownload(path, mimetype='application/zip',
                                        content_disposition='attachment; filename=%s.zip' %\
                                                            filename,
                                        extras={'X-CommCareHQ-Export-Token': bulk_export_helper.get_id}),
                                        expiry)
    else:
        export_object = bulk_export_helper.bulk_files[0]
        return cache_file_to_be_served(export_object.generate_bulk_file(),
            FakeCheckpoint(),
            download_id,
            filename=export_object.filename,
            format=export_object.format
        )

def cache_file_to_be_served(tmp, checkpoint, download_id, format=None, filename=None, expiry=10*60*60):
    if checkpoint:
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:
            file.write(tmp.getvalue())
        # make file globally read/writeable in case celery runs as root
        os.chmod(path, GLOBAL_RW)
        format = Format.from_format(format)
        try:
            filename = unidecode(filename)
        except Exception: 
            pass
        FileDownload(path,
            mimetype=format.mimetype,
            content_disposition='attachment; filename=%s.%s' % (filename, format.extension),
            extras={'X-CommCareHQ-Export-Token': checkpoint.get_id},
            download_id=download_id
        ).save(expiry)
    else:
        temp_id = uuid.uuid4().hex
        cache.set(temp_id, "Sorry, there wasn't any data.", expiry)
        CachedDownload(temp_id,
            content_disposition="",
            mimetype="text/html",
            download_id=download_id
        ).save(expiry)

