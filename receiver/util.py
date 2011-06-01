from StringIO import StringIO
from django.test.client import Client
from couchforms.models import XFormInstance

def spoof_submission(submit_url, body, name="form.xml", hqsubmission=True, headers={}):
    client = Client()
    f = StringIO(body.encode('utf-8'))
    f.name = name
    response = client.post(submit_url, {
        'xml_submission_file': f,
    }, **headers)
    if hqsubmission:
        xform_id = response['X-CommCareHQ-FormID']
        xform = XFormInstance.get(xform_id)
        xform['doc_type'] = "HQSubmission"
        xform.save()
    return response