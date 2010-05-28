# from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
# from django.http import HttpResponseRedirect
# from rapidsms.webui.utils import render_to_response

import os
import settings

from django_digest.decorators import *

from xml.dom.minidom import parse

@httpdigest
def restore(request):
    # username = request.user.username
    username = 'derik'
    search_str = "<username>%s</username>" % username
    
    atts_dir = settings.RAPIDSMS_APPS['receiver']['attachments_path']
    
    out = '''
    <restoredata>
        <username>ctsims</username>
    '''
    
    for f in os.listdir(atts_dir):
        if not f.endswith('.xml'): continue
        path = atts_dir + f
        contents = open(path).read()

        if search_str in contents and '<case>' in contents:
            dom = parse(path)
            cases = dom.getElementsByTagName("case")
            for case in cases:
                out += case.toprettyxml()
            
    out += "</restoredata>"
    
    return HttpResponse(out, mimetype="text/xml")