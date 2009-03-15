
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

  def __init__(self):
      self.children = []
      self.allowable_values = []
    
  def isValid(): #boolean
      pass

  def addChild(self, element_def):
      self.children.append(element_def)

  def tostring(self, depth=0, string='', ):
      indent = ' '*depth
      string = indent + "name=" + str(self.name) + ", type=" + str(self.type) + "\n"
      for child in self.children:
          string = string + child.tostring(depth+1, string)
      return string

class FormDef(ElementDef):
  """ Stores metadata about forms """
  xmlns = ''
  
  def __init__(self, xmlns):
    self.xmlns = xmlns
    ElementDef.__init__(self)

  #date_created
  #group_id
        
  def tostring(self):
      return self.xmlns + '\n' + ElementDef.tostring(self)

  #def __init__(self):
  #    ElementDef.__init__(self)


