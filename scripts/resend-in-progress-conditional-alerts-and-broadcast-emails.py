from corehq.apps.sms.models import MessagingSubEvent
from corehq.apps.sms.models import Email
from corehq.apps.hqwebapp.tasks import send_mail_async
from datetime import date, datetime

bug_introduced_deploy_date = date(2023, 10, 18)
utc_one_hour_after_fix_deployed = datetime(2023, 10, 25, 20, 0, 0)

#can optionally do one domain at a time
subevents = MessagingSubEvent.objects.filter(
    status='PRG',
    date__gte=bug_introduced_deploy_date,
    date__lte=utc_one_hour_after_fix_deployed
)

for subevent in subevents:
    email = Email.objects.get(messaging_subevent=subevent.pk)

    subject = email.subject
    message = email.body
    recipient_list = [email.recipient_address]
    subevent_id = subevent.id
    domain = email.domain
    send_mail_async.delay(subject,
                          message,
                          recipient_list,
                          messaging_event_id=subevent_id,
                          domain=domain,
                          use_domain_gateway=True
                          )
