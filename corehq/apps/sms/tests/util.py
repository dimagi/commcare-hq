import os
import json
from django.test import LiveServerTestCase
from django.conf import settings
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.dbaccessors import \
    get_one_case_in_domain_by_external_id
from corehq.apps.sms.test_backend import TestSMSBackend
from corehq.apps.sms.mixin import BackendMapping
from corehq.apps.sms.models import SMSLog, CallLog
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.groups.models import Group
from corehq.apps.reminders.models import (SurveyKeyword, SurveyKeywordAction,
    RECIPIENT_SENDER, METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS, METHOD_SMS)
from corehq.apps.app_manager.models import import_app
from corehq.apps.users.models import CommCareUser, WebUser
from django.contrib.sites.models import Site
from couchforms.dbaccessors import get_forms_by_type
from time import sleep
from dateutil.parser import parse
import uuid
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2


def time_parser(value):
    return parse(value).time()


class TouchformsTestCase(LiveServerTestCase):
    """
    For now, these test cases need to be run manually. Before running, the 
    following dependencies must be met:
        1. touchforms/backend/localsettings.py:
            URL_ROOT = "http://localhost:8081/a/{{DOMAIN}}"
        2. Django localsettings.py:
            TOUCHFORMS_API_USER = "touchforms_user"
            TOUCHFORMS_API_PASSWORD = "123"
        3. Start touchforms
    """

    users = None
    apps = None
    keywords = None
    groups = None

    def create_domain(self, domain):
        domain_obj = Domain(name=domain)
        domain_obj.use_default_sms_response = True
        domain_obj.default_sms_response = "Default SMS Response"
        domain_obj.save()

        generator.instantiate_accounting_for_tests()
        self.account = BillingAccount.get_or_create_account_by_domain(
            domain_obj.name,
            created_by="automated-test",
        )[0]
        plan = DefaultProductPlan.get_default_plan_by_domain(
            domain_obj, edition=SoftwarePlanEdition.ADVANCED
        )
        self.subscription = Subscription.new_domain_subscription(
            self.account,
            domain_obj.name,
            plan
        )
        self.subscription.is_active = True
        self.subscription.save()

        return domain_obj

    def create_mobile_worker(self, username, password, phone_number, save_vn=True):
        user = CommCareUser.create(self.domain, username, password,
            phone_number=phone_number)
        if save_vn:
            user.save_verified_number(self.domain, phone_number, True, None)
        self.users.append(user)
        return user

    def update_case_owner(self, case, owner):
        case_block = CaseBlock(
            create=False,
            case_id=case._id,
            case_type='participant',
            owner_id=owner._id,
            user_id=owner._id,
            version=V2
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})

    def add_parent_access(self, user, case):
        case_block = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            case_type='magic_map',
            owner_id=user._id,
            version=V2,
            index={'parent': ('participant', case._id)}
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})

    def create_web_user(self, username, password):
        user = WebUser.create(self.domain, username, password)
        self.users.append(user)
        return user

    def create_group(self, name, users):
        group = Group(
            domain=self.domain,
            name=name,
            users=[user._id for user in users],
            case_sharing=True,
        )
        group.save()
        self.groups.append(group)
        return group

    def load_app(self, filename, dirname=None):
        dirname = dirname or os.path.dirname(os.path.abspath(__file__))
        full_filename = "%s/%s" % (dirname, filename)
        with open(full_filename, "r") as f:
            app_source = f.read()
            app_source = json.loads(app_source)
        app = import_app(app_source, self.domain)
        self.apps.append(app)
        return app

    def create_sms_keyword(self, keyword, reply_sms,
        override_open_sessions=True, initiator_filter=None,
        recipient=RECIPIENT_SENDER, recipient_id=None):
        sk = SurveyKeyword(
            domain=self.domain,
            keyword=keyword,
            description=keyword,
            actions=[SurveyKeywordAction(
                recipient=recipient,
                recipient_id=recipient_id,
                action=METHOD_SMS,
                message_content=reply_sms,
                form_unique_id=None,
                use_named_args=False,
                named_args={},
                named_args_separator=None,
            )],
            delimiter=None,
            override_open_sessions=override_open_sessions,
            initiator_doc_type_filter=initiator_filter or [],
        )
        sk.save()
        self.keywords.append(sk)
        return sk

    def create_survey_keyword(self, keyword, form_unique_id, delimiter=None,
        override_open_sessions=True, initiator_filter=None):
        sk = SurveyKeyword(
            domain=self.domain,
            keyword=keyword,
            description=keyword,
            actions=[SurveyKeywordAction(
                recipient=RECIPIENT_SENDER,
                recipient_id=None,
                action=METHOD_SMS_SURVEY,
                message_content=None,
                form_unique_id=form_unique_id,
                use_named_args=False,
                named_args={},
                named_args_separator=None,
            )],
            delimiter=delimiter,
            override_open_sessions=override_open_sessions,
            initiator_doc_type_filter=initiator_filter or [],
        )
        sk.save()
        self.keywords.append(sk)
        return sk

    def create_structured_sms_keyword(self, keyword, form_unique_id, reply_sms,
        delimiter=None, named_args=None, named_args_separator=None,
        override_open_sessions=True, initiator_filter=None):
        sk = SurveyKeyword(
            domain=self.domain,
            keyword=keyword,
            description=keyword,
            actions=[
                SurveyKeywordAction(
                    recipient=RECIPIENT_SENDER,
                    recipient_id=None,
                    action=METHOD_SMS,
                    message_content=reply_sms,
                    form_unique_id=None,
                    use_named_args=False,
                    named_args={},
                    named_args_separator=None,
                ),
                SurveyKeywordAction(
                    recipient=RECIPIENT_SENDER,
                    recipient_id=None,
                    action=METHOD_STRUCTURED_SMS,
                    message_content=None,
                    form_unique_id=form_unique_id,
                    use_named_args=(named_args is not None),
                    named_args=(named_args or {}),
                    named_args_separator=named_args_separator,
                )
            ],
            delimiter=delimiter,
            override_open_sessions=override_open_sessions,
            initiator_doc_type_filter=initiator_filter or [],
        )
        sk.save()
        self.keywords.append(sk)
        return sk

    def create_site(self):
        site = Site(id=settings.SITE_ID, domain=self.live_server_url,
            name=self.live_server_url)
        site.save()
        return site

    def get_case(self, external_id):
        return get_one_case_in_domain_by_external_id(self.domain, external_id)

    def assertCasePropertyEquals(self, case, prop, value):
        self.assertEquals(case.get_case_property(prop), value)

    def get_last_form_submission(self):
        result = get_forms_by_type(self.domain, 'XFormInstance',
                                   recent_first=True, limit=1)
        return result[0] if len(result) > 0 else None

    def assertNoNewSubmission(self, last_submission):
        new_submission = self.get_last_form_submission()
        self.assertEquals(last_submission._id, new_submission._id)

    def assertFormQuestionEquals(self, form, question, value, cast=None):
        self.assertIn(question, form.form)
        form_value = form.form[question]
        if cast:
            form_value = cast(form_value)
        self.assertEquals(form_value, value)

    def get_last_outbound_sms(self, contact):
        # Not clear why this should be necessary, but without it the latest
        # sms may not be returned
        sleep(0.25)
        sms = SMSLog.view("sms/by_recipient",
            startkey=[contact.doc_type, contact._id, "SMSLog", "O", {}],
            endkey=[contact.doc_type, contact._id, "SMSLog", "O"],
            descending=True,
            include_docs=True,
            reduce=False,
        ).first()
        return sms

    def get_last_outbound_call(self, contact):
        # Not clear why this should be necessary, but without it the latest
        # call may not be returned
        sleep(0.25)
        call = CallLog.view("sms/by_recipient",
            startkey=[contact.doc_type, contact._id, "CallLog", "O", {}],
            endkey=[contact.doc_type, contact._id, "CallLog", "O"],
            descending=True,
            include_docs=True,
            reduce=False,
        ).first()
        return call

    def get_open_session(self, contact):
        return SQLXFormsSession.get_open_sms_session(self.domain, contact._id)

    def assertLastOutboundSMSEquals(self, contact, message):
        sms = self.get_last_outbound_sms(contact)
        self.assertIsNotNone(sms)
        self.assertEqual(sms.text, message)
        return sms

    def assertMetadataEqual(self, sms, xforms_session_couch_id=None, workflow=None):
        if xforms_session_couch_id:
            self.assertEqual(sms.xforms_session_couch_id, xforms_session_couch_id)
        if workflow:
            self.assertEqual(sms.workflow, workflow)

    def setUp(self):
        self.users = []
        self.apps = []
        self.keywords = []
        self.groups = []
        self.site = self.create_site()
        self.domain = "test-domain"
        self.domain_obj = self.create_domain(self.domain)
        self.create_web_user("touchforms_user", "123")

        self.backend = TestSMSBackend(name="TEST", is_global=True)
        self.backend.save()
        self.backend_mapping = BackendMapping(is_global=True, prefix="*",
            backend_id=self.backend._id)
        self.backend_mapping.save()

        settings.DEBUG = True

    def tearDown(self):
        for user in self.users:
            user.delete_verified_number()
            user.delete()
        for app in self.apps:
            app.delete()
        for keyword in self.keywords:
            keyword.delete()
        for group in self.groups:
            group.delete()
        self.domain_obj.delete()
        self.site.delete()
        self.backend.delete()
        self.backend_mapping.delete()
        SubscriptionAdjustment.objects.all().delete()
        self.subscription.delete()
        self.account.delete()
