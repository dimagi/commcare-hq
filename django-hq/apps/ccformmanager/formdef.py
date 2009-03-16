
class ElementDef():
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

  def __init__(self, name=''):
      self.child_elements = []
      self.allowable_values = []
      self.name = name
      self.type = ''
      self.min_occurs = ''
    
  def isValid(): #boolean
      pass

  def addChild(self, element_def):
      self.child_elements.append(element_def)

  def tostring(self, depth=0, string='', ):
      indent = ' '*depth
      string = indent + "name=" + str(self.name) + ", type=" + str(self.type) + "\n"
      for child in self.child_elements:
          string = string + child.tostring(depth+1, string)
      return string

class FormDef(ElementDef):
  """ Stores metadata about forms """
  
  def __init__(self, xmlns):
    self.xmlns = xmlns
    ElementDef.__init__(self, xmlns)

  #date_created
  #group_id
        
  def tostring(self):
      return str(self.name) + ":" + str(self.xmlns) + '\n' + ElementDef.tostring(self)

  #def __init__(self):
  #    ElementDef.__init__(self)


