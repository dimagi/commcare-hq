from collections import defaultdict

from corehq.util.model_log import log_model_change
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import get_request


class TrackModelUpdates(object):
    def __init__(self, model_object, by_user=None):
        self.model_object = model_object
        self.by_user = by_user

    def _can_track(self):
        if not hasattr(self.model_object, 'track_updates_for') or not self.model_object.track_updates_for:
            return False
        if not hasattr(self.model_object, '_original'):
            soft_assert(to=["mkangia@dimagi.com"], notify_admins=False, exponential_backoff=True)(
                False, "Model called without original doc"
            )
            return False
        if not self.by_user:
            request = get_request()
            try:
                django_user = request.user
            except:
                soft_assert(to=["mkangia@dimagi.com"], notify_admins=False, exponential_backoff=True)(
                    False, "Could not get user for request"
                )
                return False
            else:
                self.by_user = django_user
        return True

    def save(self):
        if not self._can_track():
            return False
        changes = defaultdict(dict)
        for attr_to_check in self.model_object.track_updates_for:
            new_value = self.model_object._doc.get(attr_to_check)
            old_value = self.model_object._original.get(attr_to_check)
            if old_value and not new_value:
                changes[attr_to_check]['delete'] = old_value
            elif new_value and not old_value:
                changes[attr_to_check]['create'] = new_value
            else:
                if hasattr(self.model_object, f"compare_{attr_to_check}"):
                    attr_changes = getattr(self.model_object, f"compare_{attr_to_check}")(self.model_object._original)
                    if attr_changes:
                        changes[attr_to_check] = attr_changes
        if changes:
            log_model_change(user=self.by_user, model_object=self.model_object.get_django_user(),
                             message=dict(changes))
        return True
