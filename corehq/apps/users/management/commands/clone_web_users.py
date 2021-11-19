import csv
import logging
import re

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
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
from corehq.toggles import all_toggles_by_name, toggles_enabled_for_user
from corehq.util.bounced_email_manager import EMAIL_REGEX_VALIDATION

logger = logging.getLogger(__name__)

OLD_USERNAME = 'old_username'
NEW_USERNAME = 'new_username'

NOTIFY = 'notify'
RUN_MIGRATION = 'run'
COMMAND_CHOICES = [NOTIFY, RUN_MIGRATION]


class OldUserNotFound(Exception):
    pass


class NewUserAlreadyExists(Exception):
    pass


class Command(BaseCommand):
    help = """
    `notify` command - sends an email to specified users explaining a planned migration will take place in 7 days
    `run` command - creates new web users based on existing users, copying/transferring data like reports, domain
    memberships, and feature flags. Passwords are reset, and 2FA and API keys are not copied over.
    cchq --control <env> django-manage clone_web_users <command> <file.csv> --verbose --dry-run
    """

    def add_arguments(self, parser):
        parser.add_argument('command', choices=COMMAND_CHOICES)
        parser.add_argument('file', help='')
        parser.add_argument('--verbose', action="store_true")
        parser.add_argument('--dry-run', action="store_true")

    def handle(self, command, file, **options):
        logger.setLevel(logging.INFO if options["verbose"] else logging.WARNING)
        dry_run = options['dry_run']

        if command == NOTIFY:
            command_to_run = notify_users_command
        elif command == RUN_MIGRATION:
            command_to_run = run_migration_command
        else:
            raise CommandError(f"The '{command}' command is not supported.")

        already_existing_users = []
        non_existent_old_users = []
        invalid_emails = []
        for old_username, new_username in iterate_usernames_to_update(file):
            if not re.search(EMAIL_REGEX_VALIDATION, new_username):
                invalid_emails.append((old_username, new_username))
                continue

            try:
                command_to_run(old_username, new_username, dry_run)
            except OldUserNotFound:
                non_existent_old_users.append((old_username, new_username))
                continue
            except (CouchUser.Inconsistent, NewUserAlreadyExists):
                already_existing_users.append((old_username, new_username))
                continue
        log_skipped_pairs(already_existing_users, non_existent_old_users, invalid_emails)


def run_migration_command(old_username, new_username, dry_run):
    """
    This is responsible for running the actual cloning process
    This signature should be the same as other commands in this file
    """
    old_user, new_user = clone_user(old_username, new_username, dry_run=dry_run)

    logger.info(f'Successfully cloned old user {old_username} to new user {new_username}')
    if not dry_run:
        deactivate_django_user(old_user.get_django_user())
        send_deprecation_email(old_user, new_user)


def notify_users_command(old_username, new_username, dry_run):
    """
    This is responsible for notifying users of a planned migration
    This signature should be the same as other commands in this file
    """
    old_user = validate_usernames(old_username, new_username)

    scheduled_date = date.today() + timedelta(days=7)
    dry_run_tag = "[DRY_RUN]" if dry_run else ""
    logger.info(f'{dry_run_tag}Sending email notifying {old_user.get_email()} a migration is scheduled for '
                f'{scheduled_date}.')
    if not dry_run:
        send_scheduled_migration_email(old_user, new_username, scheduled_date)


def iterate_usernames_to_update(file):
    with open(file) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            yield row[OLD_USERNAME], row[NEW_USERNAME]


def validate_usernames(old_username, new_username):
    """
    Ensures the old_username has an existing user, and the new_username does not
    :return: the old user that was fetched from the DB if all went well
    """
    old_username = old_username.lower()
    old_user = WebUser.get_by_username(old_username)
    if not old_user:
        raise OldUserNotFound

    new_username = new_username.lower()
    if WebUser.get_by_username(new_username):
        raise NewUserAlreadyExists

    return old_user


def clone_user(old_username, new_username, dry_run=False):
    old_user = validate_usernames(old_username, new_username)

    new_user = None
    if not dry_run:
        new_user = create_new_user_from_old_user(old_user, new_username)
        new_user.save()

    # Copy methods do not impact the existing user
    copy_domain_memberships(old_user, new_user, dry_run=dry_run)
    # Transfer methods do impact the existing user
    transfer_exports(old_user, new_user, dry_run=dry_run)
    transfer_scheduled_reports(old_user, new_user, dry_run=dry_run)
    transfer_saved_reports(old_user, new_user, dry_run=dry_run)
    transfer_feature_flags(old_user, new_user, dry_run=dry_run)

    return old_user, new_user


def create_new_user_from_old_user(old_user, new_username):
    new_user = WebUser.create(
        None,
        new_username,
        User.objects.make_random_password(),
        None,
        USER_CHANGE_VIA_CLONE,
        by_domain_required_for_log=False,
    )
    new_user = copy_user_fields(old_user, new_user)
    logger.info(f'Created new user {new_user.username}.')
    return new_user


def deactivate_django_user(django_user):
    django_user.is_active = False
    django_user.save()
    logger.info(f'Deactivated user {django_user.username}.')


def copy_domain_memberships(from_user, to_user, dry_run=False):
    dry_run_tag = "[DRY_RUN]" if dry_run else ""
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
        if not dry_run:
            to_user.domain_memberships.append(copied_membership)
            to_user.domains.append(copied_membership.domain)
        logger.info(f'{dry_run_tag}Copied {domain_membership.domain} domain membership.')
    if not dry_run:
        to_user.save()


def transfer_exports(from_user, to_user, dry_run=False):
    dry_run_tag = "[DRY_RUN]" if dry_run else ""
    for domain in from_user.domains:
        key = [domain]
        for export in _get_export_instance(ExportInstance, key):
            if export.owner_id == from_user.get_id:
                if not dry_run:
                    export.owner_id = to_user.get_id
                    export.save()
                logger.info(f'{dry_run_tag}Transferred ownership of export {export._id}.')


def transfer_scheduled_reports(from_user, to_user, dry_run=False):
    dry_run_tag = "[DRY_RUN]" if dry_run else ""
    for domain in from_user.domains:
        for scheduled_report in ReportNotification.by_domain_and_owner(domain, from_user._id, stale=False):
            if not dry_run:
                scheduled_report.owner_id = to_user._id
                scheduled_report.save()
            logger.info(f'{dry_run_tag}Transferred ownership of scheduled report {scheduled_report._id}.')


def transfer_saved_reports(from_user, to_user, dry_run=False):
    dry_run_tag = "[DRY_RUN]" if dry_run else ""
    for domain in from_user.domains:
        for saved_report in ReportConfig.by_domain_and_owner(domain, from_user.get_id, stale=False):
            if not dry_run:
                saved_report.owner_id = to_user.get_id
                saved_report.save()
            logger.info(f'{dry_run_tag}Transferred ownership of saved report {saved_report._id}.')


def transfer_feature_flags(from_username, to_username, dry_run=False):
    dry_run_tag = "[DRY_RUN]" if dry_run else ""
    enabled_toggles = toggles_enabled_for_user(from_username)
    by_name = all_toggles_by_name()
    for toggle_name in enabled_toggles:
        if not dry_run:
            toggle_slug = by_name[toggle_name].slug
            set_toggle(toggle_slug, from_username, False)
            set_toggle(toggle_slug, to_username, True)
        logger.info(f'{dry_run_tag}Updated toggle name {toggle_name} from {from_username} to {to_username}')

    if not dry_run:
        toggles_enabled_for_user.clear(from_username)
        toggles_enabled_for_user.clear(to_username)


def copy_user_fields(from_user, to_user):
    # DjangoUserMixin fields
    # username, email and password have already been set
    # do not copy last_login and date_joined
    to_user.first_name = from_user.first_name
    to_user.last_name = from_user.last_name
    to_user.is_staff = from_user.is_staff
    to_user.is_active = from_user.is_active
    to_user.is_superuser = from_user.is_superuser
    to_user.email = from_user.email or from_user.username

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

    send_html_email_async.delay(
        _("Your CommCare User Was Migrated"),
        old_user.get_email(),
        email_html,
        text_content=email_plaintext,
        email_from=settings.DEFAULT_FROM_EMAIL,
        file_attachments=[],
        cc=[new_user.get_email()]
    )


def send_scheduled_migration_email(old_user, new_username, scheduled_date):
    context = {
        'greeting': _("Dear {name},").format(name=old_user.first_name) if old_user.first_name else _("Hello,"),
        'old_username': old_user.username,
        'new_username': new_username,
        'date': scheduled_date
    }

    email_html = render_to_string('users/email/notify_scheduled_user_migration.html', context)
    email_plaintext = render_to_string('users/email/notify_scheduled_user_migration.txt', context)

    send_html_email_async.delay(
        _("Scheduled Migration For Your CommCare User"),
        old_user.get_email(),
        email_html,
        text_content=email_plaintext,
        email_from=settings.DEFAULT_FROM_EMAIL,
        file_attachments=[],
    )


def log_skipped_pairs(already_existing_users, non_existent_old_users, invalid_emails):
    if already_existing_users:
        pairs = "\n".join([str(pair) for pair in already_existing_users])
        logger.warning(f'SKIPPED: New username already exists\n {pairs}')
    if non_existent_old_users:
        pairs = "\n".join([str(pair) for pair in non_existent_old_users])
        logger.warning(f'SKIPPED: Old user not found\n {pairs}')
    if invalid_emails:
        pairs = "\n".join([str(pair) for pair in invalid_emails])
        logger.warning(f'SKIPPED: New username is not a valid email\n {pairs}')
