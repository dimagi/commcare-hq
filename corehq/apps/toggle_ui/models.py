from django.db import models

from corehq.toggles import NAMESPACE_USER, NAMESPACE_DOMAIN, NAMESPACE_OTHER


class ToggleAuditManager(models.Manager):
    def log_toggle_changes(self, slug, username, current_items, previous_items, randomness):
        if current_items != previous_items:
            added = current_items - previous_items
            removed = previous_items - current_items
            for action, namespaced_items in [(ToggleAudit.ACTION_ADD, added), (ToggleAudit.ACTION_REMOVE, removed)]:
                self.log_toggle_action(slug, username, namespaced_items, action)

        if randomness is not None:
            self.create(
                slug=slug, username=username, action=ToggleAudit.ACTION_UPDATE_RANDOMNESS,
                randomness=randomness
            )

    def log_toggle_action(self, slug, username, namespaced_items, action):
        for namespaced_item in namespaced_items:
            namespace, item = parse_item(namespaced_item)
            self.create(
                slug=slug, username=username, action=action,
                namespace=namespace, item=item
            )


class ToggleAudit(models.Model):
    ACTION_ADD = "add"
    ACTION_REMOVE = "remove"
    ACTION_UPDATE_RANDOMNESS = "random"
    ACTION_CHOICES = (
        (ACTION_ADD, ACTION_ADD),
        (ACTION_REMOVE, ACTION_REMOVE),
        (ACTION_UPDATE_RANDOMNESS, ACTION_UPDATE_RANDOMNESS),
    )
    NAMESPACE_CHOICES = (
        (NAMESPACE_USER, NAMESPACE_USER),
        (NAMESPACE_DOMAIN, NAMESPACE_DOMAIN),
        (NAMESPACE_OTHER, NAMESPACE_OTHER),
    )

    created = models.DateTimeField(auto_now=True)
    slug = models.TextField()
    username = models.CharField(max_length=256, help_text="Username of user making change")
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    namespace = models.CharField(max_length=12, choices=NAMESPACE_CHOICES, null=True)
    item = models.TextField(null=True)
    randomness = models.DecimalField(max_digits=6, decimal_places=5, null=True)

    objects = ToggleAuditManager()


def parse_item(namespaced_item):
    if ":" not in namespaced_item:
        return NAMESPACE_USER, namespaced_item

    nsp, item = namespaced_item.split(":", 1)
    if nsp in (NAMESPACE_DOMAIN, NAMESPACE_OTHER):
        return nsp, item
    return NAMESPACE_USER, namespaced_item
