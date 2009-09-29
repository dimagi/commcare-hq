from xformmanager.util import *
from xformmanager.models import Metadata, MetaDataValidationError
from lxml import etree
import re
import logging

class ElementDef(object):
    """ Stores metadata about simple and complex types """
 
    def __init__(self, name='', is_repeatable=False):
        self.name = name
        self.xpath = ''
        self.child_elements = []
        self.allowable_values = []
        self.short_name = ''
        self.type = ''
        self.is_repeatable = is_repeatable
        #self.attributes - not supported yet
      
    def isValid(): # to do: place restriction functions in here
        pass

    def addChild(self, element_def):
        self.child_elements.append(element_def)

    def __str__(self, depth=0, string='', ):
        indent = ' '*depth
        string = indent + "xpath=" + str(self.xpath) + "\n"
        string = string + indent + "name=" + str(self.name) + ", type=" + str(self.type) + ", repeatable=" + str(self.is_repeatable)  + "\n"
        for child in self.child_elements:
            string = string + child.__str__(depth+1, string)
        return string

    def populateElementFields(self, input_node, xpath, full_name):
        if not self.name: self.name = full_name
        self.short_name = input_node.get('name')
        self.type = input_node.get('type')
        self.min_occurs = input_node.get('minOccurs')
        self.tag = input_node.tag
        if xpath: self.xpath = xpath + "/" + self.short_name
        else: self.xpath = self.short_name
        
class FormDef(ElementDef):
    """ Stores metadata about forms 
    When this code was written, I didn't realize XML requires having
    only one root element. Ergo, the root of this xml is accessed via
    FormDef.root (rather than just FormDef)
    """

    def __init__(self, input=None, child_element=None, **kwargs):
        """Either a stream pointer to an XML stream to populate this form
           or a child element to a valid element_def should be provided.
           If neither is, this is a pretty useless form"""
        # call the base class to initialize some more properties
        super(FormDef, self).__init__(**kwargs) 
        self.types = {}
        self.version = None
        self.uiversion = None
        self.target_namespace = ''
        if input is not None and child_element is not None:
            # log this, cause it's a bad idea
            logging.error("""Both XML and a child element explicitly passed to
                             create a new formdef.  The child element %s will be
                             ignored""" % child_element) 
        if input is not None:
            if isinstance(input,basestring):
                # 'input' is a filename
                fin = open(input,'r')
                payload = get_xml_string( fin )
                fin.close()
            else:
                # 'input' is an input stream
                payload = get_xml_string(input)
            self.parseString(payload)
        elif child_element is not None:
            self.child_elements = [child_element]
        if len(self.child_elements)>1:
            # fail hard on too many children, since it's bad xml
            raise Exception("Poorly formed XML. Multiple root elements!")
        if not self.child_elements:
            logging.error("You just created a formdef %s with no children.  Why?!" % self)
        else:
            # safe to set a root node here
            self.root = self.child_elements[0]
          
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
        """ populates formdef with data from xml string
        
        Note that we currently allow 'bad form' xforms 
        (e.g. bad metadata, bad version numbers)
        Such errors can be caught/reported using FormDef.validate()
        """
        root = etree.XML(string)

        # there must be a better way of finding case-insensitive version
        self.version = case_insensitive_attribute(root, "version")
        
        # there must be a better way of finding case-insensitive version
        self.uiversion = case_insensitive_attribute(root, "uiversion")

        self.target_namespace = case_insensitive_attribute(root, 'targetNamespace')
        if not self.target_namespace:
            logging.error("Target namespace is not found in xsd schema")
        ElementDef.__init__(self, self.target_namespace)

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
                    child_element.populateElementFields(input_node, element.xpath, name)
                else:
                    child_element = ElementDef()
                    #discard parent_name
                    next_name_prefix = join_if_exists( name_prefix, name )
                    full_name = next_name_prefix
                    child_element.populateElementFields(input_node, element.xpath, full_name)
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

    def validate(self):
        # check xmlns not none
        if not self.target_namespace:
            raise FormDef.FormDefError("No namespace found in submitted form: %s" % self.target_namespace)

        # all the forms in use today have a superset namespace they default to
        # something like: http://www.w3.org/2002/xforms
        if self.target_namespace.lower().find('www.w3.org') != -1:
            raise FormDef.FormDefError("No namespace found in submitted form: %s" % self.target_namespace)
        
        if self.version:
            if not self.version.strip().isdigit():
                # should make this into a custom exception
                raise FormDef.FormDefError("Version attribute must be an integer in xform %s" % self.target_namespace)

        meta_element = self.get_meta_element()
        if not meta_element:
            raise FormDef.FormDefError("From %s had no meta block!" % self.target_namespace)
        
        meta_issues = FormDef.get_meta_validation_issues(meta_element)
        if meta_issues:
            mve = MetaDataValidationError(meta_issues, self.target_namespace)
            # until we have a clear understanding of how meta versions will work,
            # don't fail on issues that only come back with "extra" set.  i.e.
            # look for missing or duplicate
            if mve.duplicate or mve.missing:
                raise mve
            else:
                logging.warning("Found extra meta fields in xform %s: %s" % 
                                (self.target_namespace, mve.extra))
        # validated! 
        return True
    
    def force_to_valid(self):
        if self.version and self.version.strip().isdigit():
            self.version = self.version.strip()
        else:
            self.version = None
        if self.uiversion and self.uiversion.strip().isdigit():
            self.uiversion = self.uiversion.strip()
        else:
            self.uiversion = None

    def is_compatible_with(self, otherdef):
        return self.get_differences(otherdef).is_empty()

    def get_differences(self, otherdef):
        # TODO - put comparison logic here. populate d.
        # if differences exist:
        #     d = Differences()
        #     return d
        # else
        return Differences()
        
    class FormDefError(Exception):
        """ Error from FormDef Processing """

class SimpleType(object):
    """ Stores type definition for simple types """
    def __init__(self, name=''):
        self.allowable_values = []
        self.multiselect_values = []
        self.name = name

class Differences(object):
    """ Data structure to represent the differences between this and another formdef """
    def __init__(self):
        self.otherdef = None
        self.fields_added = []
        self.fields_removed = []
        self.fields_changed = []
        
    def is_empty(self):
        '''Return whether this is meaningfully empty (i.e. representing 
           no differences'''
        return not (self.fields_added or self.fields_changed or self.fields_removed)
