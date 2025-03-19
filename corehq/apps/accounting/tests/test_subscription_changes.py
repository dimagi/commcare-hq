import uuid
from datetime import date, time
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, TransactionTestCase

from corehq.util.test_utils import flag_enabled
from dimagi.utils.parsing import json_format_date

from corehq.apps.accounting.exceptions import SubscriptionAdjustmentError
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
)
from corehq.apps.accounting.subscription_changes import (
    DomainDowngradeActionHandler,
    _deactivate_schedules,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import (
    CommCareUser,
    HqPermissions,
    UserRole,
    WebUser,
)
from corehq.apps.users.role_utils import (
    UserRolePresets,
    initialize_domain_with_default_roles,
)
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    SMSContent,
    SMSSurveyContent,
    TimedEvent,
    TimedSchedule,
)
from corehq.privileges import REPORT_BUILDER_ADD_ON_PRIVS


class TestSubscriptionEmailLogic(SimpleTestCase):

    def test_new_trial_with_no_previous(self):
        self._run_test(None, Subscription(is_trial=True), False)

    def test_non_trial_with_no_previous(self):
        self._run_test(None, Subscription(is_trial=False), False)

    def test_non_trial_with_previous(self):
        self._run_test(Subscription(is_trial=False), Subscription(is_trial=False), True)
        self._run_test(Subscription(is_trial=True), Subscription(is_trial=False), True)

    def _run_test(self, old_sub, new_sub, expected_output):
        self.assertEqual(expected_output, Subscriber.should_send_subscription_notification(old_sub, new_sub))


class TestUserRoleSubscriptionChanges(BaseAccountingTest):

    def setUp(self):
        super(TestUserRoleSubscriptionChanges, self).setUp()
        self.domain = Domain(
            name="test-sub-changes",
            is_active=True,
        )
        self.domain.save()
        self.other_domain = Domain(
            name="other-domain",
            is_active=True,
        )
        self.other_domain.save()
        initialize_domain_with_default_roles(self.domain.name)
        self.user_roles = UserRole.objects.get_by_domain(self.domain.name)
        self.custom_role = UserRole.create(
            self.domain.name,
            "Custom Role",
            permissions=HqPermissions(
                edit_apps=True,
                view_apps=True,
                edit_web_users=True,
                view_web_users=True,
                view_roles=True,
            )
        )

        self.admin_username = generator.create_arbitrary_web_user_name()

        self.web_users = []
        self.commcare_users = []
        for role in [self.custom_role] + self.user_roles:
            web_user = WebUser.create(
                self.other_domain.name, generator.create_arbitrary_web_user_name(), 'test123', None, None
            )
            web_user.is_active = True
            web_user.add_domain_membership(self.domain.name, role_id=role.get_id)
            web_user.save()
            self.web_users.append(web_user)

            commcare_user = generator.arbitrary_user(
                domain_name=self.domain.name)
            commcare_user.set_role(self.domain.name, role.get_qualified_id())
            commcare_user.save()
            self.commcare_users.append(commcare_user)

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self.community_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.COMMUNITY)

    def test_cancellation(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_username
        )
        self._change_std_roles()
        subscription.change_plan(DefaultProductPlan.get_default_plan_version())

        custom_role = UserRole.objects.by_couch_id(self.custom_role.get_id)
        self.assertTrue(custom_role.is_archived)

        self._assertInitialRoles()
        self._assertStdUsers()

    def test_resubscription(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_username
        )
        self._change_std_roles()
        new_subscription = subscription.change_plan(DefaultProductPlan.get_default_plan_version())
        custom_role = UserRole.objects.by_couch_id(self.custom_role.get_id)
        self.assertTrue(custom_role.is_archived)
        new_subscription.change_plan(self.advanced_plan, web_user=self.admin_username)
        custom_role = UserRole.objects.by_couch_id(self.custom_role.get_id)
        self.assertFalse(custom_role.is_archived)

        self._assertInitialRoles()
        self._assertStdUsers()

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_add_attendance_coordinator_role_for_domain(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.community_plan,
            web_user=self.admin_username
        )

        assert not UserRole.objects.filter(
            name=UserRolePresets.ATTENDANCE_COORDINATOR,
            domain=self.domain.name
        ).exists()

        subscription.change_plan(self.advanced_plan, web_user=self.admin_username)
        pm_role_created = UserRole.objects.filter(
            name=UserRolePresets.ATTENDANCE_COORDINATOR, domain=self.domain.name
        ).exists()
        self.assertTrue(pm_role_created)

    @flag_enabled('ATTENDANCE_TRACKING')
    def test_archive_attendance_coordinator_role_when_downgrading(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_username
        )

        role = UserRole.objects.filter(
            name=UserRolePresets.ATTENDANCE_COORDINATOR,
            domain=self.domain.name
        ).first()
        self.assertFalse(role.is_archived)

        subscription.change_plan(self.community_plan, web_user=self.admin_username)
        role = UserRole.objects.filter(
            name=UserRolePresets.ATTENDANCE_COORDINATOR,
            domain=self.domain.name
        ).first()
        self.assertTrue(role.is_archived)

    @flag_enabled('ATTENDANCE_TRACKING')
    @patch('corehq.apps.events.tasks.close_mobile_worker_attendee_cases')
    def test_close_mobile_worker_attendee_cases_when_downgrading(self, close_mobile_worker_attendee_cases_mock):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_username
        )

        subscription.change_plan(self.community_plan, web_user=self.admin_username)
        close_mobile_worker_attendee_cases_mock.delay.assert_called_once()

    def _change_std_roles(self):
        for u in self.user_roles:
            user_role = UserRole.objects.by_couch_id(u.get_id)
            user_role.set_permissions(HqPermissions(
                view_reports=True,
                edit_commcare_users=True,
                view_commcare_users=True,
                edit_groups=True,
                view_groups=True,
                edit_locations=True,
                view_locations=True,
                edit_apps=True,
                view_apps=True,
                edit_data=True,
                edit_reports=True
            ).to_list())

    def _assertInitialRoles(self):
        for u in self.user_roles:
            user_role = UserRole.objects.by_couch_id(u.get_id)
            self.assertEqual(
                user_role.permissions,
                UserRolePresets.INITIAL_ROLES[user_role.name](),
            )

    def _assertStdUsers(self):
        for ind, wu in enumerate(self.web_users[1:]):
            web_user = WebUser.get(wu.get_id)
            self.assertEqual(
                web_user.get_domain_membership(self.domain.name).role_id,
                self.user_roles[ind].get_id
            )

        for ind, cc in enumerate(self.commcare_users[1:]):
            commcare_user = CommCareUser.get(cc.get_id)
            self.assertEqual(
                commcare_user.get_domain_membership(self.domain.name).role_id,
                self.user_roles[ind].get_id
            )

    def tearDown(self):
        self.domain.delete()
        self.other_domain.delete()
        super(TestUserRoleSubscriptionChanges, self).tearDown()


class TestSubscriptionChangeResourceConflict(BaseAccountingTest):

    def setUp(self):
        self.domain_name = 'test-domain-changes'
        self.domain = Domain(
            name=self.domain_name,
            is_active=True,
            description='spam',
        )
        self.domain.save()

    def tearDown(self):
        self.domain.delete()
        super(TestSubscriptionChangeResourceConflict, self).tearDown()

    def test_domain_changes(self):
        role = Mock()
        role.memberships_granted.all.return_value = []
        version = Mock()
        version.role.get_cached_role.return_value = role
        handler = DomainDowngradeActionHandler(
            self.domain, new_plan_version=version, changed_privs=REPORT_BUILDER_ADD_ON_PRIVS
        )

        conflicting_domain = Domain.get_by_name(self.domain_name)
        conflicting_domain.description = 'eggs'
        conflicting_domain.save()

        get_by_name_func = Domain.get_by_name
        with patch('corehq.apps.accounting.subscription_changes.Domain') as Domain_patch:
            Domain_patch.get_by_name.side_effect = lambda name: get_by_name_func(name)
            handler.get_response()
            Domain_patch.get_by_name.assert_called_with(self.domain_name)


class TestSoftwarePlanChanges(BaseAccountingTest):

    def setUp(self):
        super(TestSoftwarePlanChanges, self).setUp()
        self.domain = Domain(
            name="test-plan-changes",
            is_active=True,
        )
        self.domain.save()
        self.domain2 = Domain(
            name="other-domain",
            is_active=True,
        )
        self.domain2.save()

        self.admin_username = generator.create_arbitrary_web_user_name()
        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self.advanced_plan.plan.max_domains = 1
        self.community_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.COMMUNITY)

    def tearDown(self):
        self.domain.delete()
        self.domain2.delete()
        super(TestSoftwarePlanChanges, self).tearDown()

    def test_change_plan_blocks_on_max_domains(self):
        Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan
        )

        sub2 = Subscription.new_domain_subscription(
            self.account, self.domain2.name, self.community_plan
        )
        self.assertRaises(SubscriptionAdjustmentError, lambda: sub2.change_plan(self.advanced_plan))


class DeactivateScheduleTest(TransactionTestCase):

    def setUp(self):
        super(DeactivateScheduleTest, self).setUp()
        self.domain_1 = 'deactivate-schedules-1'
        self.domain_obj_1 = Domain(name=self.domain_1)
        self.domain_obj_1.save()
        self.domain_2 = 'deactivate-schedules-2'
        self.domain_obj_2 = Domain(name=self.domain_2)
        self.domain_obj_2.save()

        self.domain_1_sms_schedules = [
            self.create_scheduled_broadcast(self.domain_1, SMSContent()),
            self.create_immediate_broadcast(self.domain_1, SMSContent()),
            self.create_conditional_alert(self.domain_1, SMSContent()),
        ]

        self.domain_1_survey_schedules = [
            self.create_scheduled_broadcast(self.domain_1, self.create_survey_content()),
            self.create_immediate_broadcast(self.domain_1, self.create_survey_content()),
            self.create_conditional_alert(self.domain_1, self.create_survey_content()),
        ]

        self.domain_2_sms_schedules = [
            self.create_scheduled_broadcast(self.domain_2, SMSContent()),
            self.create_immediate_broadcast(self.domain_2, SMSContent()),
            self.create_conditional_alert(self.domain_2, SMSContent()),
        ]

        self.domain_2_survey_schedules = [
            self.create_scheduled_broadcast(self.domain_2, self.create_survey_content()),
            self.create_immediate_broadcast(self.domain_2, self.create_survey_content()),
            self.create_conditional_alert(self.domain_2, self.create_survey_content()),
        ]

    def create_survey_content(self):
        return SMSSurveyContent(
            app_id='456',
            form_unique_id='123',
            expire_after=60,
        )

    def create_scheduled_broadcast(self, domain, content):
        schedule = TimedSchedule.create_simple_daily_schedule(domain, TimedEvent(time=time(12, 0)), content)
        return ScheduledBroadcast.objects.create(
            domain=domain,
            name='',
            start_date=date(2018, 1, 1),
            schedule=schedule,
            recipients=[['CommCareUser', uuid.uuid4().hex]],
        )

    def create_immediate_broadcast(self, domain, content):
        schedule = AlertSchedule.create_simple_alert(domain, content)
        return ImmediateBroadcast.objects.create(
            domain=domain,
            name='',
            schedule=schedule,
            recipients=[['CommCareUser', uuid.uuid4().hex]],
        )

    def create_conditional_alert(self, domain, content):
        schedule = AlertSchedule.create_simple_alert(domain, content)
        rule = create_empty_rule(domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            alert_schedule_id=schedule.schedule_id,
            recipients=[['CommCareUser', uuid.uuid4().hex]],
        )
        return rule

    def tearDown(self):
        for domain in (self.domain_1, self.domain_2):
            for rule in AutomaticUpdateRule.objects.filter(domain=domain):
                rule.hard_delete()

            for broadcast in ScheduledBroadcast.objects.filter(domain=domain):
                broadcast.delete()

            for broadcast in ImmediateBroadcast.objects.filter(domain=domain):
                broadcast.delete()

            for schedule in TimedSchedule.objects.filter(domain=domain):
                schedule.delete()

            for schedule in AlertSchedule.objects.filter(domain=domain):
                schedule.delete()

        self.domain_obj_1.delete()
        self.domain_obj_2.delete()

        super(DeactivateScheduleTest, self).tearDown()

    def assertScheduleActiveFlag(self, obj, active_flag):
        if isinstance(obj, ScheduledBroadcast):
            schedule = TimedSchedule.objects.get(schedule_id=obj.schedule_id)
        elif isinstance(obj, ImmediateBroadcast):
            schedule = AlertSchedule.objects.get(schedule_id=obj.schedule_id)
        elif isinstance(obj, AutomaticUpdateRule):
            schedule = AlertSchedule.objects.get(schedule_id=obj.get_schedule().schedule_id)
        else:
            raise TypeError("Expected ScheduledBroadcast, ImmediateBroadcast, or AutomaticUpdateRule")

        self.assertEqual(schedule.active, active_flag)

    def assertSchedulesActive(self, objects):
        for obj in objects:
            self.assertScheduleActiveFlag(obj, True)

    def assertSchedulesInactive(self, objects):
        for obj in objects:
            self.assertScheduleActiveFlag(obj, False)

    def test_deactivate_all_schedules(self):
        self.assertSchedulesActive(self.domain_1_sms_schedules)
        self.assertSchedulesActive(self.domain_1_survey_schedules)
        self.assertSchedulesActive(self.domain_2_sms_schedules)
        self.assertSchedulesActive(self.domain_2_survey_schedules)

        with patch('corehq.apps.accounting.subscription_changes.refresh_timed_schedule_instances.delay') as p1, \
             patch('corehq.apps.accounting.subscription_changes.refresh_alert_schedule_instances.delay') as p2, \
             patch('corehq.messaging.tasks.initiate_messaging_rule_run') as p3:

            _deactivate_schedules(self.domain_obj_1)

            self.assertEqual(p1.call_count, 2)
            p1.assert_has_calls(
                [
                    call(
                        broadcast.schedule_id.hex,
                        broadcast.recipients,
                        start_date_iso_string=json_format_date(broadcast.start_date)
                    )
                    for broadcast in (self.domain_1_sms_schedules[0], self.domain_1_survey_schedules[0])
                ],
                any_order=True
            )

            self.assertEqual(p2.call_count, 2)
            p2.assert_has_calls(
                [
                    call(broadcast.schedule_id.hex, broadcast.recipients)
                    for broadcast in (self.domain_1_sms_schedules[1], self.domain_1_survey_schedules[1])
                ],
                any_order=True
            )

            self.assertEqual(p3.call_count, 2)
            p3.assert_has_calls(
                [
                    call(rule)
                    for rule in (self.domain_1_sms_schedules[2], self.domain_1_survey_schedules[2])
                ],
                any_order=True
            )

        self.assertSchedulesInactive(self.domain_1_sms_schedules)
        self.assertSchedulesInactive(self.domain_1_survey_schedules)
        self.assertSchedulesActive(self.domain_2_sms_schedules)
        self.assertSchedulesActive(self.domain_2_survey_schedules)

    def test_deactivate_only_survey_schedules(self):
        self.assertSchedulesActive(self.domain_1_sms_schedules)
        self.assertSchedulesActive(self.domain_1_survey_schedules)
        self.assertSchedulesActive(self.domain_2_sms_schedules)
        self.assertSchedulesActive(self.domain_2_survey_schedules)

        with patch('corehq.apps.accounting.subscription_changes.refresh_timed_schedule_instances.delay') as p1, \
             patch('corehq.apps.accounting.subscription_changes.refresh_alert_schedule_instances.delay') as p2, \
             patch('corehq.messaging.tasks.initiate_messaging_rule_run') as p3:

            _deactivate_schedules(self.domain_obj_1, survey_only=True)

            b = self.domain_1_survey_schedules[0]
            p1.assert_called_once_with(
                b.schedule_id.hex,
                b.recipients,
                start_date_iso_string=json_format_date(b.start_date)
            )

            b = self.domain_1_survey_schedules[1]
            p2.assert_called_once_with(b.schedule_id.hex, b.recipients)

            rule = self.domain_1_survey_schedules[2]
            p3.assert_called_once_with(rule)

        self.assertSchedulesActive(self.domain_1_sms_schedules)
        self.assertSchedulesInactive(self.domain_1_survey_schedules)
        self.assertSchedulesActive(self.domain_2_sms_schedules)
        self.assertSchedulesActive(self.domain_2_survey_schedules)
