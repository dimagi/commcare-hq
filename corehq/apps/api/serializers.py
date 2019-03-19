
# Standard library imports
from __future__ import absolute_import
from __future__ import unicode_literals
from io import BytesIO

# Django & Tastypie imports
from django.utils.encoding import force_text
from tastypie.bundle import Bundle
from tastypie.serializers import Serializer, get_type_string

# External imports
import defusedxml.lxml as lxml
from lxml.etree import Element
import six

from corehq.util.python_compatibility import soft_assert_type_text


class CommCareCaseSerializer(Serializer):
    '''
    A custom serializer that emits XML that matches a case's
    definition according to CaseXML rather than the
    automated Tastypie equivalent of the JSON output
    '''

    def case_to_etree(self, case):
        '''
        Encapsulates the version passed to `CommCareCase.to_xml` and
        the temporary hack of re-parsing it. TODO: expose a direct etree
        encoding in casexml?
        '''
        return lxml.parse(BytesIO(case.to_xml('2.0', include_case_on_closed=True))).getroot()

    def bundle_to_etree(self, bundle):
        '''
        A new override point we have added - how to convert a single-object bundle to XML.
        The list endpoint will re-use this.
        '''
        return self.case_to_etree(bundle.obj)

    def to_etree(self, data, options=None, name=None, depth=0):
        '''
        Exact duplicate of tastypie.serializers.Serializer.to_etree with modification because
        it does not expose sufficient APIs to customize just at the bundle level while reusing
        all this same envelope code.
        '''
        if isinstance(data, (list, tuple)):
            element = Element(name or 'objects')
            if name:
                element = Element(name)
                element.set('type', 'list')
            else:
                element = Element('objects')
            for item in data:
                element.append(self.to_etree(item, options, depth=depth+1))
        elif isinstance(data, dict):
            if depth == 0:
                element = Element(name or 'response')
            else:
                element = Element(name or 'object')
                element.set('type', 'hash')
            for (key, value) in six.iteritems(data):
                element.append(self.to_etree(value, options, name=key, depth=depth+1))
        elif isinstance(data, Bundle):
            element = self.bundle_to_etree(data) # <--------------- this is the part that is changed from https://github.com/toastdriven/django-tastypie/blob/master/tastypie/serializers.py
        elif hasattr(data, 'dehydrated_type'):
            if getattr(data, 'dehydrated_type', None) == 'related' and data.is_m2m == False:
                if data.full:
                    return self.to_etree(data.fk_resource, options, name, depth+1)
                else:
                    return self.to_etree(data.value, options, name, depth+1)
            elif getattr(data, 'dehydrated_type', None) == 'related' and data.is_m2m == True:
                if data.full:
                    element = Element(name or 'objects')
                    for bundle in data.m2m_bundles:
                        element.append(self.to_etree(bundle, options, bundle.resource_name, depth+1))
                else:
                    element = Element(name or 'objects')
                    for value in data.value:
                        element.append(self.to_etree(value, options, name, depth=depth+1))
            else:
                return self.to_etree(data.value, options, name)
        else:
            element = Element(name or 'value')
            simple_data = self.to_simple(data, options)
            data_type = get_type_string(simple_data)

            if data_type != 'string':
                element.set('type', get_type_string(simple_data))

            if data_type != 'null':
                if isinstance(simple_data, six.text_type):
                    element.text = simple_data
                else:
                    element.text = force_text(simple_data)

        return element


class CustomXMLSerializer(Serializer):

    def to_etree(self, data, options=None, name=None, depth=0):
        if isinstance(name, six.string_types):
            soft_assert_type_text(name)
            # need to strip any whitespace from xml tag names
            name = name.strip()
        etree = super(CustomXMLSerializer, self).to_etree(data, options, name, depth)
        id = etree.find('id')
        if id is not None:
            etree.attrib['id'] = id.findtext('.')
            etree.remove(id)
        return etree


class XFormInstanceSerializer(Serializer):

    def to_xml(self, data, options=None):
        if isinstance(data, Bundle):
            return data.obj.get_xml()
        else:
            return super(XFormInstanceSerializer, self).to_xml(data, options=options)
