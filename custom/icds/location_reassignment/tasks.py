from django.conf import settings
from django.core.mail.message import EmailMessage

from celery.task import task

from custom.icds.location_reassignment.dumper import HouseHolds
from custom.icds.location_reassignment.processor import Processor


@task
def process_location_reassignment(domain, transitions, new_location_details, user_transitions,
                                  site_codes, user_email):
    try:
        Processor(domain, transitions, new_location_details, user_transitions, site_codes).process()
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


@task
def email_household_details(domain, transitions, user_email):
    try:
        filestream = HouseHolds(domain).dump(transitions)
    except Exception as e:
        email = EmailMessage(
            subject='[{}] - Location Reassignment Household Dump Failed'.format(settings.SERVER_ENVIRONMENT),
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
            subject='[{}] - Location Reassignment Household Dump Completed'.format(settings.SERVER_ENVIRONMENT),
            body="The request has been successfully completed.",
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        if filestream:
            email.attach(filename="Households.xlsx", content=filestream.read())
        else:
            email.body += "There were no house hold details found."
        email.send()
