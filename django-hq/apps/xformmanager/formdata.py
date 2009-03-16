from lxml import etree

class ElementData():
    def __init__(self, stream_pointer):
        self.tree = etree.parse(stream_pointer)

    def child_iterator(self):
        return etree.ElementChildIterator(self.tree.getroot())
    
    def next(self):
        return self.iter.next()
    
    def getroot(self):
        return self.tree.getroot()

class FormData(ElementData):
    pass

