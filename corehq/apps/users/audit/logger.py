from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.util import log_user_change


class UserChangeLogger(object):
    """
    User change logger to record
        - changes to user properties
        - text messages for changes
        - useful info for changes to associated data models like role/locations
    """

    def __init__(self, by_domain, for_domain, user, is_new_user, changed_by_user, changed_via,
                 upload_record_id, user_domain_required_for_log=True):
        self.by_domain = by_domain
        self.for_domain = for_domain
        self.user = user
        self.is_new_user = is_new_user
        self.changed_by_user = changed_by_user
        self.changed_via = changed_via
        self.upload_record_id = upload_record_id
        self.user_domain_required_for_log = user_domain_required_for_log

        if not is_new_user:
            self.original_user_doc = self.user.to_json()
        else:
            self.original_user_doc = None

        self.fields_changed = {}
        self.change_messages = {}

        self._save = False  # flag to check if log needs to be saved for updates

    def add_changes(self, changes):
        """
        Add changes to user properties.
        Ignored for new user since the whole user doc is logged for a new user
        :param changes: dict of property mapped to it's new value
        """
        if self.is_new_user:
            return
        for name, new_value in changes.items():
            if self.original_user_doc[name] != new_value:
                self.fields_changed[name] = new_value
                self._save = True

    def add_change_message(self, message):
        """
        Add change message for a change in user property that is in form of a UserChangeMessage
        Ignored for new user since the whole user doc is logged for a new user
        :param message: text message for the change like 'Password reset' / 'Added as web user to domain foo'
        """
        if self.is_new_user:
            return
        self._update_change_messages(message)
        self._save = True

    def _update_change_messages(self, change_messages):
        for slug in change_messages:
            if slug in self.change_messages:
                raise UserUploadError(f"Double Entry for {slug}")
        self.change_messages.update(change_messages)

    def add_info(self, change_message):
        """
        Add change message for a change to the user that is in form of a UserChangeMessage
        """
        self._update_change_messages(change_message)
        self._save = True

    def save(self):
        if self.is_new_user or self._save:
            action = UserModelAction.CREATE if self.is_new_user else UserModelAction.UPDATE
            fields_changed = None if self.is_new_user else self.fields_changed
            log_user_change(
                by_domain=self.by_domain,
                for_domain=self.for_domain,
                couch_user=self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                change_messages=self.change_messages,
                action=action,
                fields_changed=fields_changed,
                bulk_upload_record_id=self.upload_record_id,
                for_domain_required_for_log=self.user_domain_required_for_log,
            )
