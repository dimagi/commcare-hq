from django.conf import settings

API_ID = "TEST"

def send(msg, *args, **kwargs):
    debug = getattr(settings, "DEBUG", False)
    if debug:
        print "***************************************************"
        print "Message To:      " + msg.phone_number
        print "Message Content: " + msg.text
        print "***************************************************"

