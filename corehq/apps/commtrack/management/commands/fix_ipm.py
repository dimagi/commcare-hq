from django.core.management.base import BaseCommand
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from corehq.util.couch_helpers import CouchAttachmentsBuilder
from corehq.apps.commtrack.models import SupplyPointCase
from lxml import etree
import re


class Command(BaseCommand):

    def handle(self, *args, **options):
        ids = get_form_ids_by_type('ipm-senegal', 'XFormInstance')

        to_save = []
        for doc in iter_docs(XFormInstance.get_db(), ids):
            try:
                if 'location_id' in doc['form'] and not doc['form']['location_id']:
                    case = SupplyPointCase.get(doc['form']['case']['@case_id'])
                    if case.type == 'supply-point':
                        instance = XFormInstance.get(doc['_id'])

                        # fix the XFormInstance
                        instance.form['location_id'] = case.location_id

                        # fix the actual form.xml
                        xml_object = etree.fromstring(instance.get_xml())
                        location_id_node = xml_object.find(re.sub('}.*', '}location_id', xml_object.tag))
                        location_id_node.text = case.location_id
                        updated_xml = etree.tostring(xml_object)

                        attachment_builder = CouchAttachmentsBuilder(instance._attachments)
                        attachment_builder.add(
                            name='form.xml',
                            content=updated_xml,
                            content_type=instance._attachments['form.xml']['content_type']
                        )
                        instance._attachments = attachment_builder.to_json()

                        print 'Updating XFormInstance:', doc['_id']
                        to_save.append(instance)
            except Exception:
                print 'Failed to save XFormInstance:', doc['_id']

            if len(to_save) > 500:
                XFormInstance.get_db().bulk_save(to_save)
                to_save = []

        if to_save:
            XFormInstance.get_db().bulk_save(to_save)
