import urllib2
import logging
import json
import smtplib
from gmailloghandler import TLSSMTPHandler

# this is a simple uptime monitoring script to send alert emails
# when something goes wrong with a server. it monitors both:
#   - the reachability of the server; if the server cannot be
#     reached, an alert is sent
#   - custom diagnostic information sent from the server itself;
#     the script will forward this information along as an alert,
#     if present (e.g., a rapidsms server might send information
#     about the health of the 'route' process). if this information
#     cannot be retrieved/parsed, an alert is sent as well (this
#     protects against exceptions while generating the diagnostic
#     info on the server)

# this script should run frequently in a cron job, on a _different_
# server than the server being monitored

# url on the target server that returns diagnostic information, in
# json format. must conform to the format: {'errors': [...]}. the
# contents of the 'errors' array will be sent as alerts. the array
# will be empty if all is well
DIAG_URL = 'myserver.com/diagnostics/'

# recipients of the email alerts. pro-tip: most US cell providers
# have an email gateway to send SMSes to a phone # (details vary by
# provider)
RECIPIENTS = [
    'droos@dimagi.com',
]

# email the alerts will be sent from
SMTP_USER = 'asdf@dimagi.com'

# password for accessing the email account the alerts will be sent
# from
SMTP_PASS = FILLMEIN

def init_logging():
    root = logging.getLogger()
    root.setLevel(logging.ERROR)
    handler = TLSSMTPHandler(
        ('smtp.gmail.com', 587),
        'Uptime Monitor <uptime@dimagi.com>',
        RECIPIENTS,
        'add subject here',
        (SMTP_USER, SMTP_PASS)
    )
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
    root.addHandler(handler)
init_logging()

try:
    f = urllib2.urlopen(DIAG_URL, timeout=180)
    data = json.loads(f.read())
    errors = data['errors']

    if errors:
        logging.error('errors on server:\n\n' + '\n'.join(errors))
except Exception, e:
    logging.error('could not contact rapidsms server: %s %s' % (type(e), str(e)))




# EXAMPLE server view for generating diagnostics
def diagnostics(request):
    errors = []

    if the_system_is_down():
        errors.append('system down!')

    for x in get_stuff():
        if is_wrong(x):
            errors.append('x is wrong!! [%s]' % x)

    return HttpResponse(json.dumps({'errors': errors}), 'text/json')
