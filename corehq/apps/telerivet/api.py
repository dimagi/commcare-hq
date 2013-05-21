import os
import pycurl
import StringIO
import json
from urllib import urlencode
from corehq.apps.sms.util import clean_phone_number

API_ID = "TELERIVET"
MESSAGE_TYPE_SMS = "sms"

def send(msg, *args, **kwargs):
    """
    Expected kwargs:
        api_key     The api key of the account to send from.
        project_id  The Telerivet project id.
        phone_id    The id of the phone to send from, as shown on Telerivet's API page.
    """
    try:
        text = msg.text.encode("iso-8859-1")
    except UnicodeEncodeError:
        text = msg.text.encode("utf-8")
    params = urlencode({
        "phone_id" : kwargs["phone_id"],
        "to_number" : clean_phone_number(msg.phone_number),
        "content" : text,
        "message_type" : MESSAGE_TYPE_SMS,
    })
    url = "https://api.telerivet.com/v1/projects/%s/messages/outgoing" % kwargs["project_id"]
    
    curl = pycurl.Curl()
    buf = StringIO.StringIO()
    
    curl.setopt(curl.URL, url)
    curl.setopt(curl.USERPWD, "%s:" % kwargs["api_key"])
    curl.setopt(curl.WRITEFUNCTION, buf.write)
    curl.setopt(curl.POSTFIELDS, params)
    curl.setopt(curl.CAINFO, "%s/cacert.pem" % os.path.dirname(os.path.abspath(__file__)))
    curl.perform()
    curl.close()
    
    result = json.loads(buf.getvalue())
    buf.close()

