import json
import logging
import re

from django.contrib.admin.models import LogEntry
from django.contrib.admin.options import get_content_type_for_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.encoding import force_text

from openpyxl import Workbook

from dimagi.utils.couch.bulk import get_docs

from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsProfile,
)
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.programs.models import Program
from corehq.apps.users.audit.change_messages import (
    ASSIGNED_LOCATIONS_FIELD,
    DOMAIN_FIELD,
    DOMAIN_INVITATION_FIELD,
    GROUPS_FIELD,
    LOCATION_FIELD,
    PASSWORD_FIELD,
    PHONE_NUMBERS_FIELD,
    PROFILE_FIELD,
    PROGRAM_FIELD,
    ROLE_FIELD,
    STATUS_FIELD,
    TWO_FACTOR_FIELD,
    UserChangeMessage,
)
from corehq.apps.users.models import UserHistory
from corehq.apps.users.models_role import UserRole

# Regex for various messages
# f"Program: {program.name}[{program.get_id}]"
PROGRAM_REGEX = re.compile(r"Program: (.+)\[(.+)]")

# f"Role: {user_role.name}[{user_role.get_qualified_id()}]"
ROLE_REGEX = re.compile(r"Role: (.+)\[(.+)]")

# f"Removed from domain '{domain}'"
DOMAIN_REMOVE_REGEX = re.compile(r"Removed from domain '(\S+)'")

# f"Disabled for {days} days"
DISABLED_FOR_DAYS_REGEX = re.compile(r"Disabled for (\d+) days")

# f'User {action}. Reason: "{reason}"'
STATUS_UPDATE_REGEX_PART_1 = re.compile(r'User (.+)')
STATUS_UPDATE_REGEX_PART_2 = re.compile(r'Reason: "(.+)"')

# f"Added phone number {phone_number}"
ADDED_PHONE_NUMBER_REGEX = re.compile(r'Added phone number (.+)')

# f"Removed phone number {phone_number}"
REMOVED_PHONE_NUMBER_REGEX = re.compile(r'Removed phone number (.+)')

# f"CommCare Profile: {profile_name}"
PROFILE_REGEX = re.compile(r'CommCare Profile: (.+)')

# f"Primary location: {location_name}"
COMMCARE_USER_PRIMARY_LOCATION_REGEX = re.compile(r'Primary location: (.+)')

# f"Primary location: {location.name}[{location.location_id}]"
WEB_USER_PRIMARY_LOCATION_REGEX = re.compile(r'Primary location: (.+)\[(.+)]')

# f"Assigned locations: {location_names}" where location names is a python list object of names
COMMCARE_USER_ASSIGNED_LOCATIONS_REGEX = re.compile(r'Assigned locations: \[(.+)]')

# f"Assigned locations: {locations_info}"
# where locations_info is a ", " joined location_name[location_id] for locations
WEB_USER_ASSIGNED_LOCATIONS_REGEX = re.compile(r'Assigned locations: (.*)')

# f"Groups: {groups_info}" same as assigned locations
GROUPS_REGEX = re.compile(r'Groups: (.*)')

# f"Added as web user to domain '{domain}'"
ADDED_AS_WEB_USER_REGEX = re.compile(r"Added as web user to domain '(\S+)'")

# f"Invited to domain '{domain}'"
INVITED_TO_DOMAIN_REGEX = re.compile(r"Invited to domain '(.+)'")

# f"Invitation revoked for domain '{domain}'"
INVITATION_REVOKED_FOR_DOMAIN_REGEX = re.compile(r"Invitation revoked for domain '(.+)'")

# f'Two factor disabled. Verified by: {verified_by}, verification mode: "{verification_mode}"'
DISABLED_WITH_VERIFICATION_REGEX = re.compile(
    r'Two factor disabled. Verified by: (.+), verification mode: "(.+)"')

# location-name[location_id]
# group-name[group_id]
NAME_WITH_ID_REGEX = re.compile(r'(.+)\[(.+)]')


class Command(BaseCommand):
    help = "Migrate User History records to new structure"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            dest='save',
            default=False,
            help="actually save records else just log",
        )
        parser.add_argument(
            '--skip-assertions',
            action='store_true',
            dest='skip_assertions',
            default=False,
            help="to be used to skip assertions in change message creation, useful for manual updates",
        )
        parser.add_argument(
            '--only-pending',
            action='store_true',
            dest='only_pending',
            default=False,
            help="to iterate only logs that are pending to be migrated"
        )

    def handle(self, **options):
        save = options['save']
        skip_assertions = options['skip_assertions']
        only_pending = options['only_pending']
        if save and skip_assertions:
            raise CommandError("It is not recommended to have save with assertions skipped")
        wb = Workbook()
        ws = wb.active
        ws.append([
            'ID', 'Message', 'Change Messages', 'Details Changes', 'Changes', 'Changes equal?',
            'Details Changed Via', 'Changed Via']
        )

        records = UserHistory.objects
        if only_pending:
            # filter on the new column that is expected to be blank for not migrated records only
            records = records.filter(changed_via='')

        for user_history in records.order_by('pk').iterator():
            try:
                migrate(user_history, save=save, skip_assertions=skip_assertions)
            except Exception as e:
                logging.error(f"{user_history.pk}: {e}")
            else:
                ws.append(
                    [user_history.pk,
                     user_history.message,
                     json.dumps(user_history.change_messages),
                     json.dumps(user_history.details.get('changes')),
                     json.dumps(user_history.changes),
                     user_history.details.get('changes') == user_history.changes,  # should not be False
                     user_history.details.get('changed_via'),
                     user_history.changed_via
                     ]
                )
        wb.save("migrate_user_history_to_new_structure.xlsx")


def migrate(user_history, save=False, skip_assertions=False):
    """
    1. Copy over changed_via and changes to new columns
    2. convert messages into new change messages format
    3. migrate over to log entry to back up old columns before they are deleted
    """
    # a double check to avoid re-runs on records
    if user_history.message and user_history.change_messages:
        raise Exception("got a migrated record")

    # simply copy over changed_via to new column
    # changed_via should always be present
    user_history.changed_via = user_history.details.get('changed_via')
    assert user_history.changed_via, f"Missing changed_via for {user_history.pk}"

    # simply copy over user changes to new changes column
    # changes might or might not be present
    if user_history.details.get('changes'):
        user_history.changes = user_history.details['changes']

    if user_history.message:
        change_messages = create_change_messages(user_history, skip_assertions)
        assert change_messages, f"Change message not created for message {user_history.message}"
        user_history.change_messages = change_messages

    if save:
        user_history.save()

        migrated = migrate_user_history_to_log_entry(user_history)
        assert migrated, f"Could not create log entry for User History record {user_history.pk}"


def create_change_messages(user_history, skip_assertions):
    """
    A message is a ". " join of different messages.
    So it should be possible to split by ". " and identify individual messages.
    There are two messages that have ". " in it
    - one for verified two factor disable
        'Two factor disabled. Verified by: {verified_by}, verification mode: "{verification_mode}"'
    - one for status update
        'User {action}. Reason: "{reason}"'
    They can be identified and handled accordingly
    """

    # split by . but not by something that starts with st like "St. " which was found in location names
    # "St. " or "st. " was the only case found during the dry run
    # if any message gets broken down poorly because of . in their messages,
    # conversion won't work for such messages and they will be flagged
    # all individual messages should have checks to ensure they are complete
    messages = re.split(r"(?<!St)\. ", user_history.message, flags=re.IGNORECASE)
    messages_not_converted = []
    change_messages = {}

    # flag for two factor disable message
    disable_for_days = None

    # flag for status update messages
    status_update_active = None
    status_update_reason = None

    for message in messages:
        if "Program: None" == message:
            _check_for_double_entry(PROGRAM_FIELD, message, change_messages)

            change_messages.update(
                UserChangeMessage.program_change(None)
            )

        elif PROGRAM_REGEX.match(message):
            _check_for_double_entry(PROGRAM_FIELD, message, change_messages)

            program_name, program_id = PROGRAM_REGEX.match(message).groups()

            assert program_name, f"Program name missing in message {message}"
            assert program_id, f"Program id missing in message {message}"
            program = Program.get(program_id)
            assert program, f"Could not find program with id {program_id}"

            if not skip_assertions:
                # assert for complete message
                # compare name
                assert program.name == program_name, "Looks like program name changed. Found program id " \
                                                     f"{program_id} with name {program.name} but name in log " \
                                                     f"is {program_name}"

            change_messages.update(UserChangeMessage.program_change(program))

            # fallback in case program has been deleted
            # change_messages[PROGRAM_FIELD] = {
            #     "set_program": {"id": program_id, "name": program_name}
            # }

        elif "Role: None" == message:
            _check_for_double_entry(ROLE_FIELD, message, change_messages)

            change_messages.update(UserChangeMessage.role_change(None))

        elif ROLE_REGEX.match(message):
            _check_for_double_entry(ROLE_FIELD, message, change_messages)

            role_name, role_qualified_id = ROLE_REGEX.match(message).groups()
            assert role_name, f"Role name missing in message {message}"
            assert role_qualified_id, f"Role qualified id missing in message {message}"

            if role_qualified_id == "admin" and role_name == "Admin":
                change_messages[ROLE_FIELD] = {
                    "set_role": {"id": role_qualified_id, "name": role_name}
                }
            else:
                role_id = role_qualified_id[len('user-role:'):]
                role = UserRole.objects.by_couch_id(role_id)
                if not skip_assertions:
                    # assert for complete message
                    # compare name
                    assert role.name == role_name, "Looks like role name changed. Found role id " \
                                                   f"{role_id} with name {role.name} but name in log " \
                                                   f"is {role_name}"

                change_messages.update(UserChangeMessage.role_change(role))
                # fallback in case role has been deleted
                # change_messages[ROLE_FIELD] = {
                #     "set_role": {"id": role_qualified_id, "name": role_name}
                # }

        elif DOMAIN_REMOVE_REGEX.match(message):
            _check_for_double_entry(DOMAIN_FIELD, message, change_messages)

            domain_name = DOMAIN_REMOVE_REGEX.match(message).groups()[0]
            assert domain_name, f"Could not find domain name in removal message {message}"

            if not skip_assertions:
                # assert for complete message by fetching the domain by name
                assert Domain.get_by_name(domain_name), f"Could not find domain with name {domain_name}"

            change_messages.update(UserChangeMessage.domain_removal(domain_name))

        elif "Registered devices reset" == message:
            # this message is not needed anymore
            # https://github.com/dimagi/commcare-hq/pull/30253#discussion_r695604101
            pass

        elif DISABLED_FOR_DAYS_REGEX.match(message):
            # take later with disable with verification message
            days = DISABLED_FOR_DAYS_REGEX.match(message).groups()[0]
            disable_for_days = days

        # we had R instead of r for this message at one place, so check both
        elif "Password reset" == message or "Password Reset" == message:
            _check_for_double_entry(PASSWORD_FIELD, message, change_messages)

            change_messages.update(UserChangeMessage.password_reset())

        elif STATUS_UPDATE_REGEX_PART_1.match(message):
            action = STATUS_UPDATE_REGEX_PART_1.match(message).groups()[0]

            active = None
            if action == 're-enabled':
                active = True
            elif action == 'disabled':
                active = False
            assert active is not None, f"Could not find value of is_active from {message}"

            # consolidate later with status update part 2
            status_update_active = active

        elif STATUS_UPDATE_REGEX_PART_2.match(message):
            reason = STATUS_UPDATE_REGEX_PART_2.match(message).groups()[0]
            assert reason, f"Could not find value of reason from {message}"

            # consolidate later with status update part 1
            status_update_reason = reason

        elif ADDED_PHONE_NUMBER_REGEX.match(message):
            # there can be multiple added phone number messages
            # phone numbers can be added and removed in the same message
            phone_number = ADDED_PHONE_NUMBER_REGEX.match(message).groups()[0]
            assert phone_number, f"Could not get phone number from messages {message}"

            # if already a message for phone numbers
            if PHONE_NUMBERS_FIELD in change_messages:
                # if already a message for addition then append, else update
                if "add_phone_numbers" in change_messages[PHONE_NUMBERS_FIELD]:
                    change_messages[PHONE_NUMBERS_FIELD]["add_phone_numbers"]["phone_numbers"].append(phone_number)
                else:
                    change_messages[PHONE_NUMBERS_FIELD].update(
                        UserChangeMessage.phone_numbers_added([phone_number])[PHONE_NUMBERS_FIELD]
                    )
            else:
                change_messages.update(UserChangeMessage.phone_numbers_added([phone_number]))

        elif REMOVED_PHONE_NUMBER_REGEX.match(message):
            # there can be multiple removed phone number messages
            # phone numbers can be added and removed in the same message
            phone_number = REMOVED_PHONE_NUMBER_REGEX.match(message).groups()[0]
            assert phone_number, f"Could not get phone number from messages {message}"

            # if already a message for phone numbers
            if PHONE_NUMBERS_FIELD in change_messages:
                if "remove_phone_numbers" in change_messages[PHONE_NUMBERS_FIELD]:
                    change_messages[PHONE_NUMBERS_FIELD]["remove_phone_numbers"]["phone_numbers"].append(
                        phone_number)
                else:
                    change_messages[PHONE_NUMBERS_FIELD].update(
                        UserChangeMessage.phone_numbers_removed([phone_number])[PHONE_NUMBERS_FIELD]
                    )
            else:
                change_messages.update(UserChangeMessage.phone_numbers_removed([phone_number]))

        elif "CommCare Profile: None" == message:
            _check_for_double_entry(PROFILE_FIELD, message, change_messages)

            change_messages.update(UserChangeMessage.profile_info(None))

        elif PROFILE_REGEX.match(message):
            _check_for_double_entry("profile", message, change_messages)

            profile_name = PROFILE_REGEX.match(message).groups()[0]
            # get profile id from the user data changes
            profile_id = user_history.details['changes']['user_data'][PROFILE_SLUG]
            assert profile_name, f"profile name missing in message {message}"
            assert profile_id, f"Profile id missing in user data changes {user_history.details['changes']}"

            if not skip_assertions:
                # assert for complete message
                # compare name
                profile = CustomDataFieldsProfile.objects.get(pk=profile_id)
                assert profile.name == profile_name, "Looks like profile name changed. Found profile id " \
                                                     f"{profile_id} with name {profile.name} but name in log " \
                                                     f"is {profile_name}"

            change_messages.update(UserChangeMessage.profile_info(profile_id, profile_name))

        elif "Primary location: None" == message:
            _check_for_double_entry(LOCATION_FIELD, message, change_messages)

            change_messages.update(UserChangeMessage.primary_location_removed())

        elif user_history.user_type == "WebUser" and WEB_USER_PRIMARY_LOCATION_REGEX.match(message):
            _check_for_double_entry(LOCATION_FIELD, message, change_messages)

            location_name, location_id = WEB_USER_PRIMARY_LOCATION_REGEX.match(message).groups()
            assert location_name, f"location name missing in message {message}"
            assert location_id, f"location id missing in message {message}"

            location = SQLLocation.objects.get(location_id=location_id)
            assert location, f"Could not get location with id {location_id}"

            if not skip_assertions:
                # assert for complete message
                # compare name
                assert location.name == location_name, "Looks like location name changed. Found location id " \
                                                       f"{location_id} with name {location.name} but name in " \
                                                       f"log is {location_name}"

            change_messages.update(UserChangeMessage.primary_location_info(location))

            # fallback in case location has been deleted
            # change_messages[LOCATION_FIELD] = {
            #     "set_primary_location": {"id": location_id, "name": location_name}
            # }

        elif user_history.user_type == "CommCareUser" and COMMCARE_USER_PRIMARY_LOCATION_REGEX.match(message):
            _check_for_double_entry(LOCATION_FIELD, message, change_messages)

            location_name = COMMCARE_USER_PRIMARY_LOCATION_REGEX.match(message).groups()[0]
            location_id = user_history.details['changes']['location_id']
            assert location_name, f"location name missing in message {message}"
            assert location_id, f"location id missing in user changes {user_history.details['changes']}"

            location = SQLLocation.objects.get(location_id=location_id)
            assert location, f"Could not get location with id {location_id}"

            if not skip_assertions:
                # assert for complete message
                # compare name
                assert location.name == location_name, "Looks like location name changed. Found location id " \
                                                       f"{location_id} with name {location.name} but name in " \
                                                       f"log is {location_name}"

            change_messages.update(UserChangeMessage.primary_location_info(location))

            # fallback in case location has been deleted
            # change_messages[LOCATION_FIELD] = {
            #     "set_primary_location": {"id": location_id, "name": location_name}
            # }

        elif "Assigned locations: []" == message:
            _check_for_double_entry(ASSIGNED_LOCATIONS_FIELD, message, change_messages)

            change_messages.update(UserChangeMessage.assigned_locations_info([]))

        elif user_history.user_type == "CommCareUser" and COMMCARE_USER_ASSIGNED_LOCATIONS_REGEX.match(message):
            _check_for_double_entry(ASSIGNED_LOCATIONS_FIELD, message, change_messages)

            # "'loc1', 'loc2'"
            location_names = COMMCARE_USER_ASSIGNED_LOCATIONS_REGEX.match(message).groups()[0]
            location_ids = user_history.details['changes']["assigned_location_ids"]
            assert location_names, f"location names missing in message {message}"
            assert location_ids, f"location ids missing in changes {user_history.details['changes']}"

            # check for number of locations ids and names to be equal
            # split by , that has a ' or a " before it to avoid splitting names in case they have a ,
            # we should get a list of names
            location_names_list = re.split(r"(?<=['\"]), ", location_names)
            assert len(location_ids) == len(location_names_list)
            locations = SQLLocation.objects.filter(location_id__in=location_ids)
            assert len(locations) == len(location_ids), f"Could not find some locations {location_ids}"

            if not skip_assertions:
                # assert for complete message
                # check for names of locations now with names in message
                # check for name in the string location_names instead of location_names_list
                # because location_names_list has names with quotes escaped which results in faulty
                # mismatch
                for location in locations:
                    assert location.name in location_names, "Looks like some location name changed. " \
                                                            f"Could not find {location.name} in {location_names}"

            change_messages.update(UserChangeMessage.assigned_locations_info(locations))

        elif user_history.user_type == "WebUser" and WEB_USER_ASSIGNED_LOCATIONS_REGEX.match(message):
            _check_for_double_entry(ASSIGNED_LOCATIONS_FIELD, message, change_messages)

            # loc1[loc1_id], loc2[loc2_id]
            # split by , that has a ] before it to avoid splitting names in case they have a ,
            # we should get a list of Name[ID] like NAME_WITH_ID_REGEX
            locations_info = re.split(r"(?<=]), ", WEB_USER_ASSIGNED_LOCATIONS_REGEX.match(message).groups()[0])
            assert locations_info, f"locations info missing in message {message}"

            location_ids_to_names = {}
            for location_info in locations_info:
                location_name, location_id = NAME_WITH_ID_REGEX.match(location_info).groups()
                location_ids_to_names[location_id] = location_name
            assert location_ids_to_names, f"Could not fetch assigned locations in {message}"

            location_ids = list(location_ids_to_names.keys())
            locations = SQLLocation.objects.filter(location_id__in=location_ids)
            assert len(locations) == len(location_ids), f"Could not find some locations {location_ids}"

            if not skip_assertions:
                # assert for complete message
                # compare names
                location_names = list(location_ids_to_names.values())
                for location in locations:
                    assert location.name in location_names, "Looks like some location name changed. " \
                                                            f"Could not find {location.name} in {location_names}"

            change_messages.update(UserChangeMessage.assigned_locations_info(locations))
            # fallback in locations name have changed or missing
            # change_messages[ASSIGNED_LOCATIONS_FIELD] = {
            #     "set_assigned_locations": {
            #         "locations": [{'id': location_id, 'name': location_name}
            #                       for location_id, location_name in location_ids_to_names.items()]
            #     }
            # }

        elif "Groups: " == message or "Groups: []" == message:
            _check_for_double_entry(GROUPS_FIELD, message, change_messages)

            change_messages.update(UserChangeMessage.groups_info([]))

        elif GROUPS_REGEX.match(message):
            _check_for_double_entry(GROUPS_FIELD, message, change_messages)

            # group1[group1_id], group2[group2_id]
            # split by ],
            groups_info = re.split(r"(?<=]), ", GROUPS_REGEX.match(message).groups()[0])
            assert groups_info, f"groups info missing in message {message}"

            group_ids_to_names = {}
            for group_info in groups_info:
                group_name, group_id = NAME_WITH_ID_REGEX.match(group_info).groups()
                group_ids_to_names[group_id] = group_name
            group_ids = list(group_ids_to_names.keys())
            group_names = list(group_ids_to_names.values())
            assert group_ids_to_names, f"Could not fetch groups in message {message}"
            assert group_ids, f"Could not fetch group ids in message {message}"
            assert group_names, f"Could not fetch group names in message {message}"

            groups = [Group.wrap(doc) for doc in get_docs(Group.get_db(), group_ids)]
            assert len(groups) == len(group_ids), "Could not fetch all groups with ids"

            if not skip_assertions:
                # assert for complete message
                # compare names
                for group in groups:
                    assert group.name in group_names, f"Could not find {group.name} in {group_names}"

            change_messages.update(UserChangeMessage.groups_info(groups))
            # fallback in case groups has been deleted or names changed
            # change_messages[GROUPS_FIELD] = {
            #     "set_groups": {
            #         "groups": [{'id': group_id, 'name': group_name}
            #                    for group_id, group_name in group_ids_to_names.items()]
            #     }
            # }

        elif ADDED_AS_WEB_USER_REGEX.match(message):
            _check_for_double_entry(DOMAIN_FIELD, message, change_messages)

            domain = ADDED_AS_WEB_USER_REGEX.match(message).groups()[0]
            assert domain, f"could not find domain in message {message}"

            if not skip_assertions:
                # assert for complete message
                # fetch domain by name
                assert Domain.get_by_name(domain), f"Could not find domain with name {domain}"

            change_messages.update(UserChangeMessage.added_as_web_user(domain))

        elif INVITED_TO_DOMAIN_REGEX.match(message):
            _check_for_double_entry(DOMAIN_INVITATION_FIELD, message, change_messages)

            domain = INVITED_TO_DOMAIN_REGEX.match(message).groups()[0]
            assert domain, f"could not find domain in message {message}"

            if not skip_assertions:
                # assert for complete message
                # fetch domain by name
                assert Domain.get_by_name(domain), f"Could not find domain with name {domain}"

            change_messages.update(UserChangeMessage.invited_to_domain(domain))

        elif INVITATION_REVOKED_FOR_DOMAIN_REGEX.match(message):
            _check_for_double_entry(DOMAIN_INVITATION_FIELD, message, change_messages)

            domain = INVITATION_REVOKED_FOR_DOMAIN_REGEX.match(message).groups()[0]
            assert domain, f"could not find domain in message {message}"

            if not skip_assertions:
                # assert for complete message
                # fetch domain by name
                assert Domain.get_by_name(domain), f"Could not find domain with name {domain}"

            change_messages.update(UserChangeMessage.invitation_revoked_for_domain(domain))

        else:
            messages_not_converted.append(message)

    # consolidate status change message
    if status_update_active is not None or status_update_reason is not None:
        # assert both parts were present
        assert status_update_active is not None and status_update_reason is not None

        _check_for_double_entry(STATUS_FIELD, '', change_messages)
        change_messages.update(UserChangeMessage.status_update(
            status_update_active,
            status_update_reason
        ))

    # the only messages left should be the ones about two factor updates since they have a ". " in
    # the message and hence not a good way to split those out and parse them
    # join the messages back and parse it now. They should still be in the same order
    if messages_not_converted:
        messages_not_converted_joined = ". ".join(messages_not_converted)
        if DISABLED_WITH_VERIFICATION_REGEX.match(messages_not_converted_joined):
            _check_for_double_entry(TWO_FACTOR_FIELD, messages_not_converted_joined, change_messages)

            verified_by, verification_mode = DISABLED_WITH_VERIFICATION_REGEX.match(
                messages_not_converted_joined).groups()
            assert verified_by, f"Could not get verified by in message {messages_not_converted_joined}"
            assert verification_mode, f"Could not get verified by in message {messages_not_converted_joined}"

            change_messages.update(
                UserChangeMessage.two_factor_disabled_with_verification(
                    verified_by,
                    verification_mode,
                    disable_for_days
                )
            )
            messages_not_converted = []
    if messages_not_converted:
        raise Exception(f"Could not covert messages {messages_not_converted}")

    # skipped the following during dry run because too noisy and would possibly not keep it
    # re-render messages with change messages and flag any discrepancies with old set of messages
    # rendered_messages = list(get_messages(change_messages))
    # parsed_rendered_messages = []
    # for rendered_message in rendered_messages:
    #     # parse any messages that have changed now
    #     if user_history.user_type == "CommCareUser":
    #         if "Primary location: " in rendered_message:
    #             # parse new "Primary location: Name[ID]" to old "Primary location: Name"
    #             parsed_rendered_messages.append(rendered_message.split("[")[0])
    #         elif "Assigned locations: " in rendered_message:
    #             # parse new "Assigned locations: ['Name[ID]', 'Name[ID]']"
    #             # to old "Assigned locations: ['Name', 'Name']"
    #             # the order changes here to this needs a manual confirmation on warning
    #             location_names = []
    #             locations_regex = re.compile(r'Assigned locations: \[(.*)]')
    #             # split by ", " that has a ' or a " before it
    #             # we should get a list of Name[ID]
    #             locations_info = re.split(r"(?<=['\"]), ", locations_regex.match(rendered_message).groups()[0])
    #             for location_info in locations_info:
    #                 location_name, location_id = NAME_WITH_ID_REGEX.match(location_info.strip("'")).groups()
    #                 location_names.append(location_name)
    #             parsed_rendered_messages.append(f'Assigned locations: {location_names}')
    #         elif "Profile: " in rendered_message:
    #             # parse new "CommCare Profile: Name[ID]" to old "CommCare Profile: Name"
    #             profile_name = rendered_message.split(": ")[1].split('[')[0]
    #             parsed_rendered_messages.append(f'CommCare Profile: {profile_name}')
    #         else:
    #             parsed_rendered_messages.append(rendered_message)
    #     else:
    #         parsed_rendered_messages.append(rendered_message)
    #
    # # check all re-rendered messages are present in old messages
    # for rendered_message in parsed_rendered_messages:
    #     if rendered_message not in messages:
    #         print(f"Re-rendered extra:{user_history.pk} {rendered_message} in {user_history.message}")
    # # vice versa
    # for message in messages:
    #     if message not in parsed_rendered_messages:
    #         print(f"Re-rendered missed:{user_history.pk} {message} in {parsed_rendered_messages}")

    return change_messages


def _check_for_double_entry(field_name, message, change_messages):
    if field_name in change_messages:
        raise Exception(f"double entry for {field_name} with {message} "
                        f"and already present {change_messages[field_name]}")


def migrate_user_history_to_log_entry(user_history):
    """
    Add a new LogEntry for the user history record if users still in the system.
    This is only intended to keep back up of the deprecated columns (message, details) which would be migrated to
    new columns (change_messages, changes & changed_via) for debugging purposes after the deprecated columns
    are removed.
    :returns: log entry if it was created
    """
    from corehq.apps.users.models import CouchUser

    couch_user = CouchUser.get_by_user_id(user_history.user_id)
    changed_by_couch_user = CouchUser.get_by_user_id(user_history.changed_by)

    # if any of the user is missing, they must be now deleted and we can't get their django user for LogEntry
    # ignore such logs
    if couch_user and changed_by_couch_user:
        django_user = couch_user.get_django_user()
        changed_by_django_user = changed_by_couch_user.get_django_user()

        # keep a reference to the user history record
        change_message = {
            'user_history_pk': user_history.pk
        }
        # copy the deprecated text message column from UserHistory
        if user_history.message:
            change_message['message'] = user_history.message

        # copy the deprecated details column
        if user_history.details:
            change_message['details'] = user_history.details

        # reference https://github.com/dimagi/commcare-hq/blob/a1aa13913fc48cd23dfc85dc11f9412d5fe808f9/corehq/util/model_log.py#L38
        log_entry = LogEntry.objects.log_action(
            user_id=changed_by_django_user.pk,
            content_type_id=get_content_type_for_model(django_user).pk,
            object_id=django_user.pk,
            object_repr=force_text(django_user),
            action_flag=user_history.action,
            change_message=json.dumps(change_message)
        )
        log_entry.action_time = user_history.changed_at
        log_entry.save()
        return log_entry
    else:
        return False
