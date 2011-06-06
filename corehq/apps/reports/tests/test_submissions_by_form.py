from datetime import datetime
from django.test.testcases import TestCase
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.reports.views import _relevant_form_types, submissions_by_form_json
from receiver.util import spoof_submission

def mk_xml_sub(userID, time, xmlns):
    return (time, """<data xmlns="{xmlns}">
        <meta>
            <userID>{userID}</userID>
        </meta>
    </data>""".format(userID=userID, xmlns=xmlns))

get_data = lambda mk_sub: [
    mk_sub('DANNY', "2011-05-20T12:00:00Z", "xmlns-A"),
    mk_sub('DANNY', "2011-05-20T12:00:01Z", "xmlns-B"),
    mk_sub('DANNY', "2011-05-20T12:00:02Z", "xmlns-B"),
    mk_sub('DANNY', "2011-05-20T12:00:03Z", "xmlns-A"),
    mk_sub('DANNY', "2011-05-23T12:00:00Z", "xmlns-A"),
    mk_sub('DANNY', "2011-05-23T12:00:01Z", "xmlns-B"),
    mk_sub('DANNY', "2011-05-23T12:00:02Z", "xmlns-A"),
]
DOMAIN = "test.domain"
class SubmissionsByFormTest(TestCase):
    def setUp(self):
        subs = get_data(mk_xml_sub)
        for time, xml in subs:
            spoof_submission(get_submit_url(DOMAIN), xml, hqsubmission=False, headers={
                "HTTP_X_SUBMIT_TIME": time
            })
    def test_relevant_form_types(self):
        self.failUnlessEqual(
            _relevant_form_types(DOMAIN, end=datetime(2011, 05, 24)),
            ["xmlns-A", "xmlns-B"]
        )
    def test__submissions_by_form_json(self):
        self.failUnlessEqual(
            submissions_by_form_json(
                DOMAIN,
                end=datetime(2011, 05, 24)
            ),
            {"DANNY": {"xmlns-A": 4, "xmlns-B": 3}}
        )