import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand

from django_prbac.models import Role

from corehq import privileges
from corehq.apps.accounting.utils import ensure_grants, log_removed_grants
from corehq.apps.accounting.bootstrap import features

logger = logging.getLogger(__name__)


BULK_CASE_AND_USER_MANAGEMENT = 'bulk_case_and_user_management'
CROSS_PROJECT_REPORTS = 'cross_project_reports'


def cchq_prbac_bootstrap(apps, schema_editor):
    """Convenience function for use in data migrations.
    Example operation:
        migrations.RunPython(cchq_prbac_bootstrap)
    """
    call_command('cchq_prbac_bootstrap')


class Command(BaseCommand):
    help = 'Populate a fresh database with some sample roles and grants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what happen',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Enable debug output',
        )
        parser.add_argument(
            '--fresh-start',
            action='store_true',
            default=False,
            help='We changed the core v0 plans, wipe all existing plans and start over. USE CAUTION.',
        )

    def handle(self, dry_run=False, verbose=False, fresh_start=False, **options):
        self.verbose = verbose

        if fresh_start:
            confirm_fresh_start = input(
                "Are you sure you want to delete all Roles and start over? You can't do this"
                " if accounting is already set up. Type 'yes' to continue."
            )
            if confirm_fresh_start == 'yes':
                self.flush_roles()

        self.roles_by_slug = {role.slug: role for role in Role.objects.all()}
        self.ensure_roles(self.BOOTSTRAP_PRIVILEGES + self.BOOTSTRAP_PLANS, dry_run)

        ensure_grants(
            list(self.BOOTSTRAP_GRANTS.items()),  # py3 iterable
            dry_run=dry_run,
            verbose=self.verbose,
            roles_by_slug=self.roles_by_slug,
        )

        if verbose or dry_run:
            log_removed_grants(self.OLD_PRIVILEGES, dry_run=dry_run)
        if not dry_run:
            Role.objects.filter(slug__in=self.OLD_PRIVILEGES).delete()

    def flush_roles(self):
        logger.info('Flushing ALL Roles...')
        Role.objects.all().delete()

    def ensure_roles(self, roles, dry_run=False):
        """
        Add each role if it does not already exist, otherwise skip it.
        """
        dry_run_tag = "[DRY RUN] " if dry_run else ""
        roles_to_save = []
        for role in roles:
            if role.slug not in self.roles_by_slug:
                if self.verbose or dry_run:
                    logger.info('%sCreating role: %s', dry_run_tag, role.name)
                if not dry_run:
                    roles_to_save.append(role)
            else:
                logger.info('Role already exists: %s', role.name)
        if roles_to_save:
            roles = Role.objects.bulk_create(roles_to_save)
            self.roles_by_slug.update((role.slug, role) for role in roles)

    BOOTSTRAP_PRIVILEGES = [
        Role(slug=privileges.API_ACCESS, name='API Access', description=''),
        Role(slug=privileges.LOOKUP_TABLES, name='Lookup Tables', description=''),
        Role(slug=privileges.CLOUDCARE, name='Web-based Applications (CloudCare)', description=''),
        Role(slug=privileges.CUSTOM_BRANDING, name='Custom Branding', description=''),
        Role(slug=privileges.ACTIVE_DATA_MANAGEMENT, name='Active Data Management', description=''),
        Role(slug=privileges.CUSTOM_REPORTS, name='Custom Reports', description=''),
        Role(slug=privileges.ROLE_BASED_ACCESS, name='Role-based Access', description=''),
        Role(slug=privileges.RESTRICT_ACCESS_BY_LOCATION, name='Restrict Access By Location', description=''),
        Role(
            slug=privileges.OUTBOUND_SMS, name='Outbound SMS',
            description='Use of any outbound messaging / SMS services.',
        ),
        Role(
            slug=privileges.REMINDERS_FRAMEWORK, name='Rules Engine (Use of Reminders Framework)',
            description='Use of reminders framework for spawning reminders/alerts based on certain criteria.',
        ),
        Role(
            slug=privileges.CUSTOM_SMS_GATEWAY, name='Custom Telerivet (Android) SMS Gateway',
            description='Ability to set up telerivet gateway on the "SMS Connectivity" page '
                        '(inbound or outbound).',
        ),
        Role(slug=privileges.INBOUND_SMS, name='Inbound SMS (where available)', description=''),
        Role(slug=privileges.BULK_CASE_MANAGEMENT, name='Bulk Case Management', description=''),
        Role(slug=privileges.BULK_USER_MANAGEMENT, name='Bulk User Management', description=''),
        Role(slug=privileges.DEIDENTIFIED_DATA, name='De-identified Data', description=''),
        Role(slug=privileges.HIPAA_COMPLIANCE_ASSURANCE, name='HIPAA Compliance Assurance', description=''),
        Role(slug=privileges.ALLOW_EXCESS_USERS, name='Can Add Users Above Limit', description=''),
        Role(slug=privileges.COMMCARE_LOGO_UPLOADER, name='Custom CommCare Logo Uploader', description=''),
        Role(slug=privileges.LOCATIONS, name='Locations', description=''),
        Role(slug=privileges.REPORT_BUILDER, name='User Configurable Report Builder', description=''),
        Role(slug=privileges.REPORT_BUILDER_TRIAL, name='Report Builder Trial', description=''),
        Role(slug=privileges.REPORT_BUILDER_5, name='Report Builder, 5 report limit', description=''),
        Role(slug=privileges.REPORT_BUILDER_15, name='Report Builder, 15 report limit', description=''),
        Role(slug=privileges.REPORT_BUILDER_30, name='Report Builder, 30 report limit', description=''),
        Role(slug=privileges.USERCASE, name='User Case Management', description=''),
        Role(slug=privileges.DATA_CLEANUP, name='Data Management',
             description='Tools for cleaning up data, including editing submissions and archiving forms.'),
        Role(slug=privileges.TEMPLATED_INTENTS, name='Templated Intents',
             description='Provides a dropdown for Android App Callouts'),
        Role(slug=privileges.CUSTOM_INTENTS, name='Custom Intents',
             description='Allows for specifying custom intents'),
        Role(slug=privileges.ADVANCED_DOMAIN_SECURITY, name='Advanced Domain Security',
             description='Allows domains to set security policies for all web users'),
        Role(slug=privileges.PRACTICE_MOBILE_WORKERS, name='Practice mode for mobile workers',
             description='Allows turning on practice mode for mobile workers and link them to applications'),
        Role(slug=privileges.BUILD_PROFILES, name='Application Profiles',
             description='Allows domains to create application profiles to customize app deploys'),
        Role(slug=privileges.EXCEL_DASHBOARD, name="Excel Dashbord",
             description="Allows domains to create Excel dashboard html exports"),
        Role(slug=privileges.DAILY_SAVED_EXPORT, name='DAILY_SAVED_EXPORT',
             description="Allows domains to create Daily Saved Exports"),
        Role(slug=privileges.ZAPIER_INTEGRATION, name='Zapier Integration',
             description='Allows domains to use zapier (zapier.com) integration'),
        Role(slug=privileges.LOGIN_AS, name='Log In As for App Preview',
             description='Allows domains to use the Log In As feature of App Preview'),
        Role(slug=privileges.CASE_SHARING_GROUPS,
             name='Case Sharing via Groups',
             description='Allows turning on case sharing between members in a group.'),
        Role(slug=privileges.CHILD_CASES,
             name='Child Cases',
             description='Allows for use of child cases / subcases in applications.'),
        Role(slug=privileges.ODATA_FEED,
             name='OData Feed - Tableau / BI Integration',
             description='Allows usage of Tableau / BI Integration (OData Feeds)'),
        Role(slug=privileges.DATA_FORWARDING,
             name='Data Forwarding',
             description='Allows use of Data Forwarding'),
        Role(slug=privileges.PROJECT_ACCESS,
             name='Project Access',
             description='Allows access to core project functionality.'),
        Role(slug=privileges.APP_USER_PROFILES,
             name='App User Profiles',
             description='Allows use of App User Profiles.'),
        Role(slug=privileges.GEOCODER, name='Geocoder', description='Address widget in Web Apps.'),
        Role(slug=privileges.DEFAULT_EXPORT_SETTINGS,
             name='Default Export Settings',
             description='Allows ability to set default values for newly created exports.'),
        Role(slug=privileges.RELEASE_MANAGEMENT,
             name='Release Management',
             description='Allows access to features that help manage releases between projects, like the linked '
                         'projects feature.'),
        Role(slug=privileges.LITE_RELEASE_MANAGEMENT,
             name='Lite Release Management',
             description='A limited version of Release Management'),
        Role(slug=privileges.LOADTEST_USERS,
             name='Loadtest Users',
             description='Allows creating loadtest users'),
        Role(slug=privileges.FORM_LINK_WORKFLOW,
             name='Link to other forms',
             description='Link to other forms in End of Form Navigation'),
        Role(slug=privileges.PHONE_APK_HEARTBEAT,
             name='Phone Heartbeat',
             description='Ability to configure a mobile feature to prompt users to update to latest CommCare '
                         'app and apk'),
        Role(slug=privileges.VIEW_APP_DIFF,
             name='Improved app changes view',
             description='Ability to see changes that have been made between different versions of '
                         'your application'),
        Role(slug=privileges.DATA_FILE_DOWNLOAD,
             name='File Dropzone',
             description='Offer hosting and sharing data files for downloading '
                         'from a secure dropzone'),
        Role(slug=privileges.ATTENDANCE_TRACKING,
             name='Attendance Tracking',
             description='Supports using CommCare HQ for attendance tracking'),
        Role(slug=privileges.REGEX_FIELD_VALIDATION,
             name='Regular Field Validation',
             description='Regular field validation for custom data fields'),
        Role(slug=privileges.LOCATION_SAFE_CASE_IMPORTS,
             name='Location Safe Case Imports',
             description='Location-restricted users can import cases at their location or below'),
        Role(slug=privileges.FORM_CASE_IDS_CASE_IMPORTER,
             name='Download buttons for Form- and Case IDs on Case Importer',
             description='Display the "Form IDs" and "Case IDs" download buttons on Case Importer'),
        Role(slug=privileges.EXPORT_MULTISORT,
             name='Sort multiple rows in exports simultaneously',
             description='Sort multiple rows in exports simultaneously'),
        Role(slug=privileges.EXPORT_OWNERSHIP,
             name='Allow exports to have ownership',
             description='Allow exports to have ownership'),
        Role(slug=privileges.FILTERED_BULK_USER_DOWNLOAD,
             name='Bulk user management features',
             description='For mobile users, enables bulk deletion page and bulk lookup page. '
                         'For web users, enables filtered download page.'),
        Role(slug=privileges.APPLICATION_ERROR_REPORT,
             name='Application error report',
             description='Show Application Error Report'),
        Role(slug=privileges.DATA_DICTIONARY,
             name='Data dictionary',
             description='Project level data dictionary of cases'),
        Role(slug=privileges.CASE_LIST_EXPLORER,
             name='Case List Explorer',
             description='Show Case List Explorer under Inspect Data in Reports'),
        Role(slug=privileges.CASE_COPY,
             name='Allow Case Copy',
             description='Allow case copy from one user to another'),
        Role(slug=privileges.CASE_DEDUPE,
             name='Deduplication Rules',
             description='Support for finding duplicate cases'),
        Role(slug=privileges.CUSTOM_DOMAIN_ALERTS,
             name='Custom Domain Banners',
             description='Allow projects to add banners for their users on CommCare HQ'),
    ]

    BOOTSTRAP_PLANS = [
        Role(slug='paused_plan_v0', name='Paused Plan', description=''),
        Role(slug='community_plan_v0', name='Community Plan', description=''),
        Role(slug='community_plan_v1', name='Community Plan', description=''),
        Role(slug='community_plan_v2', name='Community Plan', description=''),
        Role(slug='standard_plan_v0', name='Standard Plan', description=''),
        Role(slug='standard_plan_v1', name='Standard Plan', description=''),
        Role(slug='pro_plan_v0', name='Pro Plan', description=''),
        Role(slug='pro_plan_v1', name='Pro Plan', description=''),
        Role(slug='advanced_plan_v0', name='Advanced Plan', description=''),
        Role(slug='enterprise_plan_v0', name='Enterprise Plan', description=''),
    ] + [
        Role(slug='standard_plan_report_builder_v0', name='Standard Plan - 5 Reports', description=''),
        Role(slug='pro_plan_report_builder_v0', name='Pro Plan - 5 Reports', description=''),
        Role(slug='advanced_plan_report_builder_v0', name='Advanced Plan - 5 Reports', description=''),
    ]

    OLD_PRIVILEGES = [
        BULK_CASE_AND_USER_MANAGEMENT,
        CROSS_PROJECT_REPORTS,
    ]

    BOOTSTRAP_GRANTS = {
        'paused_plan_v0': features.paused_v0,
        'community_plan_v0': features.community_v0,
        'community_plan_v1': features.community_v1,
        'community_plan_v2': features.community_v2,
        'standard_plan_v0': features.standard_v0,
        'standard_plan_v1': features.standard_v1,
        'pro_plan_v0': features.pro_v0,
        'pro_plan_v1': features.pro_v1,
        'advanced_plan_v0': features.advanced_v0,
        'enterprise_plan_v0': features.enterprise_v0,
    }
