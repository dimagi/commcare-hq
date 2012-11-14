import mechanize
import time
from hq_settings import HQTransaction
from datetime import datetime
from urlparse import urlparse
import httplib
import uuid

# ghetto
SUBMIT_TEMPLATE = """<?xml version='1.0'?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="http://www.commcarehq.org/loadtest">
    <meta>
        <deviceID>multimechanize</deviceID>
        <timeStart>%(timestart)s</timeStart>
        <timeEnd>%(timeend)s</timeEnd>
        <username>multimechanize</username>
        <userID>multimechanize</userID>
        <instanceID>%(instanceid)s</instanceID>
    </meta>
    %(extras)s
</data>"""

CASE_TEMPLATE = """
<case xmlns="http://commcarehq.org/case/transaction/v2" case_id="%(caseid)s"
        date_modified="%(moddate)s" user_id="multimechanize">
    <create>
        <case_type_id>loadtest</case_type_id>
        <case_name>load test case</case_name>
    </create>
    <update>
        <prop1>val1</prop1>
        <prop2>val2</prop2>
    </update>
</case>
"""

ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
def _format_datetime(time):
    return time.strftime(ISO_FORMAT)

def _submission(extras=""):
    return SUBMIT_TEMPLATE % {"timestart": _format_datetime(datetime.utcnow()),
                              "timeend": _format_datetime(datetime.utcnow()),
                              "instanceid": uuid.uuid4().hex,
                              "extras": extras }
def _case_submission():
    caseblock = CASE_TEMPLATE % {"moddate": _format_datetime(datetime.utcnow()),
                                 "caseid": uuid.uuid4().hex }
    return _submission(extras=caseblock)

def _post(data, url, content_type="text/xml"):
    headers = {"content-type": content_type,
               "content-length": len(data),
               }
            
    up = urlparse(url)
    conn = httplib.HTTPSConnection(up.netloc) if url.startswith("https") else httplib.HTTPConnection(up.netloc) 
    conn.request('POST', up.path, data, headers)
    return conn.getresponse()

class Transaction(HQTransaction):
    
    def run(self):
        submit = _case_submission()
        start_timer = time.time()
        url = "%s%s" % (self.base_url, "/a/%s/receiver" % self.domain) 
        resp = _post(submit, url)
        latency = time.time() - start_timer
        self.custom_timers['submission'] = latency  
        responsetext = resp.read()
        assert resp.status == 201, 'Bad HTTP Response'
        assert "Thanks for submitting" in responsetext, "Bad response text"

if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
