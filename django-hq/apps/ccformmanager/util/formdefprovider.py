# This is an interface; currently we do not inherit any functionality
class FormDefProvider:
  def setInput(self, stream_pointer):
      pass

  def getFormDef(self):
      pass



from lxml import etree
from formdef import *
import re


class FormDefProviderFromXSD(FormDefProvider):
 
  def __init__(self, stream_pointer):
      self.parseStream(stream_pointer)
      pass

  def setInput(self, stream_pointer):
      self.parseStream(stream_pointer)
      pass

  def getFormDef(self):
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
          child_element = ElementDef()
          element.addChild(child_element)          
          self.__addAttributesAndChildElements(child_element, input_node)
  
  def __populateElementFields(self, element, input_node):
      element.name = input_node.get('name')
      element.type = input_node.get('type')
      element.min_occurs = input_node.get('minOccurs')
      
