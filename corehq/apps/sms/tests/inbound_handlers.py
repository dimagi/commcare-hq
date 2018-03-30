from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.hqcase.utils import update_case
from corehq.apps.sms.api import incoming
from corehq.apps.sms.models import WORKFLOW_KEYWORD
from corehq.apps.sms.tests.util import TouchformsTestCase, time_parser
from corehq.apps.reminders.models import (RECIPIENT_OWNER, RECIPIENT_USER_GROUP)
from corehq.apps.sms.messages import *
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from datetime import date, time
from mock import patch


class MockContextManager(object):

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def mock_critical_section_for_smsforms_sessions(contact_id):
    return MockContextManager()


@patch('corehq.apps.smsforms.util.critical_section_for_smsforms_sessions',
       new=mock_critical_section_for_smsforms_sessions)
class KeywordTestCase(TouchformsTestCase):
    """
    Must be run manually (see util.TouchformsTestCase)
    """

    def setUp(self):
        from django.core.management import call_command
        call_command('cchq_prbac_bootstrap')
        super(KeywordTestCase, self).setUp()
        self.app = self.load_app("app_source.json")
        self.create_survey_keyword("REG", self.app.modules[0].forms[0].unique_id, override_open_sessions=False)
        self.create_survey_keyword("MOD", self.app.modules[0].forms[1].unique_id)
        self.create_survey_keyword("VALIDATION_TEST", self.app.modules[0].forms[2].unique_id)
        self.create_structured_sms_keyword(
            "REG_SS",
            self.app.modules[0].forms[0].unique_id,
            "Thank you for your registration submission.",
        )
        self.create_structured_sms_keyword(
            "MOD_SS",
            self.app.modules[0].forms[1].unique_id,
            "Thank you for your modification submission.",
        )
        self.create_structured_sms_keyword(
            "MOD_SS_2",
            self.app.modules[0].forms[1].unique_id,
            "Thank you for your modification submission.",
            delimiter=",",
        )
        self.create_structured_sms_keyword(
            "MOD_SS_3",
            self.app.modules[0].forms[1].unique_id,
            "Thank you for your modification submission.",
            delimiter=",",
            named_args={
                "ARM": "/data/arm",
            },
            named_args_separator="=",
        )
        self.create_structured_sms_keyword(
            "VALIDATION_TEST_SS_1",
            self.app.modules[0].forms[2].unique_id,
            "Thank you for your submission.",
        )
        self.create_structured_sms_keyword(
            "VALIDATION_TEST_SS_2",
            self.app.modules[0].forms[2].unique_id,
            "Thank you for your submission.",
            delimiter=",",
        )
        self.create_structured_sms_keyword(
            "VALIDATION_TEST_SS_3",
            self.app.modules[0].forms[2].unique_id,
            "Thank you for your submission.",
            delimiter=",",
            named_args={
                "ARG1": "/data/q_text",
                "ARG2": "/data/q_single_select",
                "ARG3": "/data/q_multi_select",
                "ARG4": "/data/q_int",
                "ARG5": "/data/q_float",
                "ARG6": "/data/q_long",
                "ARG7": "/data/q_date",
                "ARG8": "/data/q_time",
            },
        )
        self.create_structured_sms_keyword(
            "VALIDATION_TEST_SS_4",
            self.app.modules[0].forms[2].unique_id,
            "Thank you for your submission.",
            delimiter=",",
            named_args={
                "ARG1": "/data/q_text",
                "ARG2": "/data/q_single_select",
                "ARG3": "/data/q_multi_select",
                "ARG4": "/data/q_int",
                "ARG5": "/data/q_float",
                "ARG6": "/data/q_long",
                "ARG7": "/data/q_date",
                "ARG8": "/data/q_time",
            },
            named_args_separator="=",
        )
        self.create_sms_keyword("FOR_USER", "This message is for users",
            initiator_filter=["CommCareUser"])
        self.create_sms_keyword("FOR_CASE", "This message is for cases",
            initiator_filter=["CommCareCase"])
        self.user1 = self.create_mobile_worker("abcd", "123", "999123")
        self.user2 = self.create_mobile_worker("efgh", "122", "999122")
        self.user3 = self.create_mobile_worker("xyz", "121", "999121")
        self.group1 = self.create_group("group1", [self.user1, self.user2])
        self.create_sms_keyword("FOR_OWNER", "This message is for the case owner",
            initiator_filter=["CommCareCase"], recipient=RECIPIENT_OWNER)
        self.create_sms_keyword("FOR_GROUP", "This message is for the group",
            initiator_filter=["CommCareCase"], recipient=RECIPIENT_USER_GROUP,
            recipient_id=self.group1._id)

    def test_all_inbound(self):
        # Mobile worker creates a case
        incoming("999123", "reg", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Participant ID")
        incoming("999123", "pid1234", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        incoming("999123", "1", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "participant_id", "pid1234")
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        self.assertFormQuestionEquals(form, "external_id", "pid1234")
        case = self.get_case("pid1234")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "name", "pid1234")
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Mobile worker modifies a case
        incoming("999123", "mod pid1234", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        incoming("999123", "b", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_b")
        case = self.get_case("pid1234")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        # now take the case away from the user
        self.update_case_owner(case, self.user3)
        case = self.get_case("pid1234")

        # then they should no longer have access
        incoming("999123", "mod pid1234", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_CASE_NOT_FOUND))

        # now add access back via parent connection
        self.add_parent_access(self.user1, case)
        incoming("999123", "mod pid1234", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        incoming("999123", "a", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        case = self.get_case("pid1234")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        form = self.get_last_form_submission()

        # Bad external id
        incoming("999123", "mod pid1235", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_CASE_NOT_FOUND))
        self.assertNoNewSubmission(form)

        # No external id
        incoming("999123", "mod", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_MISSING_EXTERNAL_ID))
        self.assertNoNewSubmission(form)

        # Test validation on all fields
        incoming("999123", "Validation_Test", "TEST")
        session = self.get_open_session(self.user1)
        
        sms = self.assertLastOutboundSMSEquals(self.user1, "text")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "ab", "TEST")
        self.assertTrue(sms.invalid_survey_response)
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, 'Expected "abc"')
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "abc", "TEST")
        self.assertFalse(sms.invalid_survey_response)
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "single select 1:a, 2:b, 3:c, 4:d.")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "x", "TEST")
        self.assertTrue(sms.invalid_survey_response)
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s single select 1:a, 2:b, 3:c, 4:d." % get_message(MSG_INVALID_CHOICE))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "5", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s single select 1:a, 2:b, 3:c, 4:d." % get_message(MSG_CHOICE_OUT_OF_RANGE))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "2", "TEST")
        self.assertFalse(sms.invalid_survey_response)
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "multi select 1:a, 2:b, 3:c, 4:d.")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s multi select 1:a, 2:b, 3:c, 4:d." % get_message(MSG_FIELD_REQUIRED))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "2 x", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s multi select 1:a, 2:b, 3:c, 4:d." % get_message(MSG_INVALID_CHOICE))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "1 5", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s multi select 1:a, 2:b, 3:c, 4:d." % get_message(MSG_INVALID_CHOICE))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "1 c", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "int")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "x", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s int" % get_message(MSG_INVALID_INT))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "50", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "float")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "x", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s float" % get_message(MSG_INVALID_FLOAT))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "21.3", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)
        
        sms = self.assertLastOutboundSMSEquals(self.user1, "long")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "x", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s long" % get_message(MSG_INVALID_LONG))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "-100", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "date")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "x", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s date" %
            get_message(MSG_INVALID_DATE, context=('YYYYMMDD',)))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "20140101", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "time")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "x", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s time" % get_message(MSG_INVALID_TIME))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "2500", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = self.assertLastOutboundSMSEquals(self.user1, "%s time" % get_message(MSG_INVALID_TIME))
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        sms = incoming("999123", "2345", "TEST")
        self.assertMetadataEqual(sms, session._id, WORKFLOW_KEYWORD)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "b")
        self.assertFormQuestionEquals(form, "q_multi_select", "a c")
        self.assertFormQuestionEquals(form, "q_int", 50, cast=int)
        self.assertFormQuestionEquals(form, "q_float", 21.3, cast=float)
        self.assertFormQuestionEquals(form, "q_long", -100, cast=int)
        self.assertFormQuestionEquals(form, "q_date", '2014-01-01')
        self.assertFormQuestionEquals(form, "q_time", time(23, 45), cast=time_parser)

        # Mobile worker creates a case via structured sms
        incoming("999123", "reg_ss pid1235 1", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your registration submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "participant_id", "pid1235")
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        self.assertFormQuestionEquals(form, "external_id", "pid1235")
        case = self.get_case("pid1235")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "name", "pid1235")
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Mobile worker modifies a case
        incoming("999123", "mod_ss pid1235 b", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your modification submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_b")
        case = self.get_case("pid1235")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        # Bad external id
        incoming("999123", "mod_ss pid1236", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_CASE_NOT_FOUND))
        self.assertNoNewSubmission(form)

        # No external id
        incoming("999123", "mod_ss", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_MISSING_EXTERNAL_ID))
        self.assertNoNewSubmission(form)

        def get_field_and_message(field_name, msg_id, additional_context=None):
            msg1 = get_message(MSG_FIELD_DESCRIPTOR, context=(field_name,))
            msg2 = get_message(msg_id, context=additional_context)
            return "%s%s" % (msg1, msg2)

        # Test validation on all fields from structured sms: positional args
        incoming("999123", "validation_test_ss_1 ab 2 c 50 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, 'Expected "abc"')
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc x c 50 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_single_select", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 5 c 50 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_single_select", MSG_CHOICE_OUT_OF_RANGE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 x 50 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_multi_select", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 5 50 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_multi_select", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c x 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_int", MSG_INVALID_INT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c 50 x -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_float", MSG_INVALID_FLOAT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c 50 21.3 x 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_long", MSG_INVALID_LONG))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c 50 21.3 -100 x 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1,
            get_field_and_message("q_date", MSG_INVALID_DATE, ('YYYYMMDD',)))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c 50 21.3 -100 20140101 x", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_time", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c 50 21.3 -100 20140101 2500", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_time", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_1 abc 2 c 50 21.3 -100 20140101 2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "b")
        self.assertFormQuestionEquals(form, "q_multi_select", "c")
        self.assertFormQuestionEquals(form, "q_int", 50, cast=int)
        self.assertFormQuestionEquals(form, "q_float", 21.3, cast=float)
        self.assertFormQuestionEquals(form, "q_long", -100, cast=int)
        self.assertFormQuestionEquals(form, "q_date", '2014-01-01')
        self.assertFormQuestionEquals(form, "q_time", time(23, 45), cast=time_parser)

        # Test validation on all fields from structured sms: positional args with custom delimiter
        incoming("999123", "validation_test_ss_2,ab,2,1 c,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, 'Expected "abc"')
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,x,1 c,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_single_select", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,5,1 c,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_single_select", MSG_CHOICE_OUT_OF_RANGE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 x,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_multi_select", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 5,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_multi_select", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_multi_select", MSG_FIELD_REQUIRED))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,x,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_int", MSG_INVALID_INT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,50,x,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_float", MSG_INVALID_FLOAT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,50,21.3,x,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_long", MSG_INVALID_LONG))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,50,21.3,-100,x,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1,
            get_field_and_message("q_date", MSG_INVALID_DATE, ('YYYYMMDD',)))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,50,21.3,-100,20140101,x", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_time", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,50,21.3,-100,20140101,2500", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("q_time", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_2,abc,2,1 c,50,21.3,-100,20140101,2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "b")
        self.assertFormQuestionEquals(form, "q_multi_select", "a c")
        self.assertFormQuestionEquals(form, "q_int", 50, cast=int)
        self.assertFormQuestionEquals(form, "q_float", 21.3, cast=float)
        self.assertFormQuestionEquals(form, "q_long", -100, cast=int)
        self.assertFormQuestionEquals(form, "q_date", '2014-01-01')
        self.assertFormQuestionEquals(form, "q_time", time(23, 45), cast=time_parser)

        # Test validation on all fields from structured sms: named args with custom delimiter
        incoming("999123", "validation_test_ss_3,arg1ab,arg22,arg31 c,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, 'Expected "abc"')
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg2x,arg31 c,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG2", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg25,arg31 c,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG2", MSG_CHOICE_OUT_OF_RANGE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 x,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG3", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 5,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG3", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg3,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG3", MSG_FIELD_REQUIRED))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg4x,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG4", MSG_INVALID_INT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg450,arg5x,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG5", MSG_INVALID_FLOAT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg450,arg521.3,arg6x,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG6", MSG_INVALID_LONG))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg450,arg521.3,arg6-100,arg7x,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1,
            get_field_and_message("ARG7", MSG_INVALID_DATE, ('YYYYMMDD',)))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg450,arg521.3,arg6-100,arg720140101,arg8x", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG8", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg450,arg521.3,arg6-100,arg720140101,arg82500", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG8", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_3,arg1abc,arg22,arg31 c,arg450,arg521.3,arg6-100,arg720140101,arg82345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "b")
        self.assertFormQuestionEquals(form, "q_multi_select", "a c")
        self.assertFormQuestionEquals(form, "q_int", 50, cast=int)
        self.assertFormQuestionEquals(form, "q_float", 21.3, cast=float)
        self.assertFormQuestionEquals(form, "q_long", -100, cast=int)
        self.assertFormQuestionEquals(form, "q_date", '2014-01-01')
        self.assertFormQuestionEquals(form, "q_time", time(23, 45), cast=time_parser)

        # Test validation on all fields from structured sms: named args with custom delimiter and joining character
        incoming("999123", "validation_test_ss_4,arg1=ab,arg2=2,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, 'Expected "abc"')
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=x,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG2", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=5,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG2", MSG_CHOICE_OUT_OF_RANGE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 x,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG3", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 5,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG3", MSG_INVALID_CHOICE))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG3", MSG_FIELD_REQUIRED))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=x,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG4", MSG_INVALID_INT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=50,arg5=x,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG5", MSG_INVALID_FLOAT))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=50,arg5=21.3,arg6=x,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG6", MSG_INVALID_LONG))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=x,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1,
            get_field_and_message("ARG7", MSG_INVALID_DATE, ('YYYYMMDD',)))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=x", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG8", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2500", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARG8", MSG_INVALID_TIME))
        self.assertNoNewSubmission(form)
        incoming("999123", "validation_test_ss_4,arg1=abc,arg2=2,arg3=1 c,arg4=50,arg5=21.3,arg6=-100,arg7=20140101,arg8=2345", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "b")
        self.assertFormQuestionEquals(form, "q_multi_select", "a c")
        self.assertFormQuestionEquals(form, "q_int", 50, cast=int)
        self.assertFormQuestionEquals(form, "q_float", 21.3, cast=float)
        self.assertFormQuestionEquals(form, "q_long", -100, cast=int)
        self.assertFormQuestionEquals(form, "q_date", '2014-01-01')
        self.assertFormQuestionEquals(form, "q_time", time(23, 45), cast=time_parser)

        # Test leaving fields blank via structured sms
        incoming("999123", "validation_test_ss_4,arg1=abc,arg3=1 c", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "")
        self.assertFormQuestionEquals(form, "q_multi_select", "a c")
        self.assertFormQuestionEquals(form, "q_int", "")
        self.assertFormQuestionEquals(form, "q_float", "")
        self.assertFormQuestionEquals(form, "q_long", "")
        self.assertFormQuestionEquals(form, "q_date", "")
        self.assertFormQuestionEquals(form, "q_time", "")

        incoming("999123", "validation_test_ss_1 abc b c", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "q_text", "abc")
        self.assertFormQuestionEquals(form, "q_single_select", "b")
        self.assertFormQuestionEquals(form, "q_multi_select", "c")
        self.assertFormQuestionEquals(form, "q_int", "")
        self.assertFormQuestionEquals(form, "q_float", "")
        self.assertFormQuestionEquals(form, "q_long", "")
        self.assertFormQuestionEquals(form, "q_date", "")
        self.assertFormQuestionEquals(form, "q_time", "")

        incoming("999123", "mod_ss_2,pid1235", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("arm", MSG_FIELD_REQUIRED))
        self.assertNoNewSubmission(form)

        incoming("999123", "mod_ss_2,pid1235,", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("arm", MSG_FIELD_REQUIRED))
        self.assertNoNewSubmission(form)

        incoming("999123", "mod_ss_3,pid1235,arm=", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_field_and_message("ARM", MSG_FIELD_REQUIRED))
        self.assertNoNewSubmission(form)

        incoming("999123", "mod_ss_3,pid1235,arm a", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_EXPECTED_NAMED_ARGS_SEPARATOR, context=("=",)))
        self.assertNoNewSubmission(form)

        incoming("999123", "mod_ss_3,pid1235,arm=a,arm=b", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_MULTIPLE_ANSWERS_FOUND, context=("ARM",)))
        self.assertNoNewSubmission(form)

        incoming("999123", "mod_ss_3 ,  pid1235  ,  arm = a", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Thank you for your modification submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        case = self.get_case("pid1235")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Test global keywords
        incoming("999123", "#start unknownkeyword", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_KEYWORD_NOT_FOUND, context=("UNKNOWNKEYWORD",)))
        self.assertNoNewSubmission(form)

        incoming("999123", "#start", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_START_KEYWORD_USAGE, context=("#START",)))
        self.assertNoNewSubmission(form)

        incoming("999123", "#unknown", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_UNKNOWN_GLOBAL_KEYWORD, context=("#UNKNOWN",)))
        self.assertNoNewSubmission(form)

        # Mobile worker creates a case
        incoming("999123", "#start reg", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Participant ID")
        incoming("999123", "pid1237", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        incoming("999123", "1", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "participant_id", "pid1237")
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        self.assertFormQuestionEquals(form, "external_id", "pid1237")
        case = self.get_case("pid1237")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "name", "pid1237")
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Mobile worker modifies a case
        incoming("999123", "#start mod pid1237", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        incoming("999123", "b", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_b")
        case = self.get_case("pid1237")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        # Bad external id
        incoming("999123", "#start mod pid1240", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_CASE_NOT_FOUND))
        self.assertNoNewSubmission(form)

        # No external id
        incoming("999123", "#start mod", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, get_message(MSG_MISSING_EXTERNAL_ID))
        self.assertNoNewSubmission(form)

        # CURRENT keyword
        incoming("999123", "reg", "TEST")
        sms1 = self.assertLastOutboundSMSEquals(self.user1, "Enter Participant ID")
        incoming("999123", "#CURRENT", "TEST")
        sms2 = self.assertLastOutboundSMSEquals(self.user1, "Enter Participant ID")
        self.assertNotEqual(sms1.pk, sms2.pk)

        # STOP keyword
        session = self.get_open_session(self.user1)
        self.assertIsNotNone(session)
        incoming("999123", "#STOP", "TEST")
        session = self.get_open_session(self.user1)
        self.assertIsNone(session)
        self.assertNoNewSubmission(form)

        # One keyword overrides another
        incoming("999123", "reg", "TEST")
        sms1 = self.assertLastOutboundSMSEquals(self.user1, "Enter Participant ID")
        incoming("999123", "mod pid1237", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        self.assertNoNewSubmission(form)
        incoming("999123", "reg", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "%s Enter Study Arm 1:a, 2:b." % get_message(MSG_INVALID_CHOICE))
        incoming("999123", "a", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        case = self.get_case("pid1237")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Test initator filters
        case = self.get_case("pid1237")
        update_case(self.domain, case.case_id,
            case_properties={'contact_phone_number': '999124', 'contact_phone_number_is_verified': '1'})
        case = CaseAccessors(self.domain).get_case(case.case_id)

        incoming("999123", "for_user", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "This message is for users")
        incoming("999123", "for_case", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Default SMS Response")

        incoming("999124", "for_case", "TEST")
        self.assertLastOutboundSMSEquals(case, "This message is for cases")
        incoming("999124", "for_user", "TEST")
        self.assertLastOutboundSMSEquals(case, "Default SMS Response")

        # Test form over sms for case
        incoming("999124", "mod", "TEST")
        self.assertLastOutboundSMSEquals(case, "Enter Study Arm 1:a, 2:b.")
        incoming("999123", "mod pid1237", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "Enter Study Arm 1:a, 2:b.")
        incoming("999124", "b", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_b")
        case = self.get_case("pid1237")
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        incoming("999123", "a", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        case = self.get_case("pid1237")
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Test structured sms for case
        incoming("999124", "mod_ss 2", "TEST")
        self.assertLastOutboundSMSEquals(case, "Thank you for your modification submission.")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_b")
        case = self.get_case("pid1237")
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        # Test Auth
        incoming("999122", "mod pid1237", "TEST")
        self.assertLastOutboundSMSEquals(self.user2, get_message(MSG_CASE_NOT_FOUND))

        # Test notifying others
        incoming("999124", "for_owner", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "This message is for the case owner")

        incoming("999124", "for_group", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "This message is for the group")
        self.assertLastOutboundSMSEquals(self.user2, "This message is for the group")

        case = self.get_case("pid1237")
        self.update_case_owner(case, self.group1)
        incoming("999124", "for_owner", "TEST")
        self.assertLastOutboundSMSEquals(self.user1, "This message is for the case owner")
        self.assertLastOutboundSMSEquals(self.user2, "This message is for the case owner")

        # Test case sharing auth
        incoming("999122", "mod pid1237", "TEST")
        self.assertLastOutboundSMSEquals(self.user2, "Enter Study Arm 1:a, 2:b.")
        incoming("999122", "1", "TEST")
        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        case = self.get_case("pid1237")
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Test closing open sessions on an sms reply
        incoming("999122", "reg", "TEST")
        self.assertLastOutboundSMSEquals(self.user2, "Enter Participant ID")
        incoming("999122", "for_user", "TEST")
        self.assertLastOutboundSMSEquals(self.user2, "This message is for users")
        incoming("999122", "null", "TEST")
        self.assertLastOutboundSMSEquals(self.user2, "Default SMS Response")


@patch('corehq.apps.smsforms.util.critical_section_for_smsforms_sessions',
       new=mock_critical_section_for_smsforms_sessions)
class PartialFormSubmissionTestCase(TouchformsTestCase):
    """
    Must be run manually (see util.TouchformsTestCase)
    """

    def setUp(self):
        from django.core.management import call_command
        call_command('cchq_prbac_bootstrap')
        super(PartialFormSubmissionTestCase, self).setUp()
        self.app = self.load_app("app_source.json")
        self.create_structured_sms_keyword(
            "REG",
            self.app.modules[0].forms[0].unique_id,
            "Thank you for your registration submission.",
        )
        self.create_survey_keyword("MOD", self.app.modules[0].forms[3].unique_id)
        self.user = self.create_mobile_worker("abc", "123", "999123")

    def testPartialSubmission(self):
        # Register the case
        incoming("999123", "reg pid123 1", "TEST")

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "participant_id", "pid123")
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        self.assertFormQuestionEquals(form, "external_id", "pid123")
        self.assertFalse(form.partial_submission)

        case = self.get_case("pid123")
        self.assertIsNotNone(case)
        self.assertCasePropertyEquals(case, "name", "pid123")
        self.assertCasePropertyEquals(case, "arm", "arm_a")

        # Start a modify form, and submit a partial submission with case side effects
        incoming("999123", "mod pid123", "TEST")
        incoming("999123", "2", "TEST")
        session = self.get_open_session(self.user)
        session.submit_partially_completed_forms = True
        session.include_case_updates_in_partial_submissions = True
        session.close()
        session.save()

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_b")
        self.assertFormQuestionEquals(form, "other_question", "")
        self.assertTrue(form.partial_submission)

        case = self.get_case("pid123")
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        self.assertFalse(session.session_is_open)
        self.assertEqual(session.submission_id, form.form_id)

        # Start a modify form, and submit a partial submission without case side effects
        incoming("999123", "mod pid123", "TEST")
        incoming("999123", "1", "TEST")
        session = self.get_open_session(self.user)
        session.submit_partially_completed_forms = True
        session.include_case_updates_in_partial_submissions = False
        session.close()
        session.save()

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "arm", "arm_a")
        self.assertFormQuestionEquals(form, "other_question", "")
        self.assertTrue(form.partial_submission)

        case = self.get_case("pid123")
        self.assertCasePropertyEquals(case, "arm", "arm_b")

        self.assertFalse(session.session_is_open)
        self.assertEqual(session.submission_id, form.form_id)
