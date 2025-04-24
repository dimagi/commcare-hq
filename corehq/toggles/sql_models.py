from django.contrib.postgres.fields import ArrayField
from django.db import models

from corehq.toggles import ALL_TAGS

TAG_SLUG_CHOICES = [(tag.slug, tag.slug) for tag in ALL_TAGS]


class ToggleEditPermission(models.Model):
    """
    Restricts edit access to the toggles under the tag to enabled users only.
    If the tag entry does not exist, there are no edit restrictions for the toggles under it.
    """
    tag_slug = models.CharField(max_length=255, choices=TAG_SLUG_CHOICES, unique=True)
    enabled_users = ArrayField(models.CharField(max_length=255), default=list, blank=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def add_users(self, usernames):
        assert isinstance(usernames, list)
        users_to_add = [username for username in usernames if username not in self.enabled_users]
        if users_to_add:
            self.enabled_users.extend(users_to_add)
            self.save()

    def remove_users(self, usernames):
        assert isinstance(usernames, list)
        users_to_remove = [username for username in usernames if username in self.enabled_users]
        if users_to_remove:
            for user in users_to_remove:
                self.enabled_users.remove(user)
            self.save()

    def is_user_enabled(self, username):
        return username in self.enabled_users
