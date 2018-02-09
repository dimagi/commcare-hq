from __future__ import absolute_import
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CustomMatchDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.messaging.scheduling.const import VISIT_WINDOW_END
from corehq.messaging.scheduling.models import TimedSchedule, TimedEvent, SMSContent, CustomContent
from datetime import time
from django.db import transaction


def create_beneficiary_indicator_1(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={
                u'en': u'{case.host.name} is severely malnourished. Please consult the Anganwadi for advice in the next visit',
                u'hin': u'{case.host.name} \u0917\u093e\u0902\u092d\u0940\u0930 \u0930\u0942\u092a \u0938\u0947 \u0915\u0941\u092a\u094b\u0937\u093f\u0924 \u0939\u0948\u0902 | \u0915\u0943\u092a\u093e \u0905\u0917\u0932\u0947 \u0917\u094d\u0930\u0939 \u092d\u094d\u0930\u092e\u0923 \u092e\u0947\u0902 \u0906\u0901\u0917\u0928\u0935\u093e\u095c\u0940 \u0938\u0947 \u092a\u0930\u093e\u092e\u0930\u094d\u0936 \u0915\u0930 \u0938\u0932\u093e\u0939 \u092a\u094d\u0930\u093e\u092a\u094d\u0924  \u0915\u0930\u0947 |',
                u'tel': u'{case.host.name} \u0c24\u0c40\u0c35\u0c4d\u0c30\u0c2e\u0c48\u0c28 \u0c15\u0c41\u0c2a\u0c4b\u0c37\u0c23\u0c32\u0c4b \u0c09\u0c28\u0c4d\u0c28\u0c3e\u0c30\u0c41. \u0c08 \u0c38\u0c3e\u0c30\u0c3f \u0c05\u0c02\u0c17\u0c28\u0c4d \u0c35\u0c3e\u0c21\u0c40 \u0c38\u0c46\u0c02\u0c1f\u0c30\u0c41\u0c15\u0c41 \u0c35\u0c46\u0c33\u0c4d\u0c33\u0c3f\u0c28\u0c2a\u0c4d\u0c2a\u0c41\u0c21\u0c41 \u0c24\u0c17\u0c41 \u0c38\u0c32\u0c39\u0c3e \u0c15\u0c4a\u0c30\u0c15\u0c41 \u0c15\u0c3e\u0c30\u0c4d\u0c2f\u0c15\u0c30\u0c4d\u0c24\u0c28\u0c41 \u0c38\u0c02\u0c2a\u0c4d\u0c30\u0c26\u0c3f\u0c02\u0c1a\u0c02\u0c21\u0c3f.',
            }),
            total_iterations=1
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'beneficiary_1'}
        schedule.save()

        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="Beneficiary #1: Z-Score Grading Indicator",
            case_type='child_health',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='zscore_grading_wfa',
            property_value='red',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CustomRecipient', 'ICDS_MOTHER_PERSON_CASE_FROM_CHILD_HEALTH_CASE'),),
            reset_case_property_name='last_date_gmp',
        )


def create_beneficiary_indicator_2(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_STATIC_NEGATIVE_GROWTH_MESSAGE'),
            total_iterations=1
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'beneficiary_2'}
        schedule.save()

        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="Beneficiary #2: Static / Negative Weight Indicator",
            case_type='child_health',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='static_negative_growth_time',
            match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CustomRecipient', 'ICDS_MOTHER_PERSON_CASE_FROM_CHILD_HEALTH_CASE'),),
            reset_case_property_name='static_negative_growth_time',
        )


def create_aww_indicator_3(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_MISSED_CF_VISIT_TO_AWW'),
            total_iterations=1,
            start_offset=1,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'aww_3'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="AWW #3: Missed CF #1",
            case_type='ccs_record',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='cf1_date',
            match_type=MatchPropertyDefinition.MATCH_HAS_NO_VALUE,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('Owner', None),),
            scheduler_module_info=CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
                enabled=True,
                app_id='48cc1709b7f62ffea24cc6634a004745',
                form_unique_id='84ea09b6aa5aba125ec82bf2bb8dfa44cc5ea150',
                visit_number=0,
                window_position=VISIT_WINDOW_END,
            ),
        )


def create_ls_indicator_3(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_MISSED_CF_VISIT_TO_LS'),
            total_iterations=1,
            start_offset=1,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'ls_3'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="LS #3: Missed CF #1",
            case_type='ccs_record',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='cf1_date',
            match_type=MatchPropertyDefinition.MATCH_HAS_NO_VALUE,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CustomRecipient', 'ICDS_SUPERVISOR_FROM_AWC_OWNER'),),
            scheduler_module_info=CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
                enabled=True,
                app_id='48cc1709b7f62ffea24cc6634a004745',
                form_unique_id='84ea09b6aa5aba125ec82bf2bb8dfa44cc5ea150',
                visit_number=0,
                window_position=VISIT_WINDOW_END,
            ),
        )


def _create_ls_indicator_5(domain, visit_num):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_MISSED_PNC_VISIT_TO_LS'),
            total_iterations=1,
            start_offset=1,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'ls_5'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="LS #5: Missed PNC #%s" % visit_num,
            case_type='ccs_record',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='pnc%s_date' % visit_num,
            match_type=MatchPropertyDefinition.MATCH_HAS_NO_VALUE,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CustomRecipient', 'ICDS_SUPERVISOR_FROM_AWC_OWNER'),),
            scheduler_module_info=CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
                enabled=True,
                app_id='48cc1709b7f62ffea24cc6634a004745',
                form_unique_id='f55da33c32fb41489d5082b7b3acfe43c739e988',
                visit_number=visit_num - 1,
                window_position=VISIT_WINDOW_END,
            ),
        )


def create_ls_indicator_5(domain):
    _create_ls_indicator_5(domain, 1)
    _create_ls_indicator_5(domain, 2)
    _create_ls_indicator_5(domain, 3)


def create_aww_indicator_6(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_CF_VISITS_COMPLETE'),
            total_iterations=1,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'aww_6'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="AWW #6: CF Visits Complete",
            case_type='ccs_record',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        for i in [1, 2, 3, 4, 5, 6, 7]:
            rule.add_criteria(
                MatchPropertyDefinition,
                property_name='cf%s_date' % i,
                match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
            )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('Owner', None),),
        )


def create_ls_indicator_4a(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_CHILD_ILLNESS_REPORTED'),
            total_iterations=1,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'ls_4a'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="LS #4a: Child Fever Reported in Exclusive Breastfeeding form",
            case_type='person',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='last_reported_fever_date',
            match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CustomRecipient', 'ICDS_SUPERVISOR_FROM_AWC_OWNER'),),
            reset_case_property_name='last_reported_fever_date',
        )


def create_ls_indicator_4b(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_CHILD_ILLNESS_REPORTED'),
            total_iterations=1,
            start_offset=7,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'ls_4b'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="LS #4b: Child Illness Reported in Referral Form",
            case_type='person',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='last_referral_date',
            match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='referral_health_problem',
            match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='dob',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
            property_value='-2192',
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CustomRecipient', 'ICDS_SUPERVISOR_FROM_AWC_OWNER'),),
            reset_case_property_name='last_referral_date',
        )


def create_aww_indicator_4(domain):
    with transaction.atomic():
        # Monthly schedule for the last day of the month
        schedule = TimedSchedule.create_simple_monthly_schedule(
            domain,
            TimedEvent(time=time(9, 30)),
            [-1],
            CustomContent(custom_content_id='ICDS_DPT3_AND_MEASLES_ARE_DUE'),
            total_iterations=TimedSchedule.REPEAT_INDEFINITELY
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'aww_4'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="AWW #4: DPT3 and Measles Vaccinations Due",
            case_type='tasks',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            CustomMatchDefinition,
            name='ICDS_CONSIDER_CASE_FOR_DPT3_AND_MEASLES_REMINDER',
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('Owner', None),),
        )


def create_aww_indicator_5(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            TimedEvent(time=time(9, 0)),
            CustomContent(custom_content_id='ICDS_CHILD_VACCINATIONS_COMPLETE'),
            total_iterations=1,
        )
        schedule.default_language_code = 'hin'
        schedule.custom_metadata = {'icds_indicator': 'aww_5'}
        schedule.save()
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name="AWW #5: Child Vaccinations Complete",
            case_type='tasks',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='tasks_type',
            property_value='child',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='immun_one_year_complete',
            property_value='yes',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('Owner', None),),
        )
