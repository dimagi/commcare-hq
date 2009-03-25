from lxml import etree
import re

class ElementDef(object):
    """ Stores metadata about simple and complex types """
    #name = "name"
    #type = "type" #enum of int/float/etc.
    #minoccurs = ''
    #children = [] #type ElementDef
 
    """ minOccurs
    attributes #type ElementDef
    allowable_values #user-defined values
    repeatable #boolean
    restriction #string - should be private? 
    """

    def __init__(self, name='', is_repeatable=False):
        self.child_elements = []
        self.allowable_values = []
        self.name = name
        self.type = ''
        self.is_repeatable = is_repeatable
        self.xpath = ''
      
    def isValid(): #boolean
        pass

    def addChild(self, element_def):
        self.child_elements.append(element_def)

    def tostring(self, depth=0, string='', ):
        indent = ' '*depth
        string = indent + "xpath=" + str(self.xpath) + "\n"
        string = string + indent + "name=" + str(self.name) + ", type=" + str(self.type) + ", repeatable=" + str(self.is_repeatable)  + "\n"
        for child in self.child_elements:
            string = string + child.tostring(depth+1, string)
        return string

class FormDef(ElementDef):
    """ Stores metadata about forms """

    def __init__(self, stream_pointer=None):
        if stream_pointer is not None:
            self.parseStream(stream_pointer)
    

    #date_created
    #group_id
          
    def __str__(self):
        return str(self.name) + '\n' + ElementDef.tostring(self)

    #def __init__(self):
    #    ElementDef.__init__(self)


    def parseStream(self, stream_pointer):
        #if( stream_pointer == null ) throw exception, if parent is None: 
        tree = etree.parse(stream_pointer)

        root = tree.getroot()
        target_namespace = root.get('targetNamespace')
        self.target_namespace = target_namespace
        ElementDef.__init__(self, target_namespace)

        #self.__populateElementFields(self.formDef, root, '')
        self.xpath = ""
        self.__addAttributesAndChildElements(self, root, '')
      
    def __addAttributesAndChildElements(self, element, input_tree, xpath):
        #self.__populateElementFields(element, input_tree, xpath)
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
        