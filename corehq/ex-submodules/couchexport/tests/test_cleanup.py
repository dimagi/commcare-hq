from django.test import TestCase
from couchexport.export import ExportConfiguration
from dimagi.utils.couch.database import get_safe_write_kwargs, get_db
from couchexport.util import clear_attachments, clear_computed


class CleanupTest(TestCase):

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

        # check that it works both explicitly and by default
        explicit_config = ExportConfiguration(db, ['attachments-test'], cleanup_fn=clear_attachments)
        default_config = ExportConfiguration(db, ['attachments-test'])
        for config in (explicit_config, default_config):
            schema = config.get_latest_schema()
            self.assertFalse('_attachments' in schema)
            docs = list(config.get_docs())
            self.assertEqual(1, len(docs))
            self.assertFalse('_attachments' in docs[0])

    def testComputedRemoved(self):
        db = get_db()
        db.save_doc({
                '#export_tag': 'tag',
                'tag': 'computed-test',
                'p1': 'v1',
                'computed_': {
                    'ignore': 'this stuff'
                }
            },
            **get_safe_write_kwargs()
        )

        config = ExportConfiguration(db, ['computed-test'], cleanup_fn=None)
        schema = config.get_latest_schema()
        self.assertTrue('computed_' in schema)
        docs = list(config.get_docs())
        self.assertEqual(1, len(docs))
        self.assertTrue('computed_' in docs[0])

        # check that it works both explicitly and by default
        explicit_config = ExportConfiguration(db, ['computed-test'], cleanup_fn=clear_computed)
        default_config = ExportConfiguration(db, ['computed-test'])
        for config in (explicit_config, default_config):
            schema = config.get_latest_schema()
            self.assertFalse('computed_' in schema)
            docs = list(config.get_docs())
            self.assertEqual(1, len(docs))
            self.assertFalse('computed_' in docs[0])
