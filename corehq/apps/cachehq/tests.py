from copy import deepcopy
from mock import patch
from django.test import SimpleTestCase
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.ext.jsonobject import JsonObject, StringProperty


class Super(JsonObject):
    @classmethod
    def get(cls, *args, **kwargs):
        pass

    def save(self, *args, **kwargs):
        pass


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
