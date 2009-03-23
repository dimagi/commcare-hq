from lxml import etree
import logging

class ElementData(object):
    """ This class holds xml instance data.
    
    It is basically a wrapper for lxml.etree. 
    
    """    
    
    def __init__(self, stream_pointer):
        logging.debug("ElementData: create form data object")
        #put in checking to make sure this returns properly even when inputting bad data
        self.tree = etree.parse(stream_pointer)
        self.element = self.tree.getroot()

    def child_iterator(self):
        return ElementDataIterator( self.element, etree.ElementChildIterator(self.element) )
    
    def find(self, xpath):
        return self.element.find(xpath)
    
    def find_all(self, xpath):
        return self.element.find_all(xpath)
    
    def xpath(self, location, namespaces):
        return (self.tree).xpath(location, namespaces=namespaces)
    
    def next(self):
        self.element = self.iter.next()
        return self.element
    
    def getroot(self):
        return self.element
    
class FormData(ElementData):
    """ This class holds xml instance data."""
    pass

class ElementDataIterator(object):
    """ This is an iterator for children of ElementData"""
    
    def __init__(self, element, iter):
        self.element = element
        self.iter = iter
        
    def next(self):
        self.element = self.iter.next()
        return self.element
    
    def __iter__(self):
        return self
    
    def get_child_iterator(self):
        return ElementDataIterator( self.element, etree.ElementChildIterator( self.element  ) )        
