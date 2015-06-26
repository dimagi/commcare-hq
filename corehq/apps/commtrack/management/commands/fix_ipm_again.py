from django.core.management.base import BaseCommand
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from corehq.util.couch_helpers import CouchAttachmentsBuilder
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.models import SQLLocation
from lxml import etree
import re


class Command(BaseCommand):

    def handle(self, *args, **options):
        ids = get_form_ids_by_type('ipm-senegal', 'XFormInstance')

        to_save = []

        locations = SQLLocation.objects.filter(domain='ipm-senegal').values_list('location_id', 'name')
        locations_map = {location_id: name for (location_id, name) in locations}

        for doc in iter_docs(XFormInstance.get_db(), ids):
            try:
                if 'PPS_name' in doc['form'] and not doc['form']['PPS_name']:
                    case = SupplyPointCase.get(doc['form']['case']['@case_id'])
                    if case.type == 'supply-point':
                        print 'Updating XFormInstance:', doc['_id']

                        pps_name = locations_map[case.location_id]

                        instance = XFormInstance.get(doc['_id'])

                        # fix the XFormInstance
                        instance.form['PPS_name'] = pps_name
                        for instance_prod in instance.form['products']:
                            instance_prod['PPS_name'] = instance_prod['PPS_name'] or pps_name

                        # fix the actual form.xml
                        xml_object = etree.fromstring(instance.get_xml())
                        pps_name_node = xml_object.find(re.sub('}.*', '}PPS_name', xml_object.tag))
                        pps_name_node.text = pps_name

                        products_nodes = xml_object.findall(re.sub('}.*', '}products', xml_object.tag))
                        for product_node in products_nodes:
                            product_pps_name_node = product_node.find(re.sub('}.*', '}PPS_name', xml_object.tag))
                            product_pps_name_node.text = pps_name
                        updated_xml = etree.tostring(xml_object)

                        attachment_builder = CouchAttachmentsBuilder(instance._attachments)
                        attachment_builder.add(
                            name='form.xml',
                            content=updated_xml,
                            content_type=instance._attachments['form.xml']['content_type']
                        )
                        instance._attachments = attachment_builder.to_json()

                        to_save.append(instance)
            except Exception:
                print 'Failed to save XFormInstance:', doc['_id']

            if len(to_save) > 500:
                XFormInstance.get_db().bulk_save(to_save)
                to_save = []

        if to_save:
            XFormInstance.get_db().bulk_save(to_save)
