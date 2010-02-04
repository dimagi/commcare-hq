import unittest

import xformmanager.xmlrouter as xmlrouter

counter = 0
attachment = "dummy_attach"
inc_xmlns = "test_xmlns_inc"
dec_xmlns = "test_xmlns_dec"
unused_xmlns = "unused_xmlns"

def noop(attachment):
    pass

def increment(attachment):
    global counter
    counter += 1

def increment_again(attachment):
    global counter
    counter += 1

def decrement(attachment):
    global counter
    counter -= 1

class XmlRoutingTestCase(unittest.TestCase):
    """This class tests the xmlrouter functionality."""
       
    def setUp(self):
        global counter
        counter = 0
        xmlrouter.reset()
                
    def tearDown(self):
        pass

    def testRegistry(self):
        """Tests the registration functionality."""
        # not registered at first
        self.assertFalse(xmlrouter.is_registered(inc_xmlns, increment))
        xmlrouter.register(inc_xmlns, increment)
        # now it is
        self.assertTrue(xmlrouter.is_registered(inc_xmlns, increment))
        # but not with other namespaces 
        self.assertFalse(xmlrouter.is_registered(dec_xmlns, increment))
        # or other methods
        self.assertFalse(xmlrouter.is_registered(inc_xmlns, noop))
        # unless it is registered
        xmlrouter.register(inc_xmlns, noop)
        # in which case both should work
        self.assertTrue(xmlrouter.is_registered(inc_xmlns, increment))
        self.assertTrue(xmlrouter.is_registered(inc_xmlns, noop))
        # but others still shouldn't
        self.assertFalse(xmlrouter.is_registered(inc_xmlns, decrement))
        
    def testRouting(self):
        """Tests the creation of a form group from a single form."""
        # nothing registered.  assure that nothing happens
        self.assertEqual(0, counter)
        xmlrouter.process(attachment, inc_xmlns, 0)
        self.assertEqual(0, counter)
        xmlrouter.process(attachment, dec_xmlns, 0)
        self.assertEqual(0, counter)
        xmlrouter.process(attachment, unused_xmlns, 0)
        self.assertEqual(0, counter)
        
        # register the incrementer and the decrementer
        xmlrouter.register(inc_xmlns, increment)
        xmlrouter.register(dec_xmlns, decrement)
        
        # make sure we are incrementing correctly
        xmlrouter.process(attachment, inc_xmlns, 0)
        self.assertEqual(1, counter)
        xmlrouter.process(attachment, inc_xmlns, 0)
        self.assertEqual(2, counter)
        
        # and decrementing correctly
        xmlrouter.process(attachment, dec_xmlns, 0)
        self.assertEqual(1, counter)
        
        # and ignoring what should be ignored
        xmlrouter.process(attachment, unused_xmlns, 0)
        self.assertEqual(1, counter)
        
        # reregistering should not "double up"
        xmlrouter.register(inc_xmlns, increment)
        xmlrouter.register(inc_xmlns, increment)
        xmlrouter.register(inc_xmlns, increment)
        xmlrouter.register(dec_xmlns, decrement)
        xmlrouter.process(attachment, inc_xmlns, 0)
        self.assertEqual(2, counter)
        xmlrouter.process(attachment, dec_xmlns, 0)
        self.assertEqual(1, counter)
        
        # but registering with a second method should 
        xmlrouter.register(inc_xmlns, increment_again)
        xmlrouter.process(attachment, inc_xmlns, 0)
        self.assertEqual(3, counter)
        xmlrouter.process(attachment, inc_xmlns, 0)
        self.assertEqual(5, counter)
        xmlrouter.process(attachment, dec_xmlns, 0)
        self.assertEqual(4, counter)
        
        
        
        
        