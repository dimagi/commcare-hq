from xformmanager.util import *
from lxml import etree
import re
import logging

class ElementDef(object):
    """ Stores metadata about simple and complex types """
 
    def __init__(self, target_namespace='', is_repeatable=False):
        self.child_elements = []
        self.allowable_values = []
        self.name = target_namespace
        self.type = ''
        self.is_repeatable = is_repeatable
        self.xpath = ''
        #self.attributes - not supported yet
      
    def isValid(): # to do: place restriction functions in here
        pass

    def addChild(self, element_def):
        self.child_elements.append(element_def)

    def tostring(self, depth=0, string='', ):
        indent = ' '*depth
        string = indent + "xpath=" + str(self.name) + "\n"
        string = string + indent + "name=" + str(self.name) + ", type=" + str(self.type) + ", repeatable=" + str(self.is_repeatable)  + "\n"
        for child in self.child_elements:
            string = string + child.tostring(depth+1, string)
        return string

class FormDef(ElementDef):
    """ Stores metadata about forms """

    def __init__(self, stream_pointer=None):
        if stream_pointer is not None:
            skip_junk(stream_pointer)
            self.parseStream(stream_pointer)
          
    def __str__(self):
        return str(self.name) + '\n' + ElementDef.tostring(self)

    def parseStream(self, stream_pointer):
        tree = etree.parse(stream_pointer)

        root = tree.getroot()
        target_namespace = root.get('targetNamespace')
        if target_namespace is None:
            logging.error("Target namespace is not found in xsd schema")
        self.target_namespace = target_namespace
        ElementDef.__init__(self, target_namespace)

        self.xpath = ""
        self.__addAttributesAndChildElements(self, root, '')
      
    def __addAttributesAndChildElements(self, element, input_tree, xpath):
        for input_node in etree.ElementChildIterator(input_tree):
            if (str(input_node.tag)).find("element") > -1 and ( (str(input_node.get('name'))).find('root') == -1 ):
                if input_node.get('maxOccurs') > 1: 
                    child_element = ElementDef(is_repeatable=True)
                else:
                    child_element = ElementDef()
                element.addChild(child_element)     
                self.__populateElementFields(child_element, input_node, element.xpath)
                self.__addAttributesAndChildElements(child_element, input_node, element.xpath)
            else:
                # Skip non-elements (e.g. <sequence>, <complex-type>
                self.__addAttributesAndChildElements(element, input_node, element.xpath)
    
    def __populateElementFields(self, element, input_node, xpath):
        if not element.name: element.name = input_node.get('name')
        element.type = input_node.get('type')
        if element.type is not None: element.type = element.type.lower()
        element.min_occurs = input_node.get('minOccurs')
        element.tag = input_node.tag
        if xpath: element.xpath = xpath + "/x:" + element.name
        else: element.xpath = "x:" + element.name
        