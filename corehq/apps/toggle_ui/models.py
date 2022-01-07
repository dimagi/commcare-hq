from datetime import datetime

from couchdbkit import ResourceNotFound
from django.db import models

from dimagi.ext.couchdbkit import (
    Document, DateTimeProperty, ListProperty, StringProperty
)
from corehq.toggles import NAMESPACE_USER, NAMESPACE_DOMAIN, NAMESPACE_OTHER
from corehq.util.quickcache import quickcache


TOGGLE_ID_PREFIX = 'hqFeatureToggle'


class Toggle(Document):
    """
    A very simple implementation of a feature toggle. Just a list of items
    attached to a slug.
    """
    slug = StringProperty()
    enabled_users = ListProperty()
    last_modified = DateTimeProperty()

    class Meta(object):
        app_label = 'toggle'

    def save(self, **params):
        if ('_id' not in self._doc):
            self._doc['_id'] = generate_toggle_id(self.slug)
        self.last_modified = datetime.utcnow()
        super(Toggle, self).save(**params)
        self.bust_cache()

    @classmethod
    @quickcache(['cls.__name__', 'docid'], timeout=60 * 60 * 24)
    def cached_get(cls, docid):
        try:
            return cls.get(docid)
        except ResourceNotFound:
            return None

    @classmethod
    def get(cls, docid):
        if not docid.startswith(TOGGLE_ID_PREFIX):
            docid = generate_toggle_id(docid)
        return super(Toggle, cls).get(docid, rev=None, db=None, dynamic_properties=True)

    def add(self, item):
        """
        Adds an item to the toggle. Only saves if necessary.
        """
        if item not in self.enabled_users:
            self.enabled_users.append(item)
            self.save()

    def remove(self, item):
        """
        Removes an item from the toggle. Only saves if necessary.
        """
        if item in self.enabled_users:
            self.enabled_users.remove(item)
            self.save()

    def delete(self):
        super(Toggle, self).delete()
        self.bust_cache()

    def bust_cache(self):
        self.cached_get.clear(self.__class__, self.slug)


def generate_toggle_id(slug):
    # use the slug to build the ID to avoid needing couch views
    # and to make looking up in futon easier
    return '{prefix}-{slug}'.format(prefix=TOGGLE_ID_PREFIX, slug=slug)


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
