from django.http import HttpResponse
from StringIO import StringIO
from unidecode import unidecode


def export_data_shared(export_tag, format=None, filename=None,
                       previous_export_id=None, filter=None):
    """
    Shared method for export. If there is data, return an HTTPResponse
    with the appropriate data. If there is not data returns None.
    """
    from couchexport.export import export

    if not filename:
        filename = export_tag
    
    tmp = StringIO()
    checkpoint = export(export_tag, tmp, format=format, 
                        previous_export_id=previous_export_id,
                        filter=filter)
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

