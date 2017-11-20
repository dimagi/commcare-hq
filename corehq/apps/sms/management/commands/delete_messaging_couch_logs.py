from __future__ import print_function
from __future__ import absolute_import
from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import (SMSLog, SMS, CallLog, LastReadMessage,
    ExpectedCallbackEventLog, ExpectedCallback)
from custom.fri.models import FRISMSLog
from dimagi.utils.couch.database import iter_docs_with_retry, iter_bulk_delete_with_doc_type_verification
from django.core.management.base import BaseCommand
import six


# Number of seconds to wait between each bulk delete operation
BULK_DELETE_INTERVAL = 5


class Command(BaseCommand):
    help = ("Deletes all messaging logs stored in couch")

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify",
            action="store_true",
            dest="verify",
            default=False,
            help="Include this option to double-check that all data "
                 "stored in couch is in postgres without deleting anything.",
        )
        parser.add_argument(
            "--delete-interval",
            action="store",
            dest="delete_interval",
            type=int,
            default=BULK_DELETE_INTERVAL,
            help="The number of seconds to wait between each bulk delete.",
        )

    def get_sms_couch_ids(self):
        result = SMSLog.view(
            'sms/by_domain',
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result if row['key'][1] == 'SMSLog']

    def get_call_couch_ids(self):
        result = CallLog.view(
            'sms/by_domain',
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result if row['key'][1] == 'CallLog']

    def get_callback_couch_ids(self):
        result = ExpectedCallbackEventLog.view(
            'sms/expected_callback_event',
            include_docs=False,
        ).all()
        return [row['id'] for row in result]

    def get_lastreadmessage_couch_ids(self):
        result = LastReadMessage.view(
            'sms/last_read_message',
            startkey=['by_anyone'],
            endkey=['by_anyone', {}],
            include_docs=False,
        ).all()
        return [row['id'] for row in result]

    def clean_doc(self, doc):
        """
        Some old docs apparently have +00:00Z at the end of the date string,
        which is not a valid timezone specification.

        Also, because of http://manage.dimagi.com/default.asp?111189, there's
        9 docs with very long phone numbers that should just be replaced
        with null because there was no recipient to those sms.
        """
        date = doc.get('date')
        if isinstance(date, six.string_types) and date.endswith('+00:00Z'):
            date = date[:-7] + 'Z'
            doc['date'] = date

        phone_number = doc.get('phone_number')
        if isinstance(phone_number, six.string_types) and len(phone_number) > 126:
            doc['phone_number'] = None

    def get_sms_compare_fields(self):
        return [
            'domain',
            'date',
            'couch_recipient_doc_type',
            'couch_recipient',
            'phone_number',
            'direction',
            'error',
            'system_error_message',
            'system_phone_number',
            'backend_api',
            'backend_id',
            'billed',
            'workflow',
            'xforms_session_couch_id',
            'reminder_id',
            'location_id',
            'messaging_subevent_id',
            'text',
            'raw_text',
            'datetime_to_process',
            'processed',
            'num_processing_attempts',
            'queued_timestamp',
            'processed_timestamp',
            'domain_scope',
            'ignore_opt_out',
            'backend_message_id',
            'chat_user_id',
            'invalid_survey_response',
            'fri_message_bank_lookup_completed',
            'fri_message_bank_message_id',
            'fri_id',
            'fri_risk_profile',
        ]

    def get_call_compare_fields(self):
        return [
            'domain',
            'date',
            'couch_recipient_doc_type',
            'couch_recipient',
            'phone_number',
            'direction',
            'error',
            'system_error_message',
            'system_phone_number',
            'backend_api',
            'backend_id',
            'billed',
            'workflow',
            'xforms_session_couch_id',
            'reminder_id',
            'location_id',
            'messaging_subevent_id',
            'answered',
            'duration',
            'gateway_session_id',
            'submit_partial_form',
            'include_case_side_effects',
            'max_question_retries',
            'current_question_retry_count',
            'xforms_session_id',
            'error_message',
            'use_precached_first_response',
            'first_response',
            'case_id',
            'case_for_case_submission',
            'form_unique_id',
        ]

    def get_expected_callback_compare_fields(self):
        return [
            'domain',
            'date',
            'couch_recipient_doc_type',
            'couch_recipient',
            'status',
        ]

    def verify_model(self, couch_ids, couch_model, sql_model, fields, log_file):
        log_file.write("Verifying %ss\n" % sql_model.__name__)
        count = 0
        total_count = len(couch_ids)
        for doc in iter_docs_with_retry(couch_model.get_db(), couch_ids):
            try:
                self.clean_doc(doc)
                couch_obj = couch_model.wrap(doc)
            except Exception:
                log_file.write('ERROR: Could wrap %s %s\n' % (couch_model.__name__, doc.get('_id')))
                continue

            try:
                sql_obj = sql_model.objects.get(couch_id=couch_obj._id)
            except sql_model.DoesNotExist:
                log_file.write('ERROR: Postgres record for %s with couch_id %s was not found\n' %
                    (sql_model.__name__, couch_obj._id))
                continue

            for field in fields:
                if getattr(couch_obj, field) != getattr(sql_obj, field):
                    log_file.write('ERROR: Mismatch found for %s with couch_id %s\n' %
                        (sql_model.__name__, couch_obj._id))
                    break

            count += 1
            if (count % 10000) == 0:
                print('Processed %s / %s %s documents' % (count, total_count, couch_model.__name__))

    def verify(self):
        with open('messaging_logs.txt', 'w') as f:
            self.verify_model(self.get_sms_couch_ids(), FRISMSLog, SMS, self.get_sms_compare_fields(), f)
            self.verify_model(self.get_call_couch_ids(), CallLog, Call, self.get_call_compare_fields(), f)
            self.verify_model(self.get_callback_couch_ids(), ExpectedCallbackEventLog, ExpectedCallback,
                self.get_expected_callback_compare_fields(), f)

    def delete_models(self, delete_interval):
        print('Deleting SMSLogs...')
        count = iter_bulk_delete_with_doc_type_verification(SMSLog.get_db(), self.get_sms_couch_ids(), 'SMSLog',
            wait_time=delete_interval, max_fetch_attempts=5)
        print('Deleted %s documents' % count)

        print('Deleting CallLogs...')
        count = iter_bulk_delete_with_doc_type_verification(CallLog.get_db(), self.get_call_couch_ids(), 'CallLog',
            wait_time=delete_interval, max_fetch_attempts=5)
        print('Deleted %s documents' % count)

        print('Deleting ExpectedCallbackEventLogs...')
        count = iter_bulk_delete_with_doc_type_verification(ExpectedCallbackEventLog.get_db(),
            self.get_callback_couch_ids(), 'ExpectedCallbackEventLog', wait_time=delete_interval,
            max_fetch_attempts=5)
        print('Deleted %s documents' % count)

        print('Deleting LastReadMessages...')
        count = iter_bulk_delete_with_doc_type_verification(LastReadMessage.get_db(),
            self.get_lastreadmessage_couch_ids(), 'LastReadMessage', wait_time=delete_interval,
            max_fetch_attempts=5)
        print('Deleted %s documents' % count)

    def handle(self, **options):
        if options['verify']:
            self.verify()
            return

        self.delete_models(options['delete_interval'])
