from couchdbkit.ext.django.schema import StringProperty
from django.test import TestCase
from dimagi.utils.couch.lazy_attachment_doc import LazyAttachmentDoc


class SampleDoc(LazyAttachmentDoc):

    name = StringProperty()


class LazyAttachmentDocTest(TestCase):

    def setUp(self):
        self.sample = SampleDoc(name='test sample doc')

    def test_put_lazy_attachment(self):
        content = 'this is my content'
        content2 = 'this is my content2'
        name = 'content.txt'

        def test(content, prev_content=None):
            self.sample.lazy_put_attachment(content, name=name)
            self.assertEqual(self.sample.lazy_fetch_attachment(name), content)
            if prev_content:
                self.assertEqual(self.sample.fetch_attachment(name),
                                 prev_content)
            else:
                with self.assertRaises(KeyError):
                    self.sample.fetch_attachment(name)
            self.sample.save()
            self.assertEqual(self.sample.fetch_attachment(name), content)
            self.assertEqual(self.sample.lazy_fetch_attachment(name), content)
            self.assertEqual(
                SampleDoc.get(self.sample.get_id).fetch_attachment(name),
                content
            )
            self.assertEqual(
                SampleDoc.get(self.sample.get_id).lazy_fetch_attachment(name),
                content
            )

        test(content)
        test(content2, prev_content=content)