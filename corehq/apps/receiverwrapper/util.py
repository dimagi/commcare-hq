from StringIO import StringIO
from django.test.client import Client
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db

def spoof_submission(domain, body, name="form.xml"):
    client = Client()
    f = StringIO(body.encode('utf-8'))
    f.name = name
    response = client.post("/a/{domain}/receiver/".format(domain=domain), {
        'xml_submission_file': f,
    })
    xform_id = response['X-CommCareHQ-FormID']
    xform = XFormInstance.get(xform_id)
    xform['doc_type'] = "HQSubmission"
    xform.save()