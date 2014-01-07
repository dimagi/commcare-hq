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

class Command(BaseCommand):
    help = 'Populate a fresh database with some sample roles and grants'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help='Do not actually modify the database, just verbosely log what happen'),
        make_option('--verbose', action='store_true',  default=False,
                    help='Enable debug output'),
        make_option('--fresh-start', action='store_true',  default=False,
                    help='We changed the core v0 plans, wipe all existing plans and start over. USE CAUTION.'),
    )

    def handle(self, dry_run=False, verbose=False, fresh_start=False, *args, **options):
        if verbose:
            logger.setLevel(logging.DEBUG)

        if fresh_start:
            confirm_fresh_start = input("Are you sure you want to delete all Roles and start over? You can't do this"
                                        " if accounting is already set up. Type 'yes' to continue.")
            if confirm_fresh_start == 'yes':
                self.flush_roles()

        for role in self.BOOTSTRAP_PRIVILEGES + self.BOOTSTRAP_PLANS:
            self.ensure_role(role, dry_run=dry_run)

        for (plan_role_slug, privs) in self.BOOTSTRAP_GRANTS.items():
            for priv_role_slug in privs:
                self.ensure_grant(plan_role_slug, priv_role_slug, dry_run=dry_run)

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

            if grantee.has_privilege(priv):
                logger.info('Privilege already granted: %s => %s', grantee.slug, priv.slug)
            else:
                logger.info('Granting privilege: %s => %s', grantee.slug, priv.slug)
                Grant.objects.create(
                    from_role=grantee,
                    to_role=priv,
                )

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
        Role(slug=privileges.BULK_CASE_AND_USER_MANAGEMENT, name='Bulk Case and User Management', description=''),
        Role(slug=privileges.DEIDENTIFIED_DATA, name='De-identified Data', description=''),
        Role(slug=privileges.HIPAA_COMPLIANCE_ASSURANCE, name='HIPAA Compliance Assurance', description=''),
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
        privileges.BULK_CASE_AND_USER_MANAGEMENT,
    ]

    pro_plan_features = standard_plan_features + [
        privileges.CLOUDCARE,
        privileges.CUSTOM_REPORTS,
        privileges.INBOUND_SMS,
        privileges.HIPAA_COMPLIANCE_ASSURANCE,
        privileges.DEIDENTIFIED_DATA,
    ]

    advanced_plan_features = pro_plan_features + [
        privileges.CUSTOM_BRANDING,
        privileges.ACTIVE_DATA_MANAGEMENT,
    ]

    enterprise_plan_features = advanced_plan_features + []

    BOOTSTRAP_GRANTS = {
        'community_plan_v0': community_plan_features,
        'standard_plan_v0': standard_plan_features,
        'pro_plan_v0': pro_plan_features,
        'advanced_plan_v0': advanced_plan_features,
        'enterprise_plan_v0': enterprise_plan_features,
    }

