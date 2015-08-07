from copy import deepcopy
from mock import patch, MagicMock
from django.test import SimpleTestCase
from dimagi.ext import couchdbkit as couch
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin


class BlogPost(CachedCouchDocumentMixin, couch.Document):
    title = couch.StringProperty()
    body = couch.StringProperty()


class TestCachedCouchDocumentMixin(SimpleTestCase):
    @patch('dimagi.ext.couchdbkit.Document.save', MagicMock())
    @patch('dimagi.ext.couchdbkit.Document.get')
    def test_get(self, doc_get):
        blog_post = BlogPost(title="My favorite colors", body="blue")
        blog_post._id = 'idssrgglcfoyxdtrunbcae'
        doc_get.return_value = deepcopy(blog_post)
        blog_post.save()
        blog_post.clear_caches()

        # Make two `get`s and assert that only one made it to Document.get
        BlogPost.get(blog_post._id)
        BlogPost.get(blog_post._id)
        doc_get.assert_called_once_with(blog_post._id)

        # Update the doc, save, and assert that Document.get was hit again
        blog_post.body = "Actually, it's purple"
        blog_post.save()
        BlogPost.get(blog_post._id)
        self.assertEqual(doc_get.call_count, 2)
