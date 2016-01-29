import json
import datetime
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext # probably only use one
from corehq import privileges
from corehq.apps.accounting.utils import (
    get_active_reminders_by_domain_name,
    log_accounting_error,
    log_accounting_info,
)
from corehq.apps.app_manager.dbaccessors import get_all_apps
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.reminders.models import METHOD_SMS_SURVEY, METHOD_IVR_SURVEY
from corehq.apps.users.models import CommCareUser, UserRole
from corehq.const import USER_DATE_FORMAT
from couchexport.models import SavedExportSchema
from dimagi.utils.couch.database import iter_docs # cleanup imports
from dimagi.utils.decorators.memoized import memoized


LATER_SUBSCRIPTION_NOTIFICATION = 'later_subscription'


class BaseModifySubscriptionHandler(object):
    supported_privileges = []
    action_type = "base"

    def __init__(self, domain, new_plan_version, changed_privs, verbose=False,
                 date_start=None, web_user=None):
        self.web_user = web_user
        self.verbose = verbose
        self.date_start = date_start or datetime.date.today()
        if isinstance(changed_privs, set):
            changed_privs = list(changed_privs)
        if not isinstance(domain, Domain):
            domain = Domain.get_by_name(domain)
        self.domain = domain

        # plan dependent privilege
        changed_privs.append(privileges.MOBILE_WORKER_CREATION)

        # check to make sure that no subscriptions are scheduled to
        # start in the future
        changed_privs.append(LATER_SUBSCRIPTION_NOTIFICATION)

        self.privileges = filter(lambda x: x in self.supported_privileges, changed_privs)
        self.new_plan_version = new_plan_version

    def get_response(self):
        response = []
        for priv in self.privileges:
            if self.verbose:
                log_accounting_info("Applying %s %s." % (priv, self.action_type))
            message = getattr(self, 'response_%s' % priv)
            if message is not None:
                response.append(message)
        return response


class BaseModifySubscriptionActionHandler(BaseModifySubscriptionHandler):
    def get_response(self):
        response = super(BaseModifySubscriptionActionHandler, self).get_response()
        return len(filter(lambda x: not x, response)) == 0


class DomainDowngradeActionHandler(BaseModifySubscriptionActionHandler):
    """
    This carries out the downgrade action based on each privilege.

    Each response should return a boolean.
    """
    supported_privileges = [
        privileges.OUTBOUND_SMS,
        privileges.INBOUND_SMS,
        privileges.ROLE_BASED_ACCESS,
        privileges.DATA_CLEANUP,
        privileges.COMMCARE_LOGO_UPLOADER,
    ]
    action_type = "downgrade"

    @property
    @memoized
    def _active_reminders(self):
        return get_active_reminders_by_domain_name(self.domain.name)

    @property
    def response_outbound_sms(self):
        """
        Reminder rules will be deactivated.
        """
        try:
            for reminder in self._active_reminders:
                reminder.active = False
                reminder.save()
                if self.verbose:
                    log_accounting_info(
                        "Deactivated Reminder %s [%s]"
                        % (reminder.nickname, reminder._id)
                    )
        except Exception:
            log_accounting_error(
                "Failed to downgrade outbound sms for domain %s."
                % self.domain.name
            )
            return False
        return True

    @property
    def response_inbound_sms(self):
        """
        All Reminder rules utilizing "survey" will be deactivated.
        """
        try:
            surveys = filter(lambda x: x.method in [METHOD_IVR_SURVEY, METHOD_SMS_SURVEY], self._active_reminders)
            for survey in surveys:
                survey.active = False
                survey.save()
                if self.verbose:
                    log_accounting_info(
                        "Deactivated Survey %s [%s]"
                        % (survey.nickname, survey._id)
                    )
        except Exception:
            log_accounting_error(
                "Failed to downgrade outbound sms for domain %s."
                % self.domain.name
            )
            return False
        return True

    @property
    def response_role_based_access(self):
        """
        Perform Role Based Access Downgrade
        - Archive custom roles.
        - Set user roles using custom roles to Read Only.
        - Reset initial roles to standard permissions.
        """
        custom_roles = [r.get_id for r in UserRole.get_custom_roles_by_domain(self.domain.name)]
        if not custom_roles:
            return True
        if self.verbose:
            for role in custom_roles:
                log_accounting_info("Archiving Custom Role %s" % role)
        # temporarily disable this part of the downgrade until we
        # have a better user experience for notifying the downgraded user
        # read_only_role = UserRole.get_read_only_role_by_domain(self.domain.name)
        # web_users = WebUser.by_domain(self.domain.name)
        # for web_user in web_users:
        #     if web_user.get_domain_membership(self.domain.name).role_id in custom_roles:
        #         web_user.set_role(self.domain.name, read_only_role.get_qualified_id())
        #         web_user.save()
        # for cc_user in CommCareUser.by_domain(self.domain.name):
        #     if cc_user.get_domain_membership(self.domain.name).role_id in custom_roles:
        #         cc_user.set_role(self.domain.name, 'none')
        #         cc_user.save()
        UserRole.archive_custom_roles_for_domain(self.domain.name)
        UserRole.reset_initial_roles_for_domain(self.domain.name)
        return True

    @property
    def response_data_cleanup(self):
        """
        Any active automatic case update rules should be deactivated.
        """
        try:
            AutomaticUpdateRule.objects.filter(
                domain=self.domain.name,
                deleted=False,
                active=True,
            ).update(active=False)
            return True
        except Exception:
            log_accounting_error(
                "Failed to deactivate automatic update rules "
                "for domain %s." % self.domain.name
            )
            return False

    @property
    def response_commcare_logo_uploader(self):
        """Make sure no existing applications are using a logo.
        """
        try:
            for app in get_all_apps(self.domain.name):
                has_archived = app.archive_logos()
                if has_archived:
                    app.save()
            return True
        except Exception:
            log_accounting_error(
                "Failed to remove all commcare logos for domain %s."
                % self.domain.name
            )
            return False


class DomainUpgradeActionHandler(BaseModifySubscriptionActionHandler):
    """
    This carries out the upgrade action based on each privilege.

    Each response should return a boolean.
    """
    supported_privileges = [
        privileges.ROLE_BASED_ACCESS,
        privileges.COMMCARE_LOGO_UPLOADER,
    ]
    action_type = "upgrade"

    @property
    def response_role_based_access(self):
        """
        Perform Role Based Access Upgrade
        - Un-archive custom roles.
        """
        if self.verbose:
            num_archived_roles = len(UserRole.by_domain(self.domain.name,
                                                        is_archived=True))
            if num_archived_roles:
                log_accounting_info("Re-Activating %d archived roles." % num_archived_roles)
        UserRole.unarchive_roles_for_domain(self.domain.name)
        return True

    @property
    def response_commcare_logo_uploader(self):
        """Make sure no existing applications are using a logo.
        """
        try:
            for app in get_all_apps(self.domain.name):
                has_restored = app.restore_logos()
                if has_restored:
                    app.save()
            return True
        except Exception:
            log_accounting_error(
                "Failed to restore all commcare logos for domain %s."
                % self.domain.name
            )
            return False


def _fmt_downgrade_status_alert(message, details=None):
    if details is not None and not isinstance(details, list):
        raise ValueError("details should be a list.")
    return {
        'message': message,
        'details': details,
    }


def _active_reminder_methods(domain):
    reminder_rules = get_active_reminders_by_domain_name(domain.name)
    return [reminder.method for reminder in reminder_rules]


class DomainDowngradeStatusHandler(BaseModifySubscriptionHandler):
    """
    This returns a list of alerts for the user if their current domain is using features that
    will be removed during the downgrade.
    """
    action_type = "notification"

    def get_response(self):
        response = []
        for priv in self.privileges:
            if self.verbose:
                log_accounting_info("Applying %s %s." % (priv, self.action_type))
            message = self.privilege_to_response()[priv](self.domain)
            if message is not None:
                response.append(message)
        return response

    @staticmethod
    def response_cloudcare(domain):
        """
        CloudCare enabled apps will have cloudcare_enabled set to false on downgrade.
        """
        cloudcare_enabled_apps = get_cloudcare_apps(domain.name)
        if not cloudcare_enabled_apps:
            return None

        num_apps = len(cloudcare_enabled_apps)
        return _fmt_downgrade_status_alert(
            ungettext(
                "You have %(num_apps)d application that will lose CloudCare "
                "access if you select this plan.",
                "You have %(num_apps)d applications that will lose CloudCare "
                "access if you select this plan.",
                num_apps
            ) % {
                'num_apps': num_apps,
            },
            [
                mark_safe('<a href="%(url)s">%(title)s</a>') % {
                    'title': app['name'],
                    'url': reverse('view_app', args=[domain.name, app['_id']])
                }
                for app in cloudcare_enabled_apps
            ]
        )

    @staticmethod
    def response_lookup_tables(domain):
        """
        Lookup tables will be deleted on downgrade.
        """
        num_fixtures = FixtureDataType.total_by_domain(domain.name)
        if num_fixtures > 0:
            return _fmt_downgrade_status_alert(
                ungettext(
                    "You have %(num_fix)s Lookup Table set up. Selecting this "
                    "plan will delete this Lookup Table.",
                    "You have %(num_fix)s Lookup Tables set up. Selecting "
                    "this plan will delete these Lookup Tables.",
                    num_fixtures
                ) % {'num_fix': num_fixtures}
            )

    @staticmethod
    def response_custom_branding(domain):
        """
        Custom logos will be removed on downgrade.
        """
        if domain.has_custom_logo:
            return _fmt_downgrade_status_alert(
                _("You are using custom branding. Selecting this plan will remove this feature.")
            )

    @staticmethod
    def _active_reminder_methods(domain):
        reminder_rules = get_active_reminders_by_domain_name(domain.name)
        return [reminder.method for reminder in reminder_rules]

    @staticmethod
    def response_outbound_sms(domain):
        """
        Reminder rules will be deactivated.
        """
        num_active = len(_active_reminder_methods(domain))
        if num_active > 0:
            return _fmt_downgrade_status_alert(
                ungettext(
                    "You have %(num_active)d active Reminder Rule. Selecting "
                    "this plan will deactivate this rule.",
                    "You have %(num_active)d active Reminder Rules. Selecting "
                    "this plan will deactivate these rules.",
                    num_active
                ) % {
                    'num_active': num_active,
                }
            )

    @staticmethod
    def response_inbound_sms(domain):
        """
        All Reminder rules utilizing "survey" will be deactivated.
        """
        surveys = filter(
            lambda x: x in [METHOD_IVR_SURVEY, METHOD_SMS_SURVEY],
            _active_reminder_methods(domain)
        )
        num_survey = len(surveys)
        if num_survey > 0:
            return _fmt_downgrade_status_alert(
                ungettext(
                    "You have %(num_active)d active Reminder Rule for a Survey. "
                    "Selecting this plan will deactivate this rule.",
                    "You have %(num_active)d active Reminder Rules for a Survey. "
                    "Selecting this plan will deactivate these rules.",
                    num_survey
                ) % {
                    'num_active': num_survey,
                }
            )

    @staticmethod
    def response_deidentified_data(domain):
        """
        De-id exports will be hidden
        """
        startkey = json.dumps([domain.name, ""])[:-3]
        endkey = "%s{" % startkey
        reports = SavedExportSchema.view(
            "couchexport/saved_export_schemas",
            startkey=startkey,
            endkey=endkey,
            include_docs=True,
        )
        num_deid_reports = len(filter(lambda r: r.is_safe, reports))
        if num_deid_reports > 0:
            return _fmt_downgrade_status_alert(
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

    def response_mobile_worker_creation(cls, domain):
        """
        Get the allowed number of mobile workers based on plan version.
        """
        from corehq.apps.accounting.models import FeatureType, FeatureRate, UNLIMITED_FEATURE_USAGE
        num_users = CommCareUser.total_by_domain(domain.name, is_active=True)
        try:
            user_rate = self.new_plan_version.feature_rates.filter(
                feature__feature_type=FeatureType.USER).latest('date_created')
            if user_rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
                return
            num_allowed = user_rate.monthly_limit
            num_extra = num_users - num_allowed
            if num_extra > 0:
                return _fmt_downgrade_status_alert(
                    ungettext(
                        "You have %(num_users)d Mobile Worker over the monthly "
                        "limit of %(monthly_limit)d for this new plan. There "
                        "will be an additional monthly charge of USD "
                        "%(excess_fee)s per Mobile Worker, totalling USD "
                        "%(monthly_total)s per month, if you select this plan.",
                        "You have %(num_users)d Mobile Workers over the "
                        "monthly limit of %(monthly_limit)d for this new plan. "
                        "There will be an additional monthly charge "
                        "of USD %(excess_fee)s per Mobile Worker, totalling "
                        "USD %(monthly_total)s per month, if you "
                        "select this plan.",
                        num_extra
                    ) % {
                        'num_users': num_extra,
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
    def response_role_based_access(domain):
        """
        Alert the user if there are currently custom roles set up for the domain.
        """
        custom_roles = [r.name for r in UserRole.get_custom_roles_by_domain(domain.name)]
        num_roles = len(custom_roles)
        if num_roles > 0:
            return _fmt_downgrade_status_alert(
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
                },
                custom_roles
            )

    @property
    def response_later_subscription(self):
        """
        Alert the user if they have subscriptions scheduled to start
        in the future.
        """
        from corehq.apps.accounting.models import Subscription
        later_subs = Subscription.objects.filter(
            subscriber__domain=self.domain.name,
            date_start__gt=self.date_start
        ).order_by('date_start')
        if later_subs.exists():
            next_subscription = later_subs[0]
            plan_desc = next_subscription.plan_version.user_facing_description
            return _fmt_downgrade_status_alert(
                _(
                    "You have a subscription SCHEDULED TO START on %(date_start)s. "
                    "Changing this plan will CANCEL that %(plan_name)s "
                    "subscription."
                ) % {
                    'date_start': next_subscription.date_start.strftime(USER_DATE_FORMAT),
                    'plan_name': plan_desc['name'],
                }
            )

    @staticmethod
    def response_data_cleanup(domain):
        """
        Any active automatic case update rules should be deactivated.
        """
        rule_count = AutomaticUpdateRule.objects.filter(
            domain=domain.name,
            deleted=False,
            active=True,
        ).count()
        if rule_count > 0:
            return _fmt_downgrade_status_alert(
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

    @classmethod
    def privilege_to_response(cls):
        return {
            privileges.CLOUDCARE: cls.response_cloudcare,
            privileges.LOOKUP_TABLES: cls.response_lookup_tables,
            privileges.CUSTOM_BRANDING: cls.response_custom_branding,
            privileges.OUTBOUND_SMS: cls.response_outbound_sms,
            privileges.INBOUND_SMS: cls.response_inbound_sms,
            privileges.DEIDENTIFIED_DATA: cls.response_deidentified_data,
            # privileges.MOBILE_WORKER_CREATION, # TODO - add back
            privileges.ROLE_BASED_ACCESS: cls.response_role_based_access,
            privileges.DATA_CLEANUP: cls.response_data_cleanup,
            # LATER_SUBSCRIPTION_NOTIFICATION, # TODO - add back
            privileges.CUSTOM_REPORTS: _domain_has_custom_report,
            privileges.LOCATIONS: _domain_uses_locations,
            privileges.TEMPLATED_INTENTS: _domain_has_apps_using_templated_intents,
        }

    @property
    def supported_privileges(self):
        return self.privilege_to_response().keys()


def _domain_has_custom_report(domain):
    from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
    return bool(CustomProjectReportDispatcher().get_reports(domain.name))


def _domain_uses_locations(domain):
    return domain.uses_locations


def _domain_has_apps_using_templated_intents(domain):
    return any(any(form.wrapped_xform().odk_intents for form in app.get_forms()) for app in get_all_apps(domain))
