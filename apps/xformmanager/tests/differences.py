import unittest
import copy
from xformmanager.xformdef import FormDef, ElementDef, Differences


class CompatibilityTestCase(unittest.TestCase):
    
    def testEmptyWithEmpty(self):
        self._do_two_way_compatibility_check(FormDef(), FormDef(), True)
        
    def testEmptyWithFilled(self):
        filled = self._get_basic_formdef()
        self._do_two_way_compatibility_check(filled, FormDef(), False)
        
    def testBasicFilledTwoWay(self):
        filled = self._get_basic_formdef()
        self._do_two_way_compatibility_check(filled, copy.deepcopy(filled), True)

    def testBasicAttributes(self):
        filled = self._get_basic_formdef()
        # todo: verify/modify these lists
        version_changing_attrs = ["xpath", "version", "xmlns"]
        nonversion_changing_attrs = [ "name", "short_name", "uiversion"]
        for attr in version_changing_attrs:
            fcopy = copy.deepcopy(filled)
            # we use an int in case there are parsing exceptions
            # we may need to special case this better
            setattr(fcopy, attr, 99)
            self._do_two_way_compatibility_check(filled, fcopy, False)
        
        for attr in nonversion_changing_attrs:
            fcopy = copy.deepcopy(filled)
            # ditto above.
            setattr(fcopy, attr, 99)
            self._do_two_way_compatibility_check(filled, fcopy, True)
        
    
    def testChildAttributes(self):
        child = self._get_basic_elementdef()
        filled = self._get_basic_formdef(child_elements = [child])
        # todo: verify/modify these lists
        version_changing_attrs = ["xpath", "type", "name"]
        nonversion_changing_attrs = [ "short_name", "min_occurs", "tag"]
        for attr in version_changing_attrs:
            fcopy = copy.deepcopy(filled)
            ccopy = copy.deepcopy(child)
            # same caveat as above applies
            setattr(ccopy, attr, 99)
            fcopy.child_elements = [ccopy]
            self._do_two_way_compatibility_check(filled, fcopy, False)
        
        for attr in nonversion_changing_attrs:
            fcopy = copy.deepcopy(filled)
            ccopy = copy.deepcopy(child)
            # same caveat as above applies
            setattr(ccopy, attr, 99)
            fcopy.child_elements = [ccopy]
            self._do_two_way_compatibility_check(filled, fcopy, True)
    
    def testChildOrdering(self):
        child1 = self._get_basic_elementdef(name="name1", xpath="xpath1")
        child2 = self._get_basic_elementdef(name="name2", xpath="xpath2")
        filled = self._get_basic_formdef(child_elements=[child1, child2])
        # first make sure this checks out fine with multiple children
        fcopy = copy.deepcopy(filled)
        self._do_two_way_compatibility_check(filled, fcopy, True)
        # now reorder the children, it should still pass
        fcopy.child_elements = [child2, child1]
        self._do_two_way_compatibility_check(filled, fcopy, True)
        
    def testChildAdditions(self):
        child1 = self._get_basic_elementdef(name="name1", xpath="xpath1")
        child2 = self._get_basic_elementdef(name="name2", xpath="xpath2")
        child3 = self._get_basic_elementdef(name="name3", xpath="xpath3")
        filled = self._get_basic_formdef(child_elements=[child1, child2])
        # first make sure this checks out fine with multiple children
        fcopy = copy.deepcopy(filled)
        fcopy.child_elements = [child1]
        self._do_two_way_compatibility_check(filled, fcopy, False)
        fcopy.child_elements = [child1, child2, child3]
        self._do_two_way_compatibility_check(filled, fcopy, False)
        # make sure it was the inconsistent child elements that were failing
        fcopy.child_elements = [child1, child2]
        self._do_two_way_compatibility_check(filled, fcopy, True)
        
         
    
    def _get_basic_elementdef(self, name="a name", xpath = "xpath", 
                              child_elements=[], allowable_values=[],
                              short_name="short name", type="type",
                              is_repeatable=False, min_occurs=0,
                              tag="tag"):
        """Make a formdef, with as many or as few custom parameters as you want""" 
        to_return = ElementDef()
        to_return.name = name
        to_return.xpath = xpath
        to_return.child_elements = child_elements
        to_return.allowable_values = allowable_values
        to_return.short_name = short_name
        to_return.type = type
        to_return.is_repeatable = is_repeatable
        to_return.min_occurs = min_occurs
        to_return.tag = tag
        return to_return

    
    def _get_basic_formdef(self, name="a name", xpath = "xpath", 
                           child_elements=[], allowable_values=[],
                           short_name="short name", type="type",
                           is_repeatable=False, types={},
                           version=1, uiversion=1, 
                           target_namespace="uri://my_xmlns"):
        """Make a formdef, with as many or as few custom parameters as you want""" 
        to_return = FormDef()
        to_return.name = name
        to_return.xpath = xpath
        to_return.child_elements = child_elements
        to_return.allowable_values = allowable_values
        to_return.short_name = short_name
        to_return.type = type
        to_return.is_repeatable = is_repeatable
        to_return.types = types
        to_return.version = version
        to_return.uiversion = uiversion
        to_return.target_namespace = target_namespace
        return to_return
    
    def _do_two_way_compatibility_check(self, fd1, fd2, are_compatible):
        # all compatibility checks should be two-way, this is a symmetric
        # operation.
        should_they = "should" if are_compatible else "should NOT"
        self.assertEqual(are_compatible, fd1.is_compatible_with(fd2), 
                         "%s and %s %s be compatible" % (fd1, fd2, should_they))
        self.assertEqual(are_compatible, fd2.is_compatible_with(fd1), 
                         "%s and %s %s be compatible" % (fd2, fd1, should_they))
        
        