# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Standard library imports
import sys
import logging
from optparse import make_option

# Django imports
from django.core.management.base import BaseCommand
from django.core.mail import mail_admins

# External imports
from corehq import privileges
from django_prbac.models import Grant, Role

logger = logging.getLogger(__name__)


BULK_CASE_AND_USER_MANAGEMENT = 'bulk_case_and_user_management'

class Command(BaseCommand):
    help = 'Populate a fresh database with some sample roles and grants'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help='Do not actually modify the database, just verbosely log what happen'),
        make_option('--verbose', action='store_true',  default=False,
                    help='Enable debug output'),
        make_option('--fresh-start', action='store_true',  default=False,
                    help='We changed the core v0 plans, wipe all existing plans and start over. USE CAUTION.'),
        make_option('--testing', action='store_true',  default=False,
                    help='Run this command for tests.'),
    )

    def handle(self, dry_run=False, verbose=False, fresh_start=False, testing=False, *args, **options):

        self.verbose = verbose

        if fresh_start:
            confirm_fresh_start = raw_input("Are you sure you want to delete all Roles and start over? You can't do this"
                                            " if accounting is already set up. Type 'yes' to continue.")
            if confirm_fresh_start == 'yes':
                self.flush_roles()

        for role in self.BOOTSTRAP_PRIVILEGES + self.BOOTSTRAP_PLANS:
            self.ensure_role(role, dry_run=dry_run)

        for (plan_role_slug, privs) in self.BOOTSTRAP_GRANTS.items():
            for priv_role_slug in privs:
                self.ensure_grant(plan_role_slug, priv_role_slug, dry_run=dry_run)

        for old_priv in self.OLD_PRIVILEGES:
            for plan_role_slug in self.BOOTSTRAP_GRANTS.keys():
                self.remove_grant(plan_role_slug, old_priv)

    def flush_roles(self):
        logger.info('Flushing ALL Roles...')
        Role.objects.all().delete()

    def ensure_role(self, role, dry_run=False):
        """
        Adds the role if it does not already exist, otherwise skips it.
        """

        existing_roles = Role.objects.filter(slug=role.slug)

        if existing_roles:
            logger.info('Role already exists: %s', role.name)
            return existing_roles[0]
        else:
            if dry_run:
                logger.info('[DRY RUN] Creating role: %s', role.name)
            else:
                if self.verbose:
                    logger.info('Creating role: %s', role.name)
                role.save()

    def ensure_grant(self, grantee_slug, priv_slug, dry_run=False):
        """
        Adds a parameterless grant between grantee and priv, looked up by slug.
        """

        if dry_run:
            grants = Grant.objects.filter(from_role__slug=grantee_slug,
                                          to_role__slug=priv_slug)
            if not grants:
                logger.info('[DRY RUN] Granting privilege: %s => %s', grantee_slug, priv_slug)
        else:
            grantee = Role.objects.get(slug=grantee_slug)
            priv = Role.objects.get(slug=priv_slug)

            Role.get_cache().clear()
            if grantee.has_privilege(priv):
                if self.verbose:
                    logger.info('Privilege already granted: %s => %s', grantee.slug, priv.slug)
            else:
                if self.verbose:
                    logger.info('Granting privilege: %s => %s', grantee.slug, priv.slug)
                Grant.objects.create(
                    from_role=grantee,
                    to_role=priv,
                )

    def remove_grant(self, grantee_slug, priv_slug, dry_run=False):
        grants = Grant.objects.filter(from_role__slug=grantee_slug,
                                      to_role__slug=priv_slug)
        if dry_run:
            if grants:
                logger.info("[DRY RUN] Removing privilege %s => %s", grantee_slug, priv_slug)
        else:
            if grants:
                grants.delete()
                logger.info("Removing privilege %s => %s", grantee_slug, priv_slug)

    BOOTSTRAP_PRIVILEGES = [
        Role(slug=privileges.API_ACCESS, name='API Access', description=''),
        Role(slug=privileges.LOOKUP_TABLES, name='Lookup Tables', description=''),
        Role(slug=privileges.CLOUDCARE, name='Web-based Applications (CloudCare)', description=''),
        Role(slug=privileges.CUSTOM_BRANDING, name='Custom Branding', description=''),
        Role(slug=privileges.ACTIVE_DATA_MANAGEMENT, name='Active Data Management', description=''),
        Role(slug=privileges.CROSS_PROJECT_REPORTS, name='Cross-Project Reports', description=''),
        Role(slug=privileges.CUSTOM_REPORTS, name='Custom Reports', description=''),
        Role(slug=privileges.ROLE_BASED_ACCESS, name='Role-based Access', description=''),
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
    ]

    BOOTSTRAP_PLANS = [
        Role(slug='community_plan_v0', name='Community Plan', description=''),
        Role(slug='standard_plan_v0', name='Standard Plan', description=''),
        Role(slug='pro_plan_v0', name='Pro Plan', description=''),
        Role(slug='advanced_plan_v0', name='Advanced Plan', description=''),
        Role(slug='enterprise_plan_v0', name='Enterprise Plan', description=''),
    ]

    community_plan_features = [
    ]

    standard_plan_features = community_plan_features + [
        privileges.API_ACCESS,
        privileges.LOOKUP_TABLES,
        privileges.CROSS_PROJECT_REPORTS,
        privileges.OUTBOUND_SMS,
        privileges.REMINDERS_FRAMEWORK,
        privileges.CUSTOM_SMS_GATEWAY,
        privileges.ROLE_BASED_ACCESS,
        privileges.BULK_USER_MANAGEMENT,
        privileges.BULK_CASE_MANAGEMENT,
        privileges.ALLOW_EXCESS_USERS,
        privileges.LOCATIONS,
    ]

    pro_plan_features = standard_plan_features + [
        privileges.CLOUDCARE,
        privileges.CUSTOM_REPORTS,
        privileges.INBOUND_SMS,
        privileges.HIPAA_COMPLIANCE_ASSURANCE,
        privileges.DEIDENTIFIED_DATA,
        privileges.REPORT_BUILDER,
    ]

    advanced_plan_features = pro_plan_features + [
        privileges.CUSTOM_BRANDING,
        privileges.ACTIVE_DATA_MANAGEMENT,
        privileges.COMMCARE_LOGO_UPLOADER,
    ]

    enterprise_plan_features = advanced_plan_features + []

    OLD_PRIVILEGES = [
        BULK_CASE_AND_USER_MANAGEMENT,
    ]

    BOOTSTRAP_GRANTS = {
        'community_plan_v0': community_plan_features,
        'standard_plan_v0': standard_plan_features,
        'pro_plan_v0': pro_plan_features,
        'advanced_plan_v0': advanced_plan_features,
        'enterprise_plan_v0': enterprise_plan_features,
    }

