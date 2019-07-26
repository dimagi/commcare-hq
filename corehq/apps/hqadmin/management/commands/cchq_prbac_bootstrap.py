# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Standard library imports
import logging

# Django imports
from django.core.management import call_command
from django.core.management.base import BaseCommand

# External imports
from corehq import privileges
from corehq.apps.accounting.utils import ensure_grants, log_removed_grants
from django_prbac.models import Grant, Role
from six.moves import input

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
        Role(slug=privileges.OUTBOUND_SMS, name='Outbound SMS',
             description='Use of any outbound messaging / SMS services.',
        ),
        Role(slug=privileges.REMINDERS_FRAMEWORK, name='Rules Engine (Use of Reminders Framework)',
             description='Use of reminders framework for spawning reminders/alerts based on certain criteria.',
        ),
        Role(slug=privileges.CUSTOM_SMS_GATEWAY, name='Custom Telerivet (Android) SMS Gateway',
             description='Ability to set up telerivet gateway on the "SMS Connectivity" page (inbound or outbound).',
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
        Role(slug=privileges.USER_CASE, name='User Case Management', description=''),
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
        Role(slug=privileges.LOGIN_AS, name='Login As for App Preview',
             description='Allows domains to use the login as feature of app preview'),
        Role(slug=privileges.CASE_SHARING_GROUPS,
             name='Case Sharing via Groups',
             description='Allows turning on case sharing between members in a group.'),
        Role(slug=privileges.CHILD_CASES,
             name='Child Cases',
             description='Allows for use of child cases / subcases in applications.'),
    ]

    BOOTSTRAP_PLANS = [
        Role(slug='community_plan_v0', name='Community Plan', description=''),
        Role(slug='community_plan_v1', name='Community Plan', description=''),
        Role(slug='standard_plan_v0', name='Standard Plan', description=''),
        Role(slug='pro_plan_v0', name='Pro Plan', description=''),
        Role(slug='advanced_plan_v0', name='Advanced Plan', description=''),
        Role(slug='enterprise_plan_v0', name='Enterprise Plan', description=''),
    ] + [
        Role(slug='standard_plan_report_builder_v0', name='Standard Plan - 5 Reports', description=''),
        Role(slug='pro_plan_report_builder_v0', name='Pro Plan - 5 Reports', description=''),
        Role(slug='advanced_plan_report_builder_v0', name='Advanced Plan - 5 Reports', description=''),
    ]

    community_plan_v0_features = [
        privileges.EXCEL_DASHBOARD,
        privileges.DAILY_SAVED_EXPORT,
        privileges.CASE_SHARING_GROUPS,
        privileges.CHILD_CASES,
    ]

    community_plan_v1_features = [
        privileges.CASE_SHARING_GROUPS,
        privileges.CHILD_CASES,
    ]

    standard_plan_features = community_plan_v0_features + [
        privileges.API_ACCESS,
        privileges.LOOKUP_TABLES,
        privileges.OUTBOUND_SMS,
        privileges.REMINDERS_FRAMEWORK,
        privileges.CUSTOM_SMS_GATEWAY,
        privileges.ROLE_BASED_ACCESS,
        privileges.BULK_USER_MANAGEMENT,
        privileges.BULK_CASE_MANAGEMENT,
        privileges.ALLOW_EXCESS_USERS,
        privileges.LOCATIONS,
        privileges.USER_CASE,
        privileges.ZAPIER_INTEGRATION,
        privileges.LOGIN_AS,
        privileges.PRACTICE_MOBILE_WORKERS,
    ]

    pro_plan_features = standard_plan_features + [
        privileges.CLOUDCARE,
        privileges.CUSTOM_REPORTS,
        privileges.INBOUND_SMS,
        privileges.HIPAA_COMPLIANCE_ASSURANCE,
        privileges.DEIDENTIFIED_DATA,
        privileges.REPORT_BUILDER,
        privileges.DATA_CLEANUP,
        privileges.TEMPLATED_INTENTS,
        privileges.RESTRICT_ACCESS_BY_LOCATION,
        privileges.REPORT_BUILDER_5,
    ]

    advanced_plan_features = pro_plan_features + [
        privileges.CUSTOM_BRANDING,
        privileges.ACTIVE_DATA_MANAGEMENT,
        privileges.COMMCARE_LOGO_UPLOADER,
        privileges.CUSTOM_INTENTS,
        privileges.ADVANCED_DOMAIN_SECURITY,
        privileges.BUILD_PROFILES,
    ]

    enterprise_plan_features = advanced_plan_features + []

    OLD_PRIVILEGES = [
        BULK_CASE_AND_USER_MANAGEMENT,
        CROSS_PROJECT_REPORTS,
    ]

    BOOTSTRAP_GRANTS = {
        'community_plan_v0': community_plan_v0_features,
        'community_plan_v1': community_plan_v1_features,
        'standard_plan_v0': standard_plan_features,
        'pro_plan_v0': pro_plan_features,
        'advanced_plan_v0': advanced_plan_features,
        'enterprise_plan_v0': enterprise_plan_features,
    }

