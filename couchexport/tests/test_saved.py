# coding=utf-8
from django.test import TestCase
from couchexport.models import SavedBasicExport, ExportConfiguration


class SavedExportTest(TestCase):

    def testFileSaveAndLoad(self):
        def _mk_config(name):
            return ExportConfiguration(index='dummy_index', name=name, format='xlsx')

        payload = 'something small and simple'
        for name in ['normal', u'हिंदी', None]:
            saved = SavedBasicExport(configuration=_mk_config(name))
            saved.save()
            saved.set_payload(payload)
            self.assertEqual(payload, saved.get_payload())

