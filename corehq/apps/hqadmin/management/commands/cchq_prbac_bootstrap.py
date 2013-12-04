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
from django_prbac.models import Grant, Role

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populate a fresh database with some sample roles and grants'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help='Do not actually modify the database, just verbosely log what happen'),
        make_option('--verbose', action='store_true',  default=False,
                    help='Enable debug output'),
    )

    def handle(self, dry_run=False, verbose=False, *args, **options):
        if verbose:
            logger.setLevel(logging.DEBUG)

        for role in self.BOOTSTRAP_PRIVILEGES + self.BOOTSTRAP_PLANS:
            self.ensure_role(role, dry_run=dry_run)

        for (plan_role_slug, privs) in self.BOOTSTRAP_GRANTS.items():
            for priv_role_slug in privs:
                self.ensure_grant(plan_role_slug, priv_role_slug, dry_run=dry_run)

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
        Role(slug='multimedia', name='Multimedia Support', description=''),
        Role(slug='app_builder', name='CommCare Application Builder', description=''),
        Role(slug='commcare_exchange', name='CommCare Exchange', description=''),
        Role(slug='api_access', name='API Access', description=''),
        Role(slug='lookup_tables', name='Lookup Tables', description=''),
        Role(slug='cloudcare', name='Web-based Applications (CloudCare)', description=''),
        Role(slug='custom_branding', name='Custom Branding', description=''),
        Role(slug='data_export', name='Data Export', description=''),
        Role(slug='standard_reports', name='Standard Reports', description=''),
        Role(slug='cross_project_reports', name='Cross-Project Reports', description=''),
        Role(slug='custom_reports', name='Custom Reports', description=''),
        Role(slug='active_data_management', name='Active Data Management', description=''),
        Role(slug='outbound_messaging', name='Outbound Messaging', description=''),
        Role(slug='rules_engine', name='Rules Engine', description=''),
        Role(slug='android_sms_gateway', name='Android-based SMS Gateway', description=''),
        Role(slug='sms_data_collection', name='SMS Data Collection', description=''),
        Role(slug='inbound_sms', name='Inbound SMS (where available)', description=''),
        Role(slug='user_groups', name='User Groups', description=''),
        Role(slug='role_based_access', name='Role-based Access', description=''),
        Role(slug='bulk_user_management', name='Bulk User Management', description=''),
        Role(slug='deidentified_data', name='De-identified Data', description=''),
        Role(slug='hipaa_compliance_assurance', name='HIPAA Compliance Assurance', description=''),
    ]

    BOOTSTRAP_PLANS = [
        Role(slug='community_plan_v0', name='Community Plan', description=''),
        Role(slug='standard_plan_v0', name='Standard Plan', description=''),
        Role(slug='pro_plan_v0', name='Pro Plan', description=''),
        Role(slug='advanced_plan_v0', name='Advanced Plan', description=''),
        Role(slug='enterprise_plan_v0', name='Enterprise Plan', description=''),
    ]

    community_plan_features = [
        'multimedia',
        'app_builder',
        'commcare_exchange',
        'data_export',
        'standard_reports',
        'user_groups',
    ]

    standard_plan_features = community_plan_features + [
        'api_access',
        'lookup_tables',
        'cross_project_reports',
        'outbound_messaging',
        'rules_engine',
        'android_sms_gateway',
        'role_based_access',
        'bulk_user_management',
    ]

    pro_plan_features = standard_plan_features + [
        'cloudcare',
        'custom_reports',
        'sms_data_collection',
        'inbound_sms',
        'hipaa_compliance_assurance',
        'deidentified_data',
    ]

    advanced_plan_features = pro_plan_features + [
        'custom_branding',
        'active_data_management',
    ]

    enterprise_plan_features = advanced_plan_features + []

    BOOTSTRAP_GRANTS = {
        'community_plan_v0': community_plan_features,
        'standard_plan_v0': standard_plan_features,
        'pro_plan_v0': pro_plan_features,
        'advanced_plan_v0': advanced_plan_features,
        'enterprise_plan_v0': enterprise_plan_features,
    }

