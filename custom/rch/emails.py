from django.conf import settings
from corehq.apps.hqwebapp.tasks import send_mail_async


def notify_parsing_error(for_date, state_id, beneficiary_type, district_id):
    subject = "[RCHServiceParsingError] [{for_date}] Issue with parsing RCH response".format(for_date=for_date)
    content = ("Unexpected response received for date:{for_date}, state_id:{s_id}, beneficiary_type:{bt}, "
               "district_id: {d_id}".format(for_date=for_date, s_id=state_id, bt=beneficiary_type,
                                            d_id=district_id))
    send_mail_async.delay(subject, content, settings.DEFAULT_FROM_EMAIL, ['mkangia@dimagi.com'])


def notify_insecure_access_response(for_date, state_id, beneficiary_type, district_id):
    subject = "[RCHServiceInsecureResponse] [{for_date}] RCH Insecure access response received".format(
        for_date=for_date)
    content = ("Insecure access response received for date:{for_date}, state_id:{s_id}, beneficiary_type:{bt}, "
               "district_id: {d_id}. Probably no updates in RCH for the requested date. Must check this if "
               "consecutively happening.".format(for_date=for_date, s_id=state_id, bt=beneficiary_type,
                                                 d_id=district_id))
    send_mail_async.delay(subject, content, settings.DEFAULT_FROM_EMAIL, ['mkangia@dimagi.com'])


def notify_error_in_service(message, for_date):
    subject = "[RCHServiceDown] [{for_date}] Unable to access RCH Service".format(for_date=for_date)
    content = "Error in RCH Service: {message}".format(message=message)
    send_mail_async.delay(subject, content, settings.DEFAULT_FROM_EMAIL, ['mkangia@dimagi.com'])
