from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.messaging.scheduling.models import TimedSchedule, SMSContent
from datetime import time
from django.db import transaction


def create_beneficiary_indicator_1(domain):
    with transaction.atomic():
        schedule = TimedSchedule.create_simple_daily_schedule(
            domain,
            time(9, 0),
            SMSContent(
                message={
                    'en': "{case.host.name} is severely malnourished. Please consult the Anganwadi for advice in the next visit",
                }
            ),
            total_iterations=1
        )
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
