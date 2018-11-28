from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from dimagi.ext.couchdbkit import (
    Document, DateTimeProperty, ListProperty, StringProperty
)
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

    def save(self, **params):
        if ('_id' not in self._doc):
            self._doc['_id'] = generate_toggle_id(self.slug)
        self.last_modified = datetime.utcnow()
        super(Toggle, self).save(**params)
        self.bust_cache()

    @classmethod
    @quickcache(['cls.__name__', 'docid'], timeout=60 * 60 * 24, skip_arg="skip_cache")
    def get(cls, docid, rev=None, db=None, dynamic_properties=True, skip_cache=False):
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

    def bust_cache(self):
        self.get.clear(self.__class__, self.slug)


def generate_toggle_id(slug):
    # use the slug to build the ID to avoid needing couch views
    # and to make looking up in futon easier
    return '{prefix}-{slug}'.format(prefix=TOGGLE_ID_PREFIX, slug=slug)
