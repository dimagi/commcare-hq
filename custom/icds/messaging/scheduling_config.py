from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.messaging.scheduling.models import TimedSchedule, SMSContent, CustomContent
from datetime import time
from django.db import transaction


def create_beneficiary_indicator_1(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            time(9, 0),
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
            recipients=(('CustomRecipient', 'ICDS_MOTHER_PERSON_CASE_FROM_CHILD_HEALTH_CASE'),)
        )


def create_beneficiary_indicator_2(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            time(9, 0),
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
