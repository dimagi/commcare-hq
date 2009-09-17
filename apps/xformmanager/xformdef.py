from xformmanager.util import *
from xformmanager.models import Metadata
from lxml import etree
import re
import logging

class ElementDef(object):
    """ Stores metadata about simple and complex types """
 
    def __init__(self, target_namespace='', is_repeatable=False):
        self.child_elements = []
        self.allowable_values = []
        self.name = target_namespace
        self.short_name = ''
        self.type = ''
        self.is_repeatable = is_repeatable
        #the xpath field is deprecated (unused)
        self.xpath = ''
        #self.attributes - not supported yet
      
    def isValid(): # to do: place restriction functions in here
        pass

    def addChild(self, element_def):
        self.child_elements.append(element_def)

    def __str__(self, depth=0, string='', ):
        indent = ' '*depth
        string = indent + "xpath=" + str(self.name) + "\n"
        string = string + indent + "name=" + str(self.name) + ", type=" + str(self.type) + ", repeatable=" + str(self.is_repeatable)  + "\n"
        for child in self.child_elements:
            string = string + child.__str__(depth+1, string)
        return string

class FormDef(ElementDef):
    """ Stores metadata about forms """

    def __init__(self, stream_pointer=None):
        self.types = {}
        if stream_pointer is not None:
            payload = get_xml_string(stream_pointer)
            self.parseString(payload)
          
    def __str__(self):
        string =  "DEFINITION OF " + str(self.name) + "\n"
        string = string + "TYPES: \n"
        for t in self.types:
            string = string + self.types[t].name + "\n" 
            for allowable_value in self.types[t].allowable_values:
                string = string + " allowable_value: " + allowable_value + "\n"                 
            for multiselect_value in self.types[t].multiselect_values:
                string = string + " multiselect_value: " + multiselect_value + "\n"                 
        string = string + "ELEMENTS: \n"
        return string + ElementDef.__str__(self)

    def parseString(self, string):
        root = etree.XML(string)

        target_namespace = root.get('targetNamespace')
        if not target_namespace:
            logging.error("Target namespace is not found in xsd schema")
        self.target_namespace = target_namespace
        ElementDef.__init__(self, target_namespace)

        self.xpath = ""
        self._addAttributesAndChildElements(self, root, '', '')
    
    @property
    def root_element(self):
        '''Get the root ElementDef for this form.  This will throw an
           exception if there is more than one root child defined.'''  
        if len(self.child_elements) != 1:
            raise Exception("Tried to get the single root from %s but found %s nodes"
                             % (self, len(self.child_elements)))
        return self.child_elements[0]
    
    def get_meta_element(self):
        '''Gets the meta element from the form, if it exists.
           Meta is defined as a top-level child of the form with
           the name "meta" (case insenitive).  If no meta block
           is found, this returns nothing''' 
        for child in self.root_element.child_elements:
            if child.short_name.lower() == "meta":
                return child
        
    @classmethod
    def get_meta_validation_issues(cls, element):
        '''Validates an ElementDef, assuming it is a meta block.  Ensures
           that every field we expect to find in the meta is there, and 
           that there are no extra fields.  Returns a dictionary of
           of any errors/warnings found in the following format:
           { "missing" : [list, of, missing, expected, fields]
             "duplicate" : [list, of, duplicate, fields]
             "extra" : [list, of, unexpected, fields]
           }
           If any of these lists are empty they won't be in the dictionary,
           and therefore if all are empty this method will return an empty
           dictionary.
        '''
        
        missing_fields = []
        extra_fields = []
        duplicate_fields = []
        found_fields = []
        missing_fields.extend(Metadata.fields)
        
        # hackily remove some stuff we no longer want to require
        missing_fields.remove('formname')
        missing_fields.remove('formversion')
        for field in element.child_elements:
            field_name = field.short_name.lower()
            if field_name in missing_fields:
                missing_fields.remove(field_name)
                found_fields.append(field_name)
            elif field_name in found_fields:
                # it was already found, therefore it must be 
                # a duplicate
                duplicate_fields.append(field_name)
            else:
                # it wasn't in the expected list, and wasn't a 
                # dupe, it must be an extra
                extra_fields.append(field_name)
        to_return = {}
        if missing_fields:
            to_return["missing"] = missing_fields
        if duplicate_fields:
            to_return["duplicate"] = duplicate_fields
        if extra_fields:
            to_return["extra"] = extra_fields
        return to_return

    def _addAttributesAndChildElements(self, element, input_tree, xpath, name_prefix):
        for input_node in etree.ElementChildIterator(input_tree):
            name = str(input_node.get('name'))
            if (str(input_node.tag)).find("element") > -1:
                next_name_prefix = ''
                if input_node.get('maxOccurs') > 1:
                    child_element = ElementDef(is_repeatable=True)
                    self._populateElementFields(child_element, input_node, element.xpath, name)
                else:
                    child_element = ElementDef()
                    #discard parent_name
                    next_name_prefix = join_if_exists( name_prefix, name )
                    full_name = next_name_prefix
                    self._populateElementFields(child_element, input_node, element.xpath, full_name)
                element.addChild(child_element)
                #theoretically, simpleType enumerations and list values can be defined inside of elements
                #in practice, this isn't how things are currently generated in the schema generator,
                #so we don't support that (yet)
                self._addAttributesAndChildElements(child_element, input_node, element.xpath, next_name_prefix )
            elif (str(input_node.tag)).find("simpleType") > -1:
                simpleType = SimpleType( str(input_node.get('name')) )
                child = input_node[0]
                if (str(child.tag)).find("restriction") > -1:
                    for enum in child:
                        if (str(enum.tag)).find("enumeration") > -1:
                            simpleType.allowable_values.append( sanitize(enum.get("value")) )
                elif (str(child.tag)).find("list") > -1:
                    multiselect_name = child.get("itemType")
                    if self.types[multiselect_name] is not None:
                        simpleType.multiselect_values = self.types[multiselect_name].allowable_values
                # add new type definition
                self.types[simpleType.name] = simpleType
            else:
                # Skip non-elements (e.g. <sequence>, <complex-type>
                self._addAttributesAndChildElements(element, input_node, element.xpath, name_prefix)
    
    def _populateElementFields(self, element, input_node, xpath, full_name):
        if not element.name: element.name = full_name
        element.type = input_node.get('type')
        if element.type is not None: element.type = element.type
        element.min_occurs = input_node.get('minOccurs')
        element.tag = input_node.tag
        name = input_node.get('name')
        element.short_name = name
        if xpath: element.xpath = xpath + "/x:" + name
        else: element.xpath = "x:" + name
        
class SimpleType(object):
    """ Stores type definition for simple types """
    def __init__(self, name=''):
        self.allowable_values = []
        self.multiselect_values = []
        self.name = name
