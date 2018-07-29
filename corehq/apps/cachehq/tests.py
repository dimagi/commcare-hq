from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
from django.conf import settings
from mock import patch
from django.test import SimpleTestCase
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.ext.jsonobject import JsonObject, StringProperty


class Super(JsonObject):
    _id = StringProperty()

    @classmethod
    def get(cls, *args, **kwargs):
        pass

    def save(self, *args, **kwargs):
        pass

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def bulk_save(self, *args, **kwargs):
        pass

    save_docs = bulk_save

    @classmethod
    def bulk_delete(self, *args, **kwargs):
        pass

    delete_docs = bulk_delete

    @classmethod
    def get_db(cls):
        return settings.COUCH_DATABASE

    @property
    def _doc(self):
        return self._obj


class BlogPost(CachedCouchDocumentMixin, Super):
    title = StringProperty()
    body = StringProperty()


class TestCachedCouchDocumentMixin(SimpleTestCase):

    @patch.object(Super, 'get')
    def test_get(self, doc_get):
        blog_post = BlogPost(title="My favorite colors", body="blue")
        blog_post['_id'] = 'idssrgglcfoyxdtrunbcae'
        doc_get.return_value = deepcopy(blog_post)
        blog_post.save()
        blog_post.clear_caches()

        # Make two `get`s and assert that only one made it to Document.get
        BlogPost.get(blog_post['_id'])
        BlogPost.get(blog_post['_id'])
        doc_get.assert_called_once_with(blog_post['_id'])

        # Update the doc, save, and assert that Document.get was hit again
        blog_post.body = "Actually, it's purple"
        blog_post.save()
        BlogPost.get(blog_post['_id'])
        self.assertEqual(doc_get.call_count, 2)

    @patch.object(BlogPost, 'clear_caches')
    def test_clear_caches(self, clear_caches):
        blog_post = BlogPost(_id='alksfjdaasdfkjahg')
        self.assertEqual(clear_caches.call_count, 0)
        blog_post.save()
        self.assertEqual(clear_caches.call_count, 1)
        blog_post.delete()
        self.assertEqual(clear_caches.call_count, 2)
        BlogPost.bulk_save([blog_post])
        self.assertEqual(clear_caches.call_count, 3)
        BlogPost.bulk_delete([blog_post])
        self.assertEqual(clear_caches.call_count, 4)
        BlogPost.save_docs([blog_post])
        self.assertEqual(clear_caches.call_count, 5)
        BlogPost.delete_docs([blog_post])
        self.assertEqual(clear_caches.call_count, 6)
