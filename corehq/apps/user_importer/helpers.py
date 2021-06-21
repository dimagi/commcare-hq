from dimagi.utils.parsing import string_to_boolean

from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.util import log_user_change


def spec_value_to_boolean_or_none(user_spec_dict, key):
    value = user_spec_dict.get(key, None)
    if value and isinstance(value, str):
        return string_to_boolean(value)
    elif isinstance(value, bool):
        return value
    else:
        return None


class UserChangeLogger(object):
    def __init__(self, domain, user, is_new_user, changed_by_user, changed_via):
        self.domain = domain
        self.user = user
        self.is_new_user = is_new_user
        self.changed_by_user = changed_by_user
        self.changed_via = changed_via

        self.original_user_doc = self.user.to_json()
        self.fields_changed = {}
        self.messages = []

        self._save = False  # flag to check if log needs to be saved for updates

    def add_changes(self, changes):
        # ignore for new user since the whole user doc is logged for a new user
        if self.is_new_user:
            return
        for name, new_value in changes.items():
            if self.original_user_doc[name] != new_value:
                self.fields_changed[name] = new_value
                self._save = True

    def add_change_message(self, message):
        # ignore for new user since the whole user doc is logged for a new user
        if self.is_new_user:
            return
        self.messages.append(message)
        self._save = True

    def add_info(self, info):
        # useful info for display like names
        self.messages.append(info)
        self._save = True

    def save(self):
        self._include_user_data_changes()
        if self.is_new_user:
            log_user_change(
                self.domain,
                self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                message=". ".join(self.messages),
                action=UserModelAction.CREATE,
            )
        else:
            if not self._save:
                return
            log_user_change(
                self.domain,
                self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                message=". ".join(self.messages),
                fields_changed=self.fields_changed
            )

    def _include_user_data_changes(self):
        # ToDo: consider putting just the diff
        if self.original_user_doc['user_data'] != self.user.user_data:
            self.fields_changed['user_data'] = self.user.user_data
            self._save = True
