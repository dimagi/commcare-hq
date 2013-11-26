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

        for (plan_role_name, privs) in self.BOOTSTRAP_GRANTS.items():
            for priv_role_name in privs:
                self.ensure_grant(plan_role_name, priv_role_name, dry_run=dry_run)

    def ensure_role(self, role, dry_run=False):
        """
        Adds the role if it does not already exist, otherwise skips it.
        """

        existing_roles = Role.objects.filter(name=role.name)

        if existing_roles:
            logger.info('Role already exists: %s', role.name)
            return existing_roles[0]
        else:
            if dry_run:
                logger.info('[DRY RUN] Creating role: %s', role.name)
            else:
                logger.info('Creating role: %s', role.name)
                role.save()

    def ensure_grant(self, grantee_name, priv_name, dry_run=False):
        """
        Adds a parameterless grant between grantee and priv, looked up by name.
        """

        if dry_run:
            grants = Grant.objects.filter(from_role__name=grantee_name,
                                          to_role__name=priv_name)
            if not grants:
                logger.info('[DRY RUN] Granting privilege: %s => %s', grantee_name, priv_name)
        else:
            grantee = Role.objects.get(name=grantee_name)
            priv = Role.objects.get(name=priv_name)

            if grantee.has_privilege(priv):
                logger.info('Privilege already granted: %s => %s', grantee.name, priv.name)
            else:
                logger.info('Granting privilege: %s => %s', grantee.name, priv.name)
                Grant.objects.create(
                    from_role=grantee,
                    to_role=priv,
                )

    BOOTSTRAP_PRIVILEGES = [
        Role(name='multimedia', friendly_name='Multimedia Support', description=''),
        Role(name='app_builder', friendly_name='CommCare Application Builder', description=''),
        Role(name='commcare_exchange', friendly_name='CommCare Exchange', description=''),
        Role(name='api_access', friendly_name='API Access', description=''),
        Role(name='lookup_tables', friendly_name='Lookup Tables', description=''),
        Role(name='cloudcare', friendly_name='Web-based Applications (CloudCare)', description=''),
        Role(name='custom_branding', friendly_name='Custom Branding', description=''),
        Role(name='data_export', friendly_name='Data Export', description=''),
        Role(name='standard_reports', friendly_name='Standard Reports', description=''),
        Role(name='cross_project_reports', friendly_name='Cross-Project Reports', description=''),
        Role(name='custom_reports', friendly_name='Custom Reports', description=''),
        Role(name='active_data_management', friendly_name='Active Data Management', description=''),
        Role(name='outbound_messaging', friendly_name='Outbound Messaging', description=''),
        Role(name='rules_engine', friendly_name='Rules Engine', description=''),
        Role(name='android_sms_gateway', friendly_name='Android-based SMS Gateway', description=''),
        Role(name='sms_data_collection', friendly_name='SMS Data Collection', description=''),
        Role(name='inbound_sms', friendly_name='Inbound SMS (where available)', description=''),
        Role(name='user_groups', friendly_name='User Groups', description=''),
        Role(name='role_based_access', friendly_name='Role-based Access', description=''),
        Role(name='bulk_user_management', friendly_name='Bulk User Management', description=''),
        Role(name='hipaa_compliance_assurance', friendly_name='HIPAA Compliance Assurance', description=''),
        Role(name='deidentified_data', friendly_name='De-identified Data', description=''),
    ]

    BOOTSTRAP_PLANS = [
        Role(name='community_plan_v0', friendly_name='Community Plan', description=''),
        Role(name='standard_plan_v0', friendly_name='Standard Plan', description=''),
        Role(name='pro_plan_v0', friendly_name='Pro Plan', description=''),
        Role(name='advanced_plan_v0', friendly_name='Advanced Plan', description=''),
        Role(name='enterprise_plan_v0', friendly_name='Enterprise Plan', description=''),
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

