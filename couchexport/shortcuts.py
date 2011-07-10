from django.http import HttpResponse
from StringIO import StringIO


def export_data_shared(export_tag, format=None,
                       filename=None):
    """
    Shared method for export. If there is data, return an HTTPResponse
    with the appropriate data. If there is not data returns None.
    """
    from couchexport.export import export

    if not filename:
        filename = export_tag
    
    tmp = StringIO()
    if export(export_tag, tmp, format=format):
        return export_response(tmp, format, filename)
        
    else: 
        return None
    
def export_response(file, format, filename):
    """
    Get an http response for an export
    """
    from couchexport.export import Format

    format = Format.from_format(format)
    response = HttpResponse(mimetype=format.mimetype)
    response['Content-Disposition'] = 'attachment; filename=%s.%s' % \
                                    (filename, format.extension)
    response.write(file.getvalue())
    file.close()
    return response

