from StringIO import StringIO
from django.test.client import RequestFactory
from corehq.apps.receiverwrapper import views as rcv_views

def submit_xform(url_path, domain, submission_xml_string, extra_meta=None):
    """
    RequestFactory submitter
    """
    rf = RequestFactory()
    f = StringIO(submission_xml_string.encode('utf-8'))
    f.name = 'form.xml'

    req = rf.post(url_path, data={'xml_submission_file': f}) #, content_type='multipart/form-data')
    if extra_meta:
        req.META.update(extra_meta)
    return rcv_views.post(req, domain)

