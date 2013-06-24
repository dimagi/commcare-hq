from django.test import TestCase
from couchexport.export import ExportConfiguration
from dimagi.utils.couch.database import get_safe_write_kwargs, get_db


class CleanupAttachmentTest(TestCase):

    def testAttachmentsRemoved(self):
        db = get_db()
        res = db.save_doc({
            '#export_tag': 'tag',
            'tag': 'attachments-test',
            'p1': 'v1',
            },
            **get_safe_write_kwargs()
        )
        doc = db.get(res['id'])
        db.put_attachment(doc, 'some content', 'attach.txt')

        config = ExportConfiguration(db, ['attachments-test'], cleanup_fn=None)
        schema = config.get_latest_schema()
        self.assertTrue('_attachments' in schema)
        docs = list(config.get_docs())
        self.assertEqual(1, len(docs))
        self.assertTrue('_attachments' in docs[0])

        config = ExportConfiguration(db, ['attachments-test'])
        schema = config.get_latest_schema()
        self.assertFalse('_attachments' in schema)
        docs = list(config.get_docs())
        self.assertEqual(1, len(docs))
        self.assertFalse('_attachments' in docs[0])
