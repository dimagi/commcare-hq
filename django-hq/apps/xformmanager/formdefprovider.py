# This is an interface; currently we do not inherit any functionality
class FormDefProvider(object):
    """ This is a generic interface for things that provide information about form defintions.
    
    For now we read from xsd files. In the future we could read from xforms, xml, databases, etc.
    
    """
    
    def set_input(self, stream_pointer):
        pass

    def get_formdef(self):
        pass



from lxml import etree
from xformmanager.formdef import *
import re


class FormDefProviderFromXSD(FormDefProvider):
    """ This FormDefProvider translates xsd streams into form definitions"""
    
    def __init__(self, stream_pointer=None):
        if stream_pointer is not None:
            self.parseStream(stream_pointer)          
        pass

    def set_input(self, stream_pointer):
        self.parseStream(stream_pointer)
        pass

    def get_formdef(self):
        #if(self.formDef == empty) report an error
        return self.formDef
    
    def parseStream(self, stream_pointer):
        #if( stream_pointer == null ) throw exception, if parent is None: 
        self.tree = etree.parse(stream_pointer)

        root = self.tree.getroot()
        r = re.search('{[a-zA-Z0-9\.\/\:]*}', root.tag)
        xmlns = r.group(0).strip('{').strip('}')
        self.formDef = FormDef(xmlns) # add date, time, etc. to creation later

        #self.__populateElementFields(self.formDef, root, '')
        self.formDef.xpath = ""
        self.__addAttributesAndChildElements(self.formDef, root, '')
        return self.formDef
      
    def __addAttributesAndChildElements(self, element, input_tree, xpath):
        #self.__populateElementFields(element, input_tree, xpath)
        for input_node in etree.ElementChildIterator(input_tree):
            if input_node.tag.find("element") > -1 and (input_node.get('name').find('root') == -1 ):
                if input_node.get('maxOccurs') > 1: 
                    child_element = ElementDef(is_repeatable=True)
                else:
                    child_element = ElementDef()
                element.addChild(child_element)     
                self.__populateElementFields(child_element, input_node, element.xpath)
                self.__addAttributesAndChildElements(child_element, input_node, element.xpath)
            else:
                # Non-element
                self.__addAttributesAndChildElements(element, input_node, element.xpath)
                #for other types of input nodes, pass in different parameters
                #or add another level to the tree
    
    def __populateElementFields(self, element, input_node, xpath):
        if not element.name: element.name = input_node.get('name')
        element.type = input_node.get('type')
        element.min_occurs = input_node.get('minOccurs')
        element.tag = input_node.tag
        if xpath: element.xpath = xpath + "/x:" + element.name
        else: element.xpath = "x:" + element.name
        
        
