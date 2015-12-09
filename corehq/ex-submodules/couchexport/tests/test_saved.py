# coding=utf-8
import datetime
from django.test import TestCase
from couchexport.groupexports import get_saved_export_and_delete_copies
from couchexport.models import SavedBasicExport, ExportConfiguration


class SavedExportTest(TestCase):

    def test_file_save_and_load(self):
        payload = 'something small and simple'
        for name in ['normal', u'हिंदी', None]:
            saved = SavedBasicExport(configuration=_mk_config(name))
            saved.save()
            saved.set_payload(payload)
            self.assertEqual(payload, saved.get_payload())

    def test_get_by_index(self):
        index = ['some', 'index']
        saved_export = SavedBasicExport(configuration=_mk_config(index=index))
        saved_export.save()
        back = SavedBasicExport.by_index(index)
        self.assertEqual(1, len(back))
        self.assertEqual(saved_export._id, back[0]._id)

    def test_get_saved_and_delete_copies_missing(self):
        self.assertEqual(None, get_saved_export_and_delete_copies(['missing', 'index']))

    def test_get_saved_and_delete_copies_single(self):
        index = ['single']
        saved_export = SavedBasicExport(configuration=_mk_config(index=index))
        saved_export.save()
        self.assertEqual(saved_export._id, get_saved_export_and_delete_copies(index)._id)

    def test_get_saved_and_delete_copies_multiple(self):
        index = ['multiple']
        # make three exports with the last one being the most recently updated
        timestamp = datetime.datetime.utcnow()
        for i in range(3):
            saved_export = SavedBasicExport(configuration=_mk_config(index=index),
                                            last_updated=timestamp + datetime.timedelta(days=i))
            saved_export.save()

        self.assertEqual(3, len(SavedBasicExport.by_index(index)))
        chosen_one = get_saved_export_and_delete_copies(index)
        # this relies on the variable being set last in the loop which is a bit unintuitive
        self.assertEqual(saved_export._id, chosen_one._id)
        saved_after_deletion = SavedBasicExport.by_index(index)
        self.assertEqual(1, len(saved_after_deletion))
        self.assertEqual(chosen_one._id, saved_after_deletion[0]._id)


def _mk_config(name='some export name', index='dummy_index'):
    return ExportConfiguration(index=index, name=name, format='xlsx')
