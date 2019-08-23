from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

import mock
from django.test import SimpleTestCase
from corehq.apps.export.models import FormExportInstance, TableConfiguration, ExportColumn, ScalarItem, PathNode
from corehq.apps.reports.tasks import (
    _extract_form_attachment_info,
    _get_export_properties,
)
from corehq.blobs.models import BlobMeta
from corehq.form_processor.models import XFormInstanceSQL
from couchforms.models import XFormInstance


class FormMultimediaExportTest(SimpleTestCase):

    def test_get_export_properties(self):
        export_instance = FormExportInstance(
            tables=[
                TableConfiguration(
                    label="My table",
                    selected=True,
                    path=[],
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q3')],
                            ),
                            selected=True,
                        ),
                        ExportColumn(
                            label="dontshow",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='dontshow')],
                            ),
                            selected=False,
                        ),
                    ]
                ),
                TableConfiguration(
                    label="My other table",
                    selected=True,
                    path=[PathNode(name='form', is_repeat=False), PathNode(name="q2", is_repeat=False)],
                    columns=[
                        ExportColumn(
                            label="Q4",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q2'), PathNode(name='q4')],
                            ),
                            selected=True,
                        ),
                    ]
                )
            ]
        )
        props = _get_export_properties(export_instance)
        self.assertEqual(props, set(['q2-q4', 'q3']))

    def test_extract_form_attachment_info(self):
        image_1_name = "1234.jpg"
        image_2_name = "5678.jpg"
        form = {
            "name": "foo",
            "color": "bar",
            "image_1": image_1_name,
            "my_group": {
                "image_2": image_2_name
            }
        }
        attachments = {
            image_1_name: {
                "content_type": "image/jpeg",
                "content_length": 1024,
            },
            image_2_name: {
                "content_type": "image/jpeg",
                "content_length": 2048,
            },
            "form.xml": {
                "content_type": "text/xml",
                "content_length": 2048,
            }
        }
        with mock.patch.object(XFormInstanceSQL, 'form_data') as form_data_mock:
            form_data_mock.__get__ = mock.MagicMock(return_value=form)
            couch_xform = XFormInstance(
                received_on=datetime.datetime.now(),
                form=form,
            )
            for name, meta in attachments.items():
                couch_xform.deferred_put_attachment("content", name, **meta)
            sql_xform = XFormInstanceSQL(received_on=datetime.datetime.now())
            sql_xform.attachments_list = [BlobMeta(name=name, **meta)
                for name, meta in attachments.items()]

            for xform in (couch_xform, sql_xform):
                print(type(xform).__name__)
                form_info = _extract_form_attachment_info(xform, {"my_group-image_2", "image_1"})
                attachments = {a['name']: a for a in form_info['attachments']}
                self.assertTrue(image_1_name in attachments)
                self.assertTrue(image_2_name in attachments)
                self.assertEqual(attachments[image_1_name]['question_id'], "image_1")
                self.assertEqual(attachments[image_2_name]['question_id'], "my_group-image_2")
