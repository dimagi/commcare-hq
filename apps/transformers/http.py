from django.http import HttpResponse
def responsify(type, string):
    """ returns the correct HttpResponse object for 
    a variety of content-types 
    
    """
    response = HttpResponse()
    if type == 'xml':
        response['mimetype'] = 'text/xml'
        response["content-disposition"] = 'attachment; filename="report.xml"'
        response.write(string)
    return response