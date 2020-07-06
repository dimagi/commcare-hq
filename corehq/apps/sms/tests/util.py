import json
import os
import uuid
from unittest import SkipTest

from django.conf import settings
from django.contrib.sites.models import Site
from django.test import LiveServerTestCase

from dateutil.parser import parse
from nose.tools import nottest

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.app_manager.models import import_app
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.sms.api import process_username
from corehq.apps.sms.models import (
    OUTGOING,
    SMS,
    Keyword,
    KeywordAction,
    PhoneNumber,
    SQLMobileBackend,
    SQLMobileBackendMapping,
)
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.util.test_utils import unit_testing_only


def time_parser(value):
    return parse(value).time()


@nottest
def setup_default_sms_test_backend():
    backend = SQLTestSMSBackend.objects.create(
        name='MOBILE_BACKEND_TEST',
        is_global=True,
        hq_api_id=SQLTestSMSBackend.get_api_id()
    )

    backend_mapping = SQLMobileBackendMapping.objects.create(
        is_global=True,
        backend_type=SQLMobileBackend.SMS,
        prefix='*',
        backend=backend,
    )

    return (backend, backend_mapping)


class BaseSMSTest(BaseAccountingTest, DomainSubscriptionMixin):

    def setUp(self):
        super(BaseSMSTest, self).setUp()
        self.account = None
        self.subscription = None

    @classmethod
    def create_account_and_subscription(cls, domain_name):
        cls.setup_subscription(domain_name, SoftwarePlanEdition.ADVANCED)

    def tearDown(self):
        self.teardown_subscriptions()
        clear_plan_version_cache()
        super(BaseSMSTest, self).tearDown()


class TouchformsTestCase(LiveServerTestCase, DomainSubscriptionMixin):
    """
    For now, these test cases need to be run manually. Before running, the
    following dependencies must be met:

        1. formplayer/config/application.properties:

            - Update these entries:
                commcarehq.host=http://localhost:8082
                commcarehq.formplayerAuthKey=abc
                touchforms.username=touchforms_user
                touchforms.password=123

            - Update couch.* and datasource.hq.* to point to the respective
              test databases

            - Make sure your local directory referenced by sqlite.dataDir is
              completely empty

        2. Start formplayer

        3. Django localsettings.py:
            FORMPLAYER_INTERNAL_AUTH_KEY = "abc"
    """
    users = None
    apps = None
    keywords = None
    groups = None

    # Always start the test live server on port 8082
    port = 8082

    def create_domain(self, domain):
        domain_obj = Domain(name=domain)
        domain_obj.use_default_sms_response = True
        domain_obj.default_sms_response = "Default SMS Response"
        domain_obj.save()

        self.setup_subscription(domain_obj.name, SoftwarePlanEdition.ADVANCED)
        return domain_obj

    def create_mobile_worker(self, username, password, phone_number, save_vn=True):
        processed_username = process_username(username, self.domain)
        user = CommCareUser.create(self.domain, processed_username, password, None, None,
            phone_number=phone_number)
        if save_vn:
            entry = user.get_or_create_phone_entry(phone_number)
            entry.set_two_way()
            entry.set_verified()
            entry.save()
        self.users.append(user)
        return user

    def update_case_owner(self, case, owner):
        case_block = CaseBlock.deprecated_init(
            create=False,
            case_id=case.case_id,
            case_type='participant',
            owner_id=owner.get_id,
            user_id=owner.get_id,
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})

    def add_parent_access(self, user, case):
        case_block = CaseBlock.deprecated_init(
            create=True,
            case_id=uuid.uuid4().hex,
            case_type='magic_map',
            owner_id=user.get_id,
            index={'parent': ('participant', case.case_id)}
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})

    def create_web_user(self, username, password):
        user = WebUser.create(self.domain, username, password, None, None)
        self.users.append(user)
        return user

    def create_group(self, name, users):
        group = Group(
            domain=self.domain,
            name=name,
            users=[user.get_id for user in users],
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
            recipient=KeywordAction.RECIPIENT_SENDER, recipient_id=None):

        k = Keyword(
            domain=self.domain,
            keyword=keyword,
            description=keyword,
            override_open_sessions=override_open_sessions,
            initiator_doc_type_filter=initiator_filter or [],
        )
        k.save()

        k.keywordaction_set.create(
            recipient=recipient,
            recipient_id=recipient_id,
            action=KeywordAction.ACTION_SMS,
            message_content=reply_sms,
        )

    def create_survey_keyword(self, keyword, app_id, form_unique_id, delimiter=None,
            override_open_sessions=True, initiator_filter=None):

        k = Keyword(
            domain=self.domain,
            keyword=keyword,
            description=keyword,
            delimiter=delimiter,
            override_open_sessions=override_open_sessions,
            initiator_doc_type_filter=initiator_filter or [],
        )
        k.save()

        k.keywordaction_set.create(
            recipient=KeywordAction.RECIPIENT_SENDER,
            action=KeywordAction.ACTION_SMS_SURVEY,
            app_id=app_id,
            form_unique_id=form_unique_id,
        )

    def create_structured_sms_keyword(self, keyword, app_id, form_unique_id, reply_sms,
            delimiter=None, named_args=None, named_args_separator=None,
            override_open_sessions=True, initiator_filter=None):

        k = Keyword(
            domain=self.domain,
            keyword=keyword,
            description=keyword,
            delimiter=delimiter,
            override_open_sessions=override_open_sessions,
            initiator_doc_type_filter=initiator_filter or [],
        )
        k.save()

        k.keywordaction_set.create(
            recipient=KeywordAction.RECIPIENT_SENDER,
            action=KeywordAction.ACTION_SMS,
            message_content=reply_sms,
        )

        k.keywordaction_set.create(
            recipient=KeywordAction.RECIPIENT_SENDER,
            action=KeywordAction.ACTION_STRUCTURED_SMS,
            app_id=app_id,
            form_unique_id=form_unique_id,
            use_named_args=(named_args is not None),
            named_args=(named_args or {}),
            named_args_separator=named_args_separator,
        )

    def create_site(self):
        site = Site(id=settings.SITE_ID, domain=self.live_server_url,
            name=self.live_server_url)
        site.save()
        return site

    def get_case(self, external_id):
        [case] = CaseAccessors(self.domain).get_cases_by_external_id(external_id)
        return case

    def assertCasePropertyEquals(self, case, prop, value):
        self.assertEqual(case.get_case_property(prop), value)

    def get_last_form_submission(self):
        result = FormAccessors(self.domain).get_forms_by_type('XFormInstance', 1, recent_first=True)
        return result[0] if len(result) > 0 else None

    def assertNoNewSubmission(self, last_submission):
        new_submission = self.get_last_form_submission()
        self.assertEqual(last_submission.form_id, new_submission.form_id)

    def assertFormQuestionEquals(self, form, question, value, cast=None):
        self.assertIn(question, form.form_data)
        form_value = form.form_data[question]
        if cast:
            form_value = cast(form_value)
        self.assertEqual(form_value, value)

    def get_last_outbound_sms(self, contact):
        return SMS.get_last_log_for_recipient(
            contact.doc_type,
            contact.get_id,
            direction=OUTGOING
        )

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

    @classmethod
    def setUpClass(cls):
        if getattr(settings, "SKIP_TOUCHFORMS_TESTS", False):
            raise SkipTest("because settings.SKIP_TOUCHFORMS_TESTS")

        super(TouchformsTestCase, cls).setUpClass()

    def setUp(self):
        self.users = []
        self.apps = []
        self.keywords = []
        self.groups = []
        self.site = self.create_site()
        self.domain = "test-domain"
        self.domain_obj = self.create_domain(self.domain)
        self.create_web_user("touchforms_user", "123")

        self.backend, self.backend_mapping = setup_default_sms_test_backend()

        settings.DEBUG = True

    def tearDown(self):
        delete_domain_phone_numbers(self.domain)
        for user in self.users:
            user.delete()
        for app in self.apps:
            app.delete()
        for keyword in self.keywords:
            keyword.delete()
        for group in self.groups:
            group.delete()
        self.domain_obj.delete()
        self.site.delete()
        self.backend_mapping.delete()
        self.backend.delete()
        self.teardown_subscriptions()
        clear_plan_version_cache()


@unit_testing_only
def delete_domain_phone_numbers(domain):
    for p in PhoneNumber.by_domain(domain):
        # Clear cache and delete
        p.delete()
