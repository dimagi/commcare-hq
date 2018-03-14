from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
import pickle
from corehq.apps.case_importer.util import ImporterConfig
from corehq.util.test_utils import make_make_path

_make_path = make_make_path(__file__)


class ImporterConfigCompatTest(SimpleTestCase):
    """
    test ImporterConfigs serialized (using `pickle.dumps(config, protocol=2)`)
    at various code commits can be correctly deserialized
    """
    def test_e296e568__2016_12_16(self):
        ic = pickle.loads(
            '\x80\x02ccorehq.apps.case_importer.util\nImporterConfig\nq\x00(U\rcouch_user_idq\x01U\x0cexcel_fieldsq\x02U\x0bcase_fieldsq\x03U\rcustom_fieldsq\x04U\rsearch_columnq\x05U\nkey_columnq\x06U\x0cvalue_columnq\x07U\rnamed_columnsq\x08U\tcase_typeq\tU\x0csearch_fieldq\nU\x10create_new_casesq\x0btq\x0c\x81q\r.')
        self.assertEqual(
            ic,
            ImporterConfig(
                couch_user_id='couch_user_id',
                excel_fields='excel_fields',
                case_fields='case_fields',
                custom_fields='custom_fields',
                search_column='search_column',
                # these three were removed
                #   key_column='key_column',
                #   value_column='value_column',
                #   named_columns='named_columns',
                case_type='case_type',
                search_field='search_field',
                create_new_cases='create_new_cases',
            )
        )

    def test_41e39e16__2016_12_16(self):
        ic = pickle.loads(
            '\x80\x02ccorehq.apps.case_importer.util\nImporterConfig\nq\x00(U\rcouch_user_idq\x01U\x0cexcel_fieldsq\x02U\x0bcase_fieldsq\x03U\rcustom_fieldsq\x04U\rsearch_columnq\x05U\tcase_typeq\x06U\x0csearch_fieldq\x07U\x10create_new_casesq\x08tq\t\x81q\n.')
        self.assertEqual(
            ic,
            ImporterConfig(
                couch_user_id='couch_user_id',
                excel_fields='excel_fields',
                case_fields='case_fields',
                custom_fields='custom_fields',
                search_column='search_column',
                case_type='case_type',
                search_field='search_field',
                create_new_cases='create_new_cases',
            )
        )
