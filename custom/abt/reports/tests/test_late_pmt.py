from nose.tools import assert_equal

from corehq.apps.fixtures.models import (
    FieldList,
    FixtureDataItem,
    FixtureItemField,
)
from custom.abt.reports.late_pmt import fixture_data_item_to_dict


def test_fixture_data_item_to_dict():
    data_item = FixtureDataItem(
        domain='test-domain',
        data_type_id='123456',
        fields={
            'id': FieldList(
                doc_type='FieldList',
                field_list=[
                    FixtureItemField(
                        doc_type='FixtureItemField',
                        field_value='789abc',
                        properties={}
                    )
                ]
            ),
            'name': FieldList(
                doc_type='FieldList',
                field_list=[
                    FixtureItemField(
                        doc_type='FixtureItemField',
                        field_value='John',
                        properties={'lang': 'en'}
                    ),
                    FixtureItemField(
                        doc_type='FixtureItemField',
                        field_value='Jan',
                        properties={'lang': 'nld'}
                    ),
                    FixtureItemField(
                        doc_type='FixtureItemField',
                        field_value='Jean',
                        properties={'lang': 'fra'}
                    ),
                ]
            )
        }
    )
    dict_ = fixture_data_item_to_dict(data_item)
    assert_equal(dict_, {
        'id': '789abc',
        'name': 'John'
    })
