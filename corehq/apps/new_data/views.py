from couchforms.models import XFormInstance
from corehq.util.webutils import render_to_response

def data(req, domain, template="new_data/data.html"):
    instances = XFormInstance.view('new_data/xforminstances', startkey=[domain], endkey=[domain, {}]).all()
    print instances
    return render_to_response(req, template, {
        'tab': 'data',
        'domain': domain,
        'instances': instances,
    })