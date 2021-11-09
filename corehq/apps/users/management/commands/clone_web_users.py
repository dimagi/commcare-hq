import csv
import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from toggle.shortcuts import set_toggle

import settings
from corehq.apps.export.dbaccessors import _get_export_instance
from corehq.apps.export.models import ExportInstance
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.users.models import CouchUser, DomainMembership, WebUser
from corehq.const import USER_CHANGE_VIA_CLONE
from corehq.toggles import toggles_enabled_for_user

logger = logging.getLogger(__name__)

OLD_USERNAME = 'old_username'
NEW_USERNAME = 'new_username'


class Command(BaseCommand):
    help = """
    Creates new web users with the same data as existing web users
    - Input is a CSV file with old_username and new_username columns
    - The new user is created, data is copied/transferred over, and the old user is deactivated which will log
    users out on their next request
    - Sends an email to the new user's preferred email and old user's preferred email informing them of the change
    If a user wants to reactivate their old account, they can request this via support who has the ability to make
    this change in hq admin  under User Administration -> Lookup user by email -> Disable/Enable User Account
    """

    def add_arguments(self, parser):
        parser.add_argument('file', help='')
        parser.add_argument('--verbose', action="store_true")

    def handle(self, file, **options):
        logger.setLevel(logging.INFO if options["verbose"] else logging.WARNING)
        for old_username, new_username in iterate_usernames_to_update(file):
            logger.info(f'Cloning old user {old_username} to new user {new_username}')
            try:
                old_user, new_user = clone_user(old_username, new_username)
            except CouchUser.Inconsistent as e:
                logger.error(f'{e}\nSkipping the pair ({old_username}, {new_username})')
                continue

            deactivate_django_user(old_user.get_django_user())
            send_deprecation_email(old_user, new_user)


def iterate_usernames_to_update(file):
    with open(file) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            yield row[OLD_USERNAME], row[NEW_USERNAME]


def clone_user(old_username, new_username):
    new_username = new_username.lower()
    old_user = WebUser.get_by_username(old_username)
    new_user = create_new_user_from_old_user(old_user, new_username)
    new_user.save()

    # Copy methods do not impact the existing user
    copy_domain_memberships(old_user, new_user)
    # Transfer methods do impact the existing user
    transfer_exports(old_user, new_user)
    transfer_scheduled_reports(old_user, new_user.get_id)
    transfer_saved_reports(old_user, new_user)
    transfer_feature_flags(old_user, new_user)

    return old_user, new_user


def create_new_user_from_old_user(old_user, new_username):
    new_user = WebUser.create(
        None,
        new_username,
        User.objects.make_random_password(),
        None,
        USER_CHANGE_VIA_CLONE,
        email=new_username,
        by_domain_required_for_log=False,
    )
    new_user = copy_user_fields(old_user, new_user)
    logger.info(f'Created new user {new_user.username}.')
    return new_user


def deactivate_django_user(django_user):
    django_user.is_active = False
    django_user.save()
    logger.info(f'Deactivated user {django_user.username}.')


def copy_domain_memberships(from_user, to_user):
    for domain_membership in from_user.domain_memberships:
        # intentionally leave out last_accessed
        copied_membership = DomainMembership(
            domain=domain_membership.domain,
            timezone=domain_membership.timezone,
            override_global_tz=domain_membership.override_global_tz,
            role_id=domain_membership.role_id,
            location_id=domain_membership.location_id,
            assigned_location_ids=domain_membership.assigned_location_ids,
            program_id=domain_membership.program_id,
            is_admin=domain_membership.is_admin,
        )
        to_user.domain_memberships.append(copied_membership)
        to_user.domains.append(copied_membership.domain)
        logger.info(f'Copied {domain_membership.domain} domain membership.')

    to_user.save()


def transfer_exports(from_user, to_user):
    for domain in from_user.domains:
        key = [domain]
        for export in _get_export_instance(ExportInstance, key):
            if export.owner_id == from_user.get_id:
                export.owner_id = to_user.get_id
                export.save()
                logger.info(f'Transferred ownership of export {export._id}.')


def transfer_scheduled_reports(from_user, to_user_id):
    for domain in from_user.domains:
        for scheduled_report in ReportNotification.by_domain_and_owner(domain, from_user._id, stale=False):
            scheduled_report.owner_id = to_user_id
            scheduled_report.save()
            logger.info(f'Transferred ownership of scheduled report {scheduled_report._id}.')


def transfer_saved_reports(from_user, to_user):
    for domain in from_user.domains:
        for saved_report in ReportConfig.by_domain_and_owner(domain, from_user.get_id, stale=False):
            saved_report.owner_id = to_user.get_id
            saved_report.save()
            logger.info(f'Transferred ownership of saved report {saved_report._id}.')


def transfer_feature_flags(from_user, to_user):
    enabled_toggles = toggles_enabled_for_user(from_user.username)
    for toggle in enabled_toggles:
        logger.info(f'Updating toggle {toggle} from {from_user.username} to {to_user.username}')
        set_toggle(toggle, from_user.username, False)
        set_toggle(toggle, to_user.username, True)
        logger.info(f'Transferred access to {toggle}.')

    toggles_enabled_for_user.clear(from_user.username)
    toggles_enabled_for_user.clear(to_user.username)


def copy_user_fields(from_user, to_user):
    # DjangoUserMixin fields
    # username, email and password have already been set
    # do not copy last_login and date_joined
    to_user.first_name = from_user.first_name
    to_user.last_name = from_user.last_name
    to_user.is_staff = from_user.is_staff
    to_user.is_active = from_user.is_active
    to_user.is_superuser = from_user.is_superuser

    # CouchUser fields
    # ignoring device_ids, last_device, created_on, last_modified
    to_user.devices = from_user.devices
    to_user.phone_numbers = from_user.phone_numbers
    to_user.status = from_user.status
    to_user.language = from_user.language
    to_user.subscribed_to_commcare_users = from_user.subscribed_to_commcare_users
    to_user.announcements_seen = from_user.announcements_seen
    to_user.user_data = from_user.user_data
    to_user.update_metadata(from_user.metadata)
    # I know it isn't recommended to set location_id directly, but this seems like a good exception
    to_user.location_id = from_user.location_id
    to_user.assigned_location_ids = from_user.assigned_location_ids
    to_user.has_built_app = from_user.has_built_app
    to_user.analytics_enabled = from_user.analytics_enabled

    # Web User fields
    to_user.program_id = from_user.program_id
    to_user.fcm_device_token = from_user.fcm_device_token
    to_user.atypical_user = from_user.atypical_user

    # EulaMixin field
    to_user.eulas = from_user.eulas

    return to_user


def send_deprecation_email(old_user, new_user):
    context = {
        'greeting': _("Dear {name},").format(name=new_user.first_name) if new_user.first_name else _("Hello,"),
        'old_username': old_user.username,
        'new_username': new_user.username,
    }

    email_html = render_to_string('users/email/deprecated_user.html', context)
    email_plaintext = render_to_string('users/email/deprecated_user.txt', context)

    logger.info(f'Sending email with deprecated notice to old email {old_user.get_email()} and '
                f'new email {new_user.get_email()}.')
    send_html_email_async.delay(
        _("Deprecated User"),
        old_user.get_email(),
        email_html,
        text_content=email_plaintext,
        email_from=settings.DEFAULT_FROM_EMAIL,
        file_attachments=[],
        cc=[new_user.get_email()]
    )
