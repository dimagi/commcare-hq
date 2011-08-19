from django.http import HttpResponse
from StringIO import StringIO
from unidecode import unidecode
from django.core.cache import cache

def get_export_files(export_tag, format=None, previous_export_id=None, filter=None):
    # the APIs of how these methods are broken down suck, but at least
    # it's DRY
    
    from couchexport.export import export
    
    CACHE_TIME = 1 * 60 * 60 # cache for 1 hour, in seconds
    def _build_cache_key(tag, prev_export_id, format):
        return "couchexport_:%s:%s:%s" % (tag, prev_export_id, format)
    
    # check cache, only supported for filterless queries, currently
    if filter is None:
        cached_data = cache.get(_build_cache_key(export_tag, previous_export_id, format))
        if cached_data:
            (tmp, checkpoint) = cached_data
            return (tmp, checkpoint)
    

    tmp = StringIO()
    checkpoint = export(export_tag, tmp, format=format, 
                        previous_export_id=previous_export_id,
                        filter=filter)
    if checkpoint:
        cache.set(_build_cache_key(export_tag, previous_export_id, format), (tmp, checkpoint), CACHE_TIME)
        return (tmp, checkpoint)
    
    return (None, None) # hacky empty case
    
def export_data_shared(export_tag, format=None, filename=None,
                       previous_export_id=None, filter=None):
    """
    Shared method for export. If there is data, return an HTTPResponse
    with the appropriate data. If there is not data returns None.
    """
    from couchexport.export import export

    if not filename:
        filename = export_tag
    
    
    tmp, checkpoint = get_export_files(export_tag, format, 
                                       previous_export_id, filter)
    
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
    response['Content-Disposition'] = 'attachment; filename=%s.%s' % \
                                    (unidecode(filename), format.extension)
    if checkpoint:
        response['X-CommCareHQ-Export-Token'] = checkpoint.get_id
    response.write(file.getvalue())
    file.close()
    return response

