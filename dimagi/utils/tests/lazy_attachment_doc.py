from couchdbkit.ext.django.schema import StringProperty
from django.test import TestCase
from dimagi.utils.couch.lazy_attachment_doc import LazyAttachmentDoc


class SampleDoc(LazyAttachmentDoc):

    name = StringProperty()

    class Meta:
        app_label = 'utils'


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

    def test_wrap(self):
        name = 'lordsprayer.txt'
        lordsprayer = """
            Our Father who art in heaven,
            hallowed be thy name.
            Thy kingdom come.
            Thy will be done
            on earth as it is in heaven.
            Give us this day our daily bread,
            and forgive us our trespasses,
            as we forgive those who trespass against us,
            and lead us not into temptation,
            but deliver us from evil.
        """
        doc = SampleDoc.wrap({'_attachments': {
            name: lordsprayer
        }, 'name': 'Texts'})

        with self.assertRaises(KeyError):
            doc.fetch_attachment(name)
        self.assertEqual(doc.lazy_fetch_attachment(name), lordsprayer)
        doc.save()

        self.assertEqual(doc.fetch_attachment(name), lordsprayer)
        self.assertEqual(doc.lazy_fetch_attachment(name), lordsprayer)

        SampleDoc.wrap({})

    def test_lazy_list_attachments(self):
        doc = SampleDoc.wrap({'_attachments': {'one.txt': '1'}})
        doc.save()
        self.assertEqual(doc.lazy_list_attachments(),
                         set(doc._attachments.keys()))
        doc.lazy_put_attachment('2', 'two.txt')
        self.assertEqual(doc.lazy_list_attachments(),
                         set(['one.txt', 'two.txt']))
        self.assertNotEqual(doc.lazy_list_attachments(),
                            set(doc._attachments.keys()))
        doc.save()
        self.assertEqual(doc.lazy_list_attachments(),
                         set(doc._attachments.keys()))

    def test_null_lazy_list_attachments(self):
        doc = SampleDoc.wrap({})
        self.assertEqual(doc.lazy_list_attachments(), set())
