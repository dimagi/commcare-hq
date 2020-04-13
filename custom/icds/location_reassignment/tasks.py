from django.conf import settings
from django.core.mail.message import EmailMessage

from celery.task import task

from custom.icds.location_reassignment.processor import Processor


@task
def process_location_reassignment(domain, transitions, new_location_details, site_codes, user_email):
    try:
        Processor(domain, transitions, new_location_details, site_codes).process()
    except Exception as e:
        email = EmailMessage(
            subject='[{}] - Location Reassignment Failed'.format(settings.SERVER_ENVIRONMENT),
            body="The request could not be completed. Something went wrong. "
                 "Error raised : {}. "
                 "Please report an issue if needed.".format(e),
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()
        raise e
    else:
        email = EmailMessage(
            subject='[{}] - Location Reassignment Completed'.format(settings.SERVER_ENVIRONMENT),
            body="The request has been successfully completed.",
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()
