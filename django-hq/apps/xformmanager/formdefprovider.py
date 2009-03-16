# This is an interface; currently we do not inherit any functionality
class FormDefProvider:
  def set_input(self, stream_pointer):
      pass

  def get_formdef(self):
      pass



from lxml import etree
from xformmanager.formdef import *
import re


class FormDefProviderFromXSD(FormDefProvider):
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

      r = re.search('{[a-zA-Z0-9\.\/\:]*}', self.tree.getroot().tag)
      xmlns = r.group(0).strip('{').strip('}')
      self.formDef = FormDef(xmlns) # add date, time, etc. to creation later

      self.__addAttributesAndChildElements(self.formDef, self.tree.getroot())
      return self.formDef
    
  def __addAttributesAndChildElements(self, element, input_tree):
      self.__populateElementFields(element, input_tree)
      for input_node in etree.ElementChildIterator(input_tree):
          if input_node.tag.find("element") > -1 and (input_node.get('name').find('root') == -1 ):
            child_element = ElementDef()
            element.addChild(child_element)     
            self.__addAttributesAndChildElements(child_element, input_node)
          else:
            self.__addAttributesAndChildElements(element, input_node)            
          #for other types of input nodes, pass in different parameters
          #or add another level to the tree
  
  def __populateElementFields(self, element, input_node):
      if not element.name: element.name = input_node.get('name')
      element.type = input_node.get('type')
      element.min_occurs = input_node.get('minOccurs')
      element.tag = input_node.tag
      
