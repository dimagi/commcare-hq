import datetime

from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext

from couchdbkit import ResourceConflict

from corehq import privileges
from corehq.apps.accounting.utils import get_privileges, log_accounting_error
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.exceptions import DomainDoesNotExist
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.userreports.exceptions import (
    DataSourceConfigurationNotFoundError,
)
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.role_utils import (
    get_custom_roles_for_domain,
    archive_custom_roles_for_domain,
    unarchive_roles_for_domain,
    reset_initial_roles_for_domain,
)
from corehq.const import USER_DATE_FORMAT
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    TimedSchedule,
)
from corehq.messaging.scheduling.tasks import (
    refresh_alert_schedule_instances,
    refresh_timed_schedule_instances,
)


class BaseModifySubscriptionHandler(object):

    def __init__(self, domain, new_plan_version, changed_privs, date_start=None):
        self.domain = (
            domain if isinstance(domain, Domain)
            else Domain.get_by_name(domain, strict=True)
        )
        if self.domain is None:
            # This fails down the line anyway
            # and failing now gives a much better traceback
            raise DomainDoesNotExist()
        self.date_start = date_start or datetime.date.today()
        self.new_plan_version = new_plan_version

        self.privileges = [x for x in changed_privs if x in self.supported_privileges()]

    def get_response(self):
        responses = []
        for privilege in self.privileges:
            try:
                response = self.privilege_to_response_function()[privilege](self.domain, self.new_plan_version)
            except ResourceConflict:
                # Something else updated the domain. Reload and try again.
                self.domain = Domain.get_by_name(self.domain.name)
                response = self.privilege_to_response_function()[privilege](self.domain, self.new_plan_version)
            if response is not None:
                responses.append(response)
        return responses

    @property
    def action_type(self):
        raise NotImplementedError

    @classmethod
    def privilege_to_response_function(cls):
        raise NotImplementedError

    @classmethod
    def supported_privileges(cls):
        return list(cls.privilege_to_response_function().keys())


class BaseModifySubscriptionActionHandler(BaseModifySubscriptionHandler):

    def get_response(self):
        response = super(BaseModifySubscriptionActionHandler, self).get_response()
        return all(response)


def _get_active_immediate_broadcasts(domain, survey_only=False):
    result = list(ImmediateBroadcast.objects.filter(domain=domain.name, deleted=False, schedule__active=True))
    if survey_only:
        result = [broadcast for broadcast in result if broadcast.schedule.memoized_uses_sms_survey]

    return result


def _get_active_scheduled_broadcasts(domain, survey_only=False):
    result = list(ScheduledBroadcast.objects.filter(domain=domain.name, deleted=False, schedule__active=True))
    if survey_only:
        result = [broadcast for broadcast in result if broadcast.schedule.memoized_uses_sms_survey]

    return result


def _get_active_scheduling_rules(domain, survey_only=False):
    rules = AutomaticUpdateRule.by_domain(domain.name, AutomaticUpdateRule.WORKFLOW_SCHEDULING, active_only=False)

    result = []
    for rule in rules:
        schedule = rule.get_schedule()
        if schedule.active and (not survey_only or schedule.memoized_uses_sms_survey):
            result.append(rule)

    return result


def get_refresh_alert_schedule_instances_call(broadcast):
    def refresh():
        refresh_alert_schedule_instances.delay(
            broadcast.schedule_id,
            broadcast.recipients,
        )

    return refresh


def get_refresh_timed_schedule_instances_call(broadcast):
    def refresh():
        refresh_timed_schedule_instances.delay(
            broadcast.schedule_id,
            broadcast.recipients,
            start_date=broadcast.start_date
        )

    return refresh


def _deactivate_schedules(domain, survey_only=False):
    """
    The subscription changes are executed within a transaction, so
    we need to make sure any celery tasks only get started after the
    transaction commits.
    """
    from corehq.messaging.tasks import initiate_rule_run

    for broadcast in _get_active_immediate_broadcasts(domain, survey_only=survey_only):
        AlertSchedule.objects.filter(schedule_id=broadcast.schedule_id).update(active=False)
        # We have to generate this function outside of this context otherwise it will be
        # bound to the name broadcast which changes over the course of iteration
        transaction.on_commit(get_refresh_alert_schedule_instances_call(broadcast))

    for broadcast in _get_active_scheduled_broadcasts(domain, survey_only=survey_only):
        TimedSchedule.objects.filter(schedule_id=broadcast.schedule_id).update(active=False)
        # We have to generate this function outside of this context otherwise it will be
        # bound to the name broadcast which changes over the course of iteration
        transaction.on_commit(get_refresh_timed_schedule_instances_call(broadcast))

    for rule in _get_active_scheduling_rules(domain, survey_only=survey_only):
        """
        Deactivating a scheduling rule involves only deactivating the schedule, and
        leaving the rule active. See ConditionalAlertListView.get_activate_ajax_response
        for more information.
        """
        with transaction.atomic():
            schedule = rule.get_schedule()
            if isinstance(schedule, AlertSchedule):
                AlertSchedule.objects.filter(schedule_id=schedule.schedule_id).update(active=False)
            elif isinstance(schedule, TimedSchedule):
                TimedSchedule.objects.filter(schedule_id=schedule.schedule_id).update(active=False)
            else:
                raise TypeError("Expected AlertSchedule or TimedSchedule")

            initiate_rule_run(rule)


class DomainDowngradeActionHandler(BaseModifySubscriptionActionHandler):
    """
    This carries out the downgrade action based on each privilege.

    Each response should return a boolean.
    """
    action_type = "downgrade"

    @classmethod
    def privilege_to_response_function(cls):
        privs_to_responses = {
            privileges.OUTBOUND_SMS: cls.response_outbound_sms,
            privileges.INBOUND_SMS: cls.response_inbound_sms,
            privileges.ROLE_BASED_ACCESS: cls.response_role_based_access,
            privileges.DATA_CLEANUP: cls.response_data_cleanup,
            privileges.COMMCARE_LOGO_UPLOADER: cls.response_commcare_logo_uploader,
            privileges.ADVANCED_DOMAIN_SECURITY: cls.response_domain_security,
            privileges.PRACTICE_MOBILE_WORKERS: cls.response_practice_mobile_workers,
        }
        privs_to_responses.update({
            p: cls.response_report_builder
            for p in privileges.REPORT_BUILDER_ADD_ON_PRIVS
        })
        return privs_to_responses

    def get_response(self):
        response = super(DomainDowngradeActionHandler, self).get_response()
        worker_response = self.response_mobile_worker_creation(
            self.domain, self.new_plan_version)
        return response and worker_response

    @staticmethod
    def response_outbound_sms(domain, new_plan_version):
        """
        Reminder rules will be deactivated.
        """
        try:
            _deactivate_schedules(domain)
        except Exception:
            log_accounting_error(
                "Failed to downgrade outbound sms for domain %s."
                % domain.name
            )
            return False
        return True

    @staticmethod
    def response_inbound_sms(domain, new_plan_version):
        """
        All Reminder rules utilizing "survey" will be deactivated.
        """
        try:
            _deactivate_schedules(domain, survey_only=True)
        except Exception:
            log_accounting_error(
                "Failed to downgrade inbound sms for domain %s."
                % domain.name
            )
            return False
        return True

    @staticmethod
    def response_role_based_access(domain, new_plan_version):
        """
        Perform Role Based Access Downgrade
        - Archive custom roles.
        - Set user roles using custom roles to Read Only.
        - Reset initial roles to standard permissions.
        """
        custom_roles = get_custom_roles_for_domain(domain.name)
        from corehq.apps.accounting.models import SoftwarePlanEdition
        if not custom_roles or (new_plan_version.plan.edition == SoftwarePlanEdition.PAUSED):
            return True
        archive_custom_roles_for_domain(domain.name)
        reset_initial_roles_for_domain(domain.name)
        return True

    @staticmethod
    def response_data_cleanup(domain, new_plan_version):
        """
        Any active automatic case update rules should be deactivated.
        """
        try:
            AutomaticUpdateRule.by_domain(
                domain.name,
                AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            ).update(active=False)
            AutomaticUpdateRule.clear_caches(domain.name, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
            return True
        except Exception:
            log_accounting_error(
                "Failed to deactivate automatic update rules "
                "for domain %s." % domain.name
            )
            return False

    @staticmethod
    def response_commcare_logo_uploader(domain, new_plan_version):
        """Make sure no existing applications are using a logo.
        """
        from corehq.apps.accounting.tasks import archive_logos
        archive_logos.delay(domain.name)
        return True

    @staticmethod
    def response_domain_security(domain, new_plan_version):
        if domain.two_factor_auth or domain.secure_sessions or domain.strong_mobile_passwords:
            domain.two_factor_auth = False
            domain.secure_sessions = False
            domain.strong_mobile_passwords = False
            domain.save()

    @staticmethod
    def response_report_builder(project, new_plan_version):
        if not _has_report_builder_add_on(new_plan_version):
            # Clear paywall flags
            project.requested_report_builder_subscription = []
            project.save()

            # Deactivate all report builder data sources
            builder_reports = _get_report_builder_reports(project)
            for report in builder_reports:
                try:
                    report.config.deactivate()
                except DataSourceConfigurationNotFoundError:
                    pass
                report.visible = False
                report.save()

        return True

    @staticmethod
    def response_practice_mobile_workers(project, new_plan_version):
        from corehq.apps.app_manager.views.utils import unset_practice_mode_configured_apps
        unset_practice_mode_configured_apps(project.name)

    @staticmethod
    def response_mobile_worker_creation(domain, new_plan_version):
        """ Deactivates users if there are too many for a community plan """
        from corehq.apps.accounting.models import (
            DefaultProductPlan, FeatureType, UNLIMITED_FEATURE_USAGE)

        # checks for community plan
        if (new_plan_version != DefaultProductPlan.get_default_plan_version()):
            return True

        # checks if unlimited is on for this user
        user_rate = new_plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.USER).latest('date_created')
        if user_rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
            return True

        # checks for extra users
        num_users = CommCareUser.total_by_domain(
            domain.name, is_active=True)
        num_allowed = user_rate.monthly_limit
        if num_users > num_allowed:
            # offloads deactivation onto a separate thread
            # there should be a task that deactivates users here
            pass
        return True


class DomainUpgradeActionHandler(BaseModifySubscriptionActionHandler):
    """
    This carries out the upgrade action based on each privilege.

    Each response should return a boolean.
    """
    action_type = "upgrade"

    @classmethod
    def privilege_to_response_function(cls):
        privs_to_repsones = {
            privileges.ROLE_BASED_ACCESS: cls.response_role_based_access,
            privileges.COMMCARE_LOGO_UPLOADER: cls.response_commcare_logo_uploader,
        }
        privs_to_repsones.update({
            p: cls.response_report_builder
            for p in privileges.REPORT_BUILDER_ADD_ON_PRIVS
        })
        return privs_to_repsones

    @staticmethod
    def response_role_based_access(domain, new_plan_version):
        """
        Perform Role Based Access Upgrade
        - Un-archive custom roles.
        """
        unarchive_roles_for_domain(domain.name)
        return True

    @staticmethod
    def response_commcare_logo_uploader(domain, new_plan_version):
        """Make sure no existing applications are using a logo.
        """
        from corehq.apps.accounting.tasks import restore_logos
        restore_logos.delay(domain.name)
        return True

    @staticmethod
    def response_report_builder(project, new_plan_version):
        from corehq.apps.userreports.models import ReportConfiguration
        from corehq.apps.userreports.tasks import rebuild_indicators
        reports = ReportConfiguration.by_domain(project.name)
        builder_reports = [report for report in reports if report.report_meta.created_by_builder]
        for report in builder_reports:
            try:
                report.visible = True
                report.save()
                if report.config.is_deactivated:
                    report.config.is_deactivated = False
                    report.config.save()
                    rebuild_indicators.delay(report.config._id, source='subscription_change')
            except DataSourceConfigurationNotFoundError:
                pass
        return True


def _fmt_alert(message, details=None):
    if details is not None and not isinstance(details, list):
        raise ValueError("details should be a list.")
    return {
        'message': message,
        'details': details,
    }


def _has_report_builder_add_on(plan_version):
    """
    Return True if the given SoftwarePlanVersion has a report builder add-on
    privilege.
    """
    privs = get_privileges(plan_version) if plan_version is not None else set()
    return bool(privileges.REPORT_BUILDER_ADD_ON_PRIVS.intersection(privs))


def _get_report_builder_reports(project):
    from corehq.apps.userreports.models import ReportConfiguration
    reports = ReportConfiguration.by_domain(project.name)
    return [report for report in reports if report.report_meta.created_by_builder]


class DomainDowngradeStatusHandler(BaseModifySubscriptionHandler):
    """
    This returns a list of alerts for the user if their current domain is using features that
    will be removed during the downgrade.
    """
    action_type = "notification"

    @classmethod
    def privilege_to_response_function(cls):
        privs_to_responses = {
            privileges.CLOUDCARE: cls.response_cloudcare,
            privileges.LOOKUP_TABLES: cls.response_lookup_tables,
            privileges.CUSTOM_BRANDING: cls.response_custom_branding,
            privileges.OUTBOUND_SMS: cls.response_outbound_sms,
            privileges.INBOUND_SMS: cls.response_inbound_sms,
            privileges.DEIDENTIFIED_DATA: cls.response_deidentified_data,
            privileges.ROLE_BASED_ACCESS: cls.response_role_based_access,
            privileges.DATA_CLEANUP: cls.response_data_cleanup,
            privileges.ADVANCED_DOMAIN_SECURITY: cls.response_domain_security,
            privileges.PRACTICE_MOBILE_WORKERS: cls.response_practice_mobile_workers,
        }
        privs_to_responses.update({
            p: cls.response_report_builder
            for p in privileges.REPORT_BUILDER_ADD_ON_PRIVS
        })
        return privs_to_responses

    def get_response(self):
        responses = super(DomainDowngradeStatusHandler, self).get_response()
        responses.extend([response for response in [
            self.response_later_subscription,
            self.response_mobile_worker_creation,
        ] if response is not None])
        return responses

    @staticmethod
    def response_cloudcare(domain, new_plan_version):
        """
        CloudCare enabled apps will have cloudcare_enabled set to false on downgrade.
        """
        cloudcare_enabled_apps = get_cloudcare_apps(domain.name)
        if not cloudcare_enabled_apps:
            return None

        num_apps = len(cloudcare_enabled_apps)
        return _fmt_alert(
            ungettext(
                "You have %(num_apps)d application that will lose Web Apps "
                "access if you select this plan.",
                "You have %(num_apps)d applications that will lose Web Apps "
                "access if you select this plan.",
                num_apps
            ) % {
                'num_apps': num_apps,
            },
            [
                format_html(
                    '<a href="{}">{}</a>',
                    reverse('view_app', args=[domain.name, app['_id']]),
                    app['name']
                ) for app in cloudcare_enabled_apps
            ],
        )

    @staticmethod
    def response_lookup_tables(domain, new_plan_version):
        """
        Lookup tables will be deleted on downgrade.
        """
        num_fixtures = FixtureDataType.total_by_domain(domain.name)
        if num_fixtures > 0:
            return _fmt_alert(
                ungettext(
                    "You have %(num_fix)s Lookup Table set up. Selecting this "
                    "plan will delete this Lookup Table.",
                    "You have %(num_fix)s Lookup Tables set up. Selecting "
                    "this plan will delete these Lookup Tables.",
                    num_fixtures
                ) % {'num_fix': num_fixtures}
            )

    @staticmethod
    def response_custom_branding(domain, new_plan_version):
        """
        Custom logos will be removed on downgrade.
        """
        if domain.has_custom_logo:
            return _fmt_alert(_(
                "You are using custom branding. "
                "Selecting this plan will remove this feature."
            ))

    @staticmethod
    def response_outbound_sms(domain, new_plan_version):
        """
        Reminder rules will be deactivated.
        """
        num_active = (
            len(_get_active_immediate_broadcasts(domain)) +
            len(_get_active_scheduled_broadcasts(domain)) +
            len(_get_active_scheduling_rules(domain))
        )
        if num_active > 0:
            return _fmt_alert(
                ungettext(
                    "You have %(num_active)d active Reminder Rule or Broadcast. Selecting "
                    "this plan will deactivate it.",
                    "You have %(num_active)d active Reminder Rules and Broadcasts. Selecting "
                    "this plan will deactivate them.",
                    num_active
                ) % {
                    'num_active': num_active,
                }
            )

    @staticmethod
    def response_inbound_sms(domain, new_plan_version):
        """
        All Reminder rules utilizing "survey" will be deactivated.
        """
        num_survey = (
            len(_get_active_immediate_broadcasts(domain, survey_only=True)) +
            len(_get_active_scheduled_broadcasts(domain, survey_only=True)) +
            len(_get_active_scheduling_rules(domain, survey_only=True))
        )
        if num_survey > 0:
            return _fmt_alert(
                ungettext(
                    "You have %(num_active)d active Reminder Rule or Broadcast which uses a Survey. "
                    "Selecting this plan will deactivate it.",
                    "You have %(num_active)d active Reminder Rules and Broadcasts which use a Survey. "
                    "Selecting this plan will deactivate them.",
                    num_survey
                ) % {
                    'num_active': num_survey,
                }
            )

    @staticmethod
    def response_deidentified_data(project, new_plan_version):
        """
        De-id exports will be hidden
        """
        from corehq.apps.export.dbaccessors import get_deid_export_count
        num_deid_reports = get_deid_export_count(project.name)
        if num_deid_reports > 0:
            return _fmt_alert(
                ungettext(
                    "You have %(num)d De-Identified Export. Selecting this "
                    "plan will remove it.",
                    "You have %(num)d De-Identified Exports. Selecting this "
                    "plan will remove them.",
                    num_deid_reports
                ) % {
                    'num': num_deid_reports,
                }
            )

    @property
    def response_mobile_worker_creation(self):
        """
        Get the allowed number of mobile workers based on plan version.
        """
        from corehq.apps.accounting.models import FeatureType, FeatureRate, UNLIMITED_FEATURE_USAGE
        num_users = CommCareUser.total_by_domain(self.domain.name, is_active=True)
        try:
            user_rate = self.new_plan_version.feature_rates.filter(
                feature__feature_type=FeatureType.USER).latest('date_created')
            if user_rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
                return
            num_allowed = user_rate.monthly_limit
            num_extra = num_users - num_allowed
            if num_extra > 0:
                from corehq.apps.accounting.models import DefaultProductPlan
                if self.new_plan_version != DefaultProductPlan.get_default_plan_version():
                    return _fmt_alert(
                        ungettext(
                            "You have %(num_extra)d Mobile Worker over the monthly "
                            "limit of %(monthly_limit)d for this new plan. There "
                            "will be an additional monthly charge of USD "
                            "%(excess_fee)s per Mobile Worker, totalling USD "
                            "%(monthly_total)s per month, if you select this plan.",

                            "You have %(num_extra)d Mobile Workers over the "
                            "monthly limit of %(monthly_limit)d for this new plan. "
                            "There will be an additional monthly charge "
                            "of USD %(excess_fee)s per Mobile Worker, totalling "
                            "USD %(monthly_total)s per month, if you "
                            "select this plan.",
                            num_extra
                        ) % {
                            'num_extra': num_extra,
                            'monthly_limit': user_rate.monthly_limit,
                            'excess_fee': user_rate.per_excess_fee,
                            'monthly_total': user_rate.per_excess_fee * num_extra,
                        }
                    )
                else:
                    return _fmt_alert(
                        ungettext(
                            "Community plans include %(monthly_limit)s Mobile Workers by default. "
                            "Because you have %(num_extra)d extra Mobile Worker, "
                            "all your project's Mobile Workers will be deactivated. "
                            "You can re-activate these manually after downgrade. "
                            "Each active Mobile Worker over %(monthly_limit)s will result "
                            "in an additional charge of USD %(excess_fee)s, totalling "
                            "USD %(monthly_total)s per month.",

                            "Community plans include %(monthly_limit)s Mobile Workers by default. "
                            "Because you have %(num_extra)d extra Mobile Workers, "
                            "all your project's Mobile Workers will be deactivated. "
                            "You can re-activate these manually after downgrade. "
                            "Each active Mobile Worker over %(monthly_limit)s will result "
                            "in an additional charge of USD %(excess_fee)s, totalling "
                            "USD %(monthly_total)s per month.",
                            num_extra
                        ) % {
                            'num_extra': num_extra,
                            'monthly_limit': user_rate.monthly_limit,
                            'excess_fee': user_rate.per_excess_fee,
                            'monthly_total': user_rate.per_excess_fee * num_extra,
                        }
                    )
        except FeatureRate.DoesNotExist:
            log_accounting_error(
                "It seems that the plan %s did not have rate for Mobile "
                "Workers. This is problematic."
                % self.new_plan_version.plan.name
            )

    @staticmethod
    def response_role_based_access(domain, new_plan_version):
        """
        Alert the user if there are currently custom roles set up for the domain.
        """
        custom_roles = [role.name for role in get_custom_roles_for_domain(domain.name)]
        num_roles = len(custom_roles)
        from corehq.apps.accounting.models import SoftwarePlanEdition
        if new_plan_version.plan.edition == SoftwarePlanEdition.PAUSED:
            # don't perform this downgrade for paused plans, as we don't want
            # users to lose their original role assignments when the plan is un-paused.
            return
        if num_roles > 0:
            return _fmt_alert(
                ungettext(
                    "You have %(num_roles)d Custom Role configured for your "
                    "project. If you select this plan, all users with that "
                    "role will change to having the Read Only role.",
                    "You have %(num_roles)d Custom Roles configured for your "
                    "project . If you select this plan, all users with these "
                    "roles will change to having the Read Only role.",
                    num_roles
                ) % {
                    'num_roles': num_roles,
                }, custom_roles)

    @property
    def response_later_subscription(self):
        """
        Alert the user if they have subscriptions scheduled to start
        in the future.
        """
        from corehq.apps.accounting.models import (
            Subscription,
            SoftwarePlanEdition,
        )
        later_subs = Subscription.visible_objects.filter(
            subscriber__domain=self.domain.name,
            date_start__gt=self.date_start,
        ).exclude(
            plan_version__plan__edition=SoftwarePlanEdition.PAUSED,
        ).order_by('date_start')
        if later_subs.exists():
            for next_subscription in later_subs:
                if next_subscription.date_start != next_subscription.date_end:
                    plan_desc = next_subscription.plan_version.user_facing_description
                    return _fmt_alert(_(
                        "You have a subscription SCHEDULED TO START on %(date_start)s. "
                        "Changing this plan will CANCEL that %(plan_name)s "
                        "subscription."
                    ) % {
                        'date_start': next_subscription.date_start.strftime(USER_DATE_FORMAT),
                        'plan_name': plan_desc['name'],
                    })

    @staticmethod
    def response_data_cleanup(domain, new_plan_version):
        """
        Any active automatic case update rules should be deactivated.
        """
        rule_count = AutomaticUpdateRule.by_domain(
            domain.name,
            AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        ).count()
        if rule_count > 0:
            return _fmt_alert(
                ungettext(
                    "You have %(rule_count)d automatic case update rule "
                    "configured in your project. If you select this plan, "
                    "this rule will be deactivated.",
                    "You have %(rule_count)d automatic case update rules "
                    "configured in your project. If you select this plan, "
                    "these rules will be deactivated.",
                    rule_count
                ) % {
                    'rule_count': rule_count,
                }
            )

    @staticmethod
    def response_domain_security(domain, new_plan_version):
        """
        turn off any domain enforced security features and alert user of deactivated features
        """
        two_factor = domain.two_factor_auth
        secure_sessions = domain.secure_sessions
        strong_mobile_passwords = domain.strong_mobile_passwords
        msgs = []
        if secure_sessions:
            msgs.append(_("Your project has enabled a {} minute session timeout setting. "
                          "By changing to a different plan, you will lose the ability to "
                          "enforce this shorter timeout policy.").format(Domain.secure_timeout(domain.name)))
        if two_factor:
            msgs.append(_("Two factor authentication is currently required of all of your "
                          "web users for this project space.  By changing to a different "
                          "plan you will lose the ability to enforce this requirement. "
                          "However, any web user who still wants to use two factor "
                          "authentication will be able to continue using it."))
        if strong_mobile_passwords:
            msgs.append(_("Your project currently requires all mobile workers to have "
                          "strong passwords. By changing to a different plan, you will "
                          "lose the ability to enforce these password requirements."))
        if msgs:
            return _fmt_alert(
                _("The following security features will be affected if you select this plan:"),
                msgs
            )

    @staticmethod
    def response_report_builder(project, new_plan_version):
        if not _has_report_builder_add_on(new_plan_version):
            reports = _get_report_builder_reports(project)
            if reports:
                return _fmt_alert(_(
                    "You have %(number_of_reports)d report builder reports. "
                    "By selecting this plan you will lose access to those reports."
                ) % {'number_of_reports': len(reports)})

    @staticmethod
    def response_practice_mobile_workers(project, new_plan_version):
        from corehq.apps.app_manager.views.utils import get_practice_mode_configured_apps
        apps = get_practice_mode_configured_apps(project.name)
        if not apps:
            return None
        return _fmt_alert(
            ungettext(
                "You have %(num_apps)d application that has a practice mobile worker "
                "configured, it will be unset on downgrade.",
                "You have %(num_apps)d applications that has a practice mobile worker "
                "configured, it will be unset on downgrade.",
                len(apps)
            ) % {
                'num_apps': len(apps),
            },
            [
                format_html(
                    '<a href="{}">{}</a>',
                    reverse('view_app', args=[project.name, app['_id']]),
                    app['name']
                ) for app in apps
            ],
        )
