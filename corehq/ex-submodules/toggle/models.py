from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import uuid

from couchdbkit import ResourceNotFound, ResourceConflict
from django.contrib import admin
from django.db import models

from corehq.apps.couch_sql_migration.fields import DocumentField
from corehq.util.quickcache import quickcache
from dimagi.ext.couchdbkit import (
    Document, DateTimeProperty, ListProperty, StringProperty
)


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
        if ('_rev' not in self._doc):
            self._rev = self._doc['_rev'] = uuid.uuid4().hex
            rev_not_provided = True
        else:
            rev_not_provided = False
        self.last_modified = datetime.utcnow()
        obj, created = SqlToggle.objects.get_or_create(
            id=self._doc['_id'], defaults={'document': self, 'rev': self._rev or 1}
        )
        if created is False:
            if rev_not_provided or self._rev != obj.rev:
                raise ResourceConflict

            self._doc['_rev'] = obj.rev = uuid.uuid4().hex
            obj.document = self
            obj.save()
        self._rev = obj.rev

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
        tog = SqlToggle.objects.filter(id=docid).first()
        if tog is None:
            raise ResourceNotFound
        return tog.document

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
        SqlToggle.objects.filter(id=self._doc['_id']).delete()
        self.bust_cache()

    def bust_cache(self):
        self.cached_get.clear(self.__class__, self.slug)


def generate_toggle_id(slug):
    # use the slug to build the ID to avoid needing couch views
    # and to make looking up in futon easier
    return '{prefix}-{slug}'.format(prefix=TOGGLE_ID_PREFIX, slug=slug)


class SqlToggle(models.Model):
    id = models.CharField(max_length=126, primary_key=True)
    rev = models.CharField(max_length=126)
    document = DocumentField(document_class=Toggle)


admin.site.register(SqlToggle)  # note that this does not work well as document is not JSON serializable
