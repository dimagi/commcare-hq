from celery.log import get_task_logger
from unidecode import unidecode
from celery.task import task
import uuid
import zipfile
from soil import CachedDownload, FileDownload
from couchexport.models import Format
import tempfile
import os
import stat
from django.conf import settings
from django.core import cache

logging = get_task_logger()

GLOBAL_RW = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH

EXPORT_METHOD = getattr(settings, 'COUCHEXPORT_METHOD', 'tmpfile')
EXPORT_CACHE_ID = getattr(settings, 'COUCHEXPORT_CACHE', 'default')
cache = cache.get_cache(EXPORT_CACHE_ID)

_EXPORT_METHOD_OPTIONS = ('cached', 'tmpfile')
if EXPORT_METHOD not in _EXPORT_METHOD_OPTIONS:
    raise ValueError("EXPORT_METHOD %r not recognized; must be one of %r" % (
        EXPORT_METHOD,
        ', '.join([repr(o) for o in _EXPORT_METHOD_OPTIONS])
    ))


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


    if bulk_export_helper.zip_export:
        filename = "%s_%s"% (domain, filename) if domain else filename
        _, path = tempfile.mkstemp()
        os.close(_) 
        zf = zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED)
        try: 
            for file in bulk_export_helper.bulk_files:
                try:
                    bulk = file.generate_bulk_file()
                    zf.writestr("%s/%s" %(filename, file.filename), bulk.getvalue())
                except Exception as e:
                    logging.error("FAILED to add file to bulk export archive. %s" % e)
        finally:
            zf.close()

        return cache_file_to_be_served(
            tmp=path,
            checkpoint=bulk_export_helper,
            download_id=download_id,
            filename=filename,
            format='zip',
            expiry=expiry
        )
    else:
        export_object = bulk_export_helper.bulk_files[0]
        return cache_file_to_be_served(
            tmp=export_object.generate_bulk_file(),
            checkpoint=bulk_export_helper,
            download_id=download_id,
            filename=export_object.filename,
            format=export_object.format,
            expiry=expiry
        )

def Temp(tmp):
    cls = PathTemp if isinstance(tmp, basestring) else StringIOTemp
    return cls(tmp)

class PathTemp(object):
    def __init__(self, path):
        self.path = path

    @property
    def payload(self):
        with open(self.path, 'rb') as f:
            return f.read()

class StringIOTemp(object):
    def __init__(self, buffer):
        self.buffer = buffer

    @property
    def payload(self):
        return self.buffer.getvalue()

    @property
    def path(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:
            file.write(self.buffer.getvalue())
        return path

def cache_file_to_be_served(tmp, checkpoint, download_id, format=None, filename=None, expiry=10*60*60):
    """
    tmp can be either either a path to a tempfile or a StringIO
    (the APIs for tempfiles vs StringIO are unfortunately... not similar)
    """
    if checkpoint:
        format = Format.from_format(format)
        try:
            filename = unidecode(filename)
        except Exception: 
            pass

        tmp = Temp(tmp)

        def expose_download(cls, key):
            cls(
                key,
                mimetype=format.mimetype,
                content_disposition='attachment; filename=%s.%s' % (filename, format.extension),
                extras={'X-CommCareHQ-Export-Token': checkpoint.get_id},
                download_id=download_id,
                cache_backend=EXPORT_CACHE_ID,
            ).save(expiry)

        if EXPORT_METHOD == "cached":
            download_stream = "%s_stream" % download_id
            payload = tmp.payload
            cache.set(download_stream, payload, expiry)
            expose_download(CachedDownload, download_stream)
        elif EXPORT_METHOD == 'tmpfile':
            path = tmp.path
            # make file globally read/writeable in case celery runs as root
            os.chmod(path, GLOBAL_RW)
            expose_download(FileDownload, path)
    else:
        temp_id = uuid.uuid4().hex
        cache.set(temp_id, "Sorry, there wasn't any data.", expiry)
        CachedDownload(temp_id,
            content_disposition="",
            mimetype="text/html",
            download_id=download_id
        ).save(expiry)

