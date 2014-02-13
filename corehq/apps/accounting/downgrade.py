import json
import logging
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext
from corehq import privileges, Domain
from corehq.apps.app_manager.models import Application
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.orgs.models import Organization
from corehq.apps.reminders.models import CaseReminderHandler, RECIPIENT_SURVEY_SAMPLE, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY
from corehq.apps.users.models import CommCareUser, UserRole
from couchexport.models import SavedExportSchema
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized

global_logger = logging.getLogger(__name__)


class BaseDowngradeHandler(object):
    supported_privileges = []

    def __init__(self, domain, new_plan_version, downgraded_privileges):
        if isinstance(downgraded_privileges, set):
            downgraded_privileges = list(downgraded_privileges)
        if not isinstance(domain, Domain):
            domain = Domain.get_by_name(domain)
        self.domain = domain

        # plan dependent privilege
        downgraded_privileges.append(privileges.MOBILE_WORKER_CREATION)

        self.privileges = filter(lambda x: x in self.supported_privileges, downgraded_privileges)
        self.new_plan_version = new_plan_version

    def get_response(self):
        response = []
        for priv in self.privileges:
            message = getattr(self, 'response_%s' % priv)
            if message is not None:
                response.append(message)
        return response


class DomainDowngradeActionHandler(BaseDowngradeHandler):
    """
    This carries out the downgrade action based on each privilege.

    Each response should return a boolean.

    # todo implement
    """

    def get_response(self):
        response = super(DomainDowngradeActionHandler, self).get_response()
        return len(filter(lambda x: not x, response)) == 0


class DomainDowngradeStatusHandler(BaseDowngradeHandler):
    """
    This returns a list of alerts for the user if their current domain is using features that
    will be removed during the downgrade.
    """
    supported_privileges = [
        privileges.CLOUDCARE,
        privileges.LOOKUP_TABLES,
        privileges.CUSTOM_BRANDING,
        privileges.CROSS_PROJECT_REPORTS,
        privileges.OUTBOUND_SMS,
        privileges.INBOUND_SMS,
        privileges.DEIDENTIFIED_DATA,
        privileges.MOBILE_WORKER_CREATION,
        privileges.ROLE_BASED_ACCESS,
    ]

    def _fmt_alert(self, message, details=None):
        if details is not None and not isinstance(details, list):
            raise ValueError("details should be a list.")
        return {
            'message': message,
            'details': details,
        }

    @property
    def response_cloudcare(self):
        """
        CloudCare enabled apps will have cloudcare_enabled set to false on downgrade.
        """
        key = [self.domain.name]
        db = Application.get_db()
        domain_apps = db.view(
            'app_manager/applications_brief',
            reduce=False,
            startkey=key,
            endkey=key + [{}],
        ).all()

        cloudcare_enabled_apps = []
        for app_doc in iter_docs(db, [a['id'] for a in domain_apps]):
            if app_doc.get('cloudcare_enabled', False):
                cloudcare_enabled_apps.append((app_doc['_id'], app_doc['name']))

        if not cloudcare_enabled_apps:
            return None

        num_apps = len(cloudcare_enabled_apps)
        return self._fmt_alert(
            ungettext(
                "You have %(num_apps)d application that will lose CloudCare access if you select this plan.",
                "You have %(num_apps)d applications that will lose CloudCare access if you select this plan.",
                num_apps
            ) % {
                'num_apps': num_apps,
            },
            [mark_safe('<a href="%(url)s">%(title)s</a>') % {
                'title': a[1],
                'url': reverse('view_app', args=[self.domain.name, a[0]])
            } for a in cloudcare_enabled_apps],
        )

    @property
    def response_lookup_tables(self):
        """
        Lookup tables will be deleted on downgrade.
        """
        num_fixtures = FixtureDataType.get_db().view(
            'fixtures/data_types_by_domain',
            reduce=True,
            key=self.domain.name,
        ).first()
        num_fixtures = num_fixtures['value'] if num_fixtures is not None else 0
        if num_fixtures > 0:
            return self._fmt_alert(
                ungettext(
                    "You have %(num_fix)s Lookup Table set up. Selecting this plan will delete this Lookup Table.",
                    "You have $(num_fix)s Lookup Tables set up. Selecting this plan will delete these Lookup Tables.",
                    num_fixtures
                ) % {'num_fix': num_fixtures}
            )

    @property
    def response_custom_branding(self):
        """
        Custom logos will be removed on downgrade.
        """
        if self.domain.has_custom_logo:
            return self._fmt_alert(_("You are using custom branding. Selecting this plan will remove this feature."))

    @property
    def response_cross_project_reports(self):
        """
        Organization menu and corresponding reports are hidden on downgrade.
        """
        if self.domain.organization:
            org = Organization.get_by_name(self.domain.organization)
            return self._fmt_alert(
                _("You will lose access to cross-project reports for the organization '%(org_name)s'.") % {
                    'org_name': org.title,
                })

    @property
    @memoized
    def _active_reminder_methods(self):
        db = CaseReminderHandler.get_db()
        key = [self.domain.name]
        reminder_rules = db.view(
            'reminders/handlers_by_reminder_type',
            startkey=key,
            endkey=key+[{}],
            reduce=False
        ).all()
        recipients = []
        for reminder_doc in iter_docs(db, [r['id'] for r in reminder_rules]):
            if reminder_doc['active']:
                recipients.append(reminder_doc['method'])
        return recipients

    @property
    def response_outbound_sms(self):
        """
        Reminder rules will be deactivated.
        """
        num_active = len(self._active_reminder_methods)
        if num_active > 0:
            return self._fmt_alert(
                ungettext(
                    "You have %(num_active)d active Reminder Rule. Selecting this plan will deactivate this rule.",
                    "You have %(num_active)d active Reminder Rules. Selecting this plan will deactivate these rules.",
                    num_active
                ) % {
                    'num_active': num_active,
                }
            )

    @property
    def response_inbound_sms(self):
        """
        All Reminder rules utilizing "survey" will be deactivated.
        """
        surveys = filter(lambda x: x in [METHOD_IVR_SURVEY, METHOD_SMS_SURVEY], self._active_reminder_methods)
        num_survey = len(surveys)
        if num_survey > 0:
            return self._fmt_alert(
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

    @property
    def response_deidentified_data(self):
        """
        De-id exports will be hidden
        """
        startkey = json.dumps([self.domain.name, ""])[:-3]
        endkey = "%s{" % startkey
        num_deid_reports = SavedExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey,
            endkey=endkey,
            include_docs=False,
        ).count()
        if num_deid_reports > 0:
            return self._fmt_alert(
                ungettext(
                    "You have %(num)d De-Identified Export. Selecting this plan will remove it.",
                    "You have %(num)d De-Identified Exports. Selecting this plan will remove them.",
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
        from corehq.apps.accounting.models import FeatureType, FeatureRate
        num_users = CommCareUser.total_by_domain(self.domain.name, is_active=True)
        try:
            user_rate = self.new_plan_version.feature_rates.filter(
                feature__feature_type=FeatureType.USER).latest('date_created')
            num_allowed = user_rate.monthly_limit
            num_extra = num_users - num_allowed
            if num_extra > 0:
                return self._fmt_alert(
                    ungettext(
                        "You have %(num_users)d Mobile Worker over the monthly limit of %(monthly_limit)d for "
                        "this new plan. There will be an additional monthly charge of USD %(excess_fee)s per "
                        "Mobile Worker, totalling USD %(monthly_total)s per month, if you select this plan.",
                        "You have %(num_users)d Mobile Workers over the monthly limit of %(monthly_limit)d for "
                        "this new plan. There will be an additional monthly charge of USD %(excess_fee)s per "
                        "Mobile Worker, totalling USD %(monthly_total)s per month, if you select this plan.",
                        num_extra
                    ) % {
                        'num_users': num_extra,
                        'monthly_limit': user_rate.monthly_limit,
                        'excess_fee': user_rate.per_excess_fee,
                        'monthly_total': user_rate.per_excess_fee * num_extra,
                    }
                )
        except FeatureRate.DoesNotExist:
            global_logger.error(
                "It seems that the plan %s did not have rate for Mobile Workers. This is problematic." %
                    self.new_plan_version.plan.name
                )

    @property
    def response_role_based_access(self):
        """
        Alert the user if there are currently custom roles set up for the domain.
        """
        db = UserRole.get_db()
        user_roles_query = db.view(
            'users/roles_by_domain',
            startkey=[self.domain.name],
            endkey=[self.domain.name, {}],
            reduce=False,
        ).all()
        user_role_ids = [r['id'] for r in user_roles_query]

        EDIT_WEB_USERS = 'edit_web_users'
        EDIT_CC_USERS = 'edit_commcare_users'
        EDIT_APPS = 'edit_apps'
        EDIT_DATA = 'edit_data'
        VIEW_REPORTS = 'view_reports'

        STD_ROLES = {
            'Read Only': {
                'on': [VIEW_REPORTS],
                'off': [EDIT_DATA, EDIT_APPS, EDIT_CC_USERS, EDIT_WEB_USERS],
            },
            'Field Implementer': {
                'on': [VIEW_REPORTS, EDIT_CC_USERS],
                'off': [EDIT_DATA, EDIT_APPS, EDIT_WEB_USERS],
            },
            'App Editor': {
                'on': [VIEW_REPORTS, EDIT_APPS],
                'off': [EDIT_DATA, EDIT_WEB_USERS, EDIT_CC_USERS],
            }
        }

        def _is_custom_role(doc):
            role_name = doc['name']
            if not role_name in STD_ROLES.keys():
                return True
            doc_perms = doc['permissions']
            if len(doc_perms['view_report_list']) > 0:
                return True
            std_perms = STD_ROLES[role_name]
            def _is_match(status, val):
                return sum([doc_perms[k] == val for k in std_perms[status]]) == len(std_perms[status])
            if not _is_match('on', True):
                return True
            if not _is_match('off', False):
                return True
            return False

        custom_roles = []
        for role_doc in iter_docs(db, user_role_ids):
            if _is_custom_role(role_doc):
                custom_roles.append(role_doc['name'])

        num_roles = len(custom_roles)
        if num_roles > 0:
            return self._fmt_alert(
                ungettext(
                    "You have %(num_roles)d Custom Role configured for your project. If you "
                    "select this plan, all users with that role will change to having the Read Only role.",
                    "You have %(num_roles)d Custom Roles configured for your project . If you "
                    "select this plan, all users with these roles will change to having the Read Only role.",
                    num_roles
                ) % {
                    'num_roles': num_roles,
                }, custom_roles)
