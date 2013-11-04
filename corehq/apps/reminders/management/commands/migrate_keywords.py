from django.core.management.base import BaseCommand, CommandError
from corehq.apps.reminders.models import FORM_TYPE_ONE_BY_ONE, FORM_TYPE_ALL_AT_ONCE, SurveyKeyword, SurveyKeywordAction, RECIPIENT_SENDER, METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS
from datetime import datetime

class Command(BaseCommand):
    args = ""
    help = "Migrate keywords."

    def handle(self, *args, **options):
        keywords = SurveyKeyword.view("reminders/survey_keywords", reduce=False, include_docs=True).all()
        for keyword in keywords:
            if keyword.oct13_migration_timestamp is None:
                print "Processing keyword %s, %s" % (keyword.domain, keyword._id)
                keyword.description = "(none)"
                keyword.initiator_doc_type_filter = []
                if keyword.form_type == FORM_TYPE_ALL_AT_ONCE:
                    keyword.override_open_sessions = True
                    keyword.actions = [SurveyKeywordAction(
                        recipient = RECIPIENT_SENDER,
                        recipient_id = None,
                        action = METHOD_STRUCTURED_SMS,
                        message_content = None,
                        form_unique_id = keyword.form_unique_id,
                        use_named_args = keyword.use_named_args,
                        named_args = keyword.named_args,
                        named_args_separator = keyword.named_args_separator,
                    )]
                else:
                    keyword.override_open_sessions = False
                    keyword.actions = [SurveyKeywordAction(
                        recipient = RECIPIENT_SENDER,
                        recipient_id = None,
                        action = METHOD_SMS_SURVEY,
                        message_content = None,
                        form_unique_id = keyword.form_unique_id,
                    )]
                keyword.form_type = None
                keyword.form_unique_id = None
                keyword.use_named_args = None
                keyword.named_args = None
                keyword.named_args_separator = None

                keyword.oct13_migration_timestamp = datetime.utcnow()
                keyword.save()

