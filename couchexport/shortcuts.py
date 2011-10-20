import logging
from zipfile import ZipFile
from couchdbkit.ext.django.schema import Document
from django.http import HttpResponse
from StringIO import StringIO
from unidecode import unidecode
from couchforms.models import XFormInstance
from django.core.cache import cache
import hashlib

def get_export_files(export_tag, format=None, previous_export_id=None, filter=None,
                     use_cache=True, max_column_size=2000):
    # the APIs of how these methods are broken down suck, but at least
    # it's DRY
    
    from couchexport.export import export
    
    CACHE_TIME = 1 * 60 * 60 # cache for 1 hour, in seconds
    def _build_cache_key(tag, prev_export_id, format, max_column_size):
        def _human_readable_key(tag, prev_export_id, format, max_column_size):
            return "couchexport_:%s:%s:%s:%s" % (tag, prev_export_id, format, max_column_size)
        return hashlib.md5(_human_readable_key(tag, prev_export_id, 
                                               format, max_column_size)).hexdigest()
    
    # check cache, only supported for filterless queries, currently
    cache_key = _build_cache_key(export_tag, previous_export_id, 
                                 format, max_column_size)
    if use_cache and filter is None:
        cached_data = cache.get(cache_key)
        if cached_data:
            (tmp, checkpoint) = cached_data
            return (tmp, checkpoint)
    
    tmp = StringIO()
    checkpoint = export(export_tag, tmp, format=format, 
                        previous_export_id=previous_export_id,
                        filter=filter, max_column_size=max_column_size)
    if checkpoint:
        if use_cache:
            cache.set(cache_key, (tmp, checkpoint), CACHE_TIME)
        return (tmp, checkpoint)
    
    return (None, None) # hacky empty case
    
def export_data_shared(export_tag, format=None, filename=None,
                       previous_export_id=None, filter=None,
                       use_cache=True, max_column_size=2000):
    """
    Shared method for export. If there is data, return an HTTPResponse
    with the appropriate data. If there is not data returns None.
    """
    from couchexport.export import export

    if not filename:
        filename = export_tag
    
    tmp, checkpoint = get_export_files(export_tag, format, 
                                       previous_export_id, filter, 
                                       use_cache, max_column_size)
    
    if checkpoint:
        return export_response(tmp, format, filename, checkpoint)
    else: 
        return None
    
def export_response(file, format, filename, checkpoint=None):
    """
    Get an http response for an export
    """
    from couchexport.export import Format
    if not filename:
        filename = "NAMELESS EXPORT"
    
    format = Format.from_format(format)
    response = HttpResponse(mimetype=format.mimetype)

    try:
        filename = unidecode(filename)
    except Exception:
        logging.exception("Error with filename: %r" % filename)
        filename = "data"
    finally:
        response['Content-Disposition'] = 'attachment; filename={filename}.{format.extension}'.format(
            filename=filename,
            format=format
        )

    if checkpoint:
        response['X-CommCareHQ-Export-Token'] = checkpoint.get_id
    response.write(file.getvalue())
    file.close()
    return response

def export_raw_data(export_tag, filename=None):
                       
    xform_instances = XFormInstance.view('couchexport/schema_index', key=export_tag, include_docs=True)
    f = StringIO()
    zipfile = ZipFile(f, 'w')
    for xform_instance in xform_instances:
        form_xml = xform_instance.fetch_attachment('form.xml').encode('utf-8')
        zipfile.writestr("%s.xml" % xform_instance.get_id, form_xml)
    zipfile.close()
    f.flush()
    response = HttpResponse(f.getvalue())
    f.close()
    response['Content-Type'] = "application/zip"
    response['Content-Disposition'] = "attachment; filename=%s.zip" % filename
    return response
