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
        version_changing_attrs = [ "xpath", "name", "type"]
        nonversion_changing_attrs = [ "target_namespace", "version", "uiversion", "tag" ]
        for attr in version_changing_attrs:
            fcopy = copy.deepcopy(filled)
            # we use an string in case there are parsing exceptions
            # we may need to special case this better
            setattr(fcopy, attr, "99")
            self._do_two_way_compatibility_check(filled, fcopy, False)
        
        for attr in nonversion_changing_attrs:
            fcopy = copy.deepcopy(filled)
            # ditto above.
            setattr(fcopy, attr, "99")
            self._do_two_way_compatibility_check(filled, fcopy, True)
                    
    def testChildAttributes(self):
        child = self._get_basic_elementdef()
        ccopy = copy.deepcopy(child)
        filled = self._get_basic_formdef(child_elements = [child])
        fcopy = copy.deepcopy(filled)
        fcopy.child_elements = [ccopy]
        self._do_two_way_compatibility_check(filled, fcopy, True)
        self._do_child_attribute_check(filled, fcopy, ccopy)
    
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
        # do not check duplicates, since valid xsd schema will not have duplicates
        # fcopy.child_elements = [child1, child2, child1]
        # self._do_two_way_compatibility_check(filled, fcopy, False)
        # make sure it was the inconsistent child elements that were failing
        fcopy.child_elements = [child1, child2]
        self._do_two_way_compatibility_check(filled, fcopy, True)
        
    def testSubChildren(self):
        child1 = self._get_basic_elementdef(name="name1", xpath="xpath1")
        subchild1 = self._get_basic_elementdef(name="subname1", xpath="subpath1")
        subchild2 = self._get_basic_elementdef(name="subname2", xpath="subpath2")
        child1.child_elements=[subchild1, subchild2]
        child2 = self._get_basic_elementdef(name="name2", xpath="xpath2")
        subchild3 = self._get_basic_elementdef(name="subname3", xpath="subpath3")
        subchild4 = self._get_basic_elementdef(name="subname4", xpath="subpath4")
        child2.child_elements = [subchild3, subchild4]
        c1copy = copy.deepcopy(child1)
        c2copy = copy.deepcopy(child2)
        filled = self._get_basic_formdef(child_elements=[child1, child2])
        fcopy = copy.deepcopy(filled)
        # all is the same, should pass
        self._do_two_way_compatibility_check(filled, fcopy, True)
        # run through the standard compatibility checks on all children, 
        # all subchildren
        for child in [child1, child2, subchild1, subchild2, subchild3, subchild4]:
             self._do_child_attribute_check(filled, fcopy, child)
        
        # test ordering of super children, and then of sub children
        fcopy.child_elements = [c2copy, c1copy] 
        self._do_two_way_compatibility_check(filled, fcopy, True)
        # ordering should pass
        c1copy.child_elements = [subchild2, subchild1]
        self._do_two_way_compatibility_check(filled, fcopy, True)
        # removal should not
        c1copy.child_elements = [subchild1]
        self._do_two_way_compatibility_check(filled, fcopy, False)
        
        # additions should not
        c1copy.child_elements = [subchild2, subchild1, subchild3]
        self._do_two_way_compatibility_check(filled, fcopy, False)
        #Forget about duplicates
        #c1copy.child_elements = [subchild2, subchild1, subchild1]
        #self._do_two_way_compatibility_check(filled, fcopy, False)
        # swapping should not
        c1copy.child_elements = [subchild1, subchild3]
        self._do_two_way_compatibility_check(filled, fcopy, False)
        # moving children to different elements should not
        c2copy.child_elements = [subchild2, subchild4]
        self._do_two_way_compatibility_check(filled, fcopy, False)
        
        # finally run through basic tests with a subsubchild
        # let's get our copies back in our expected state:
        c1copy.child_elements = [subchild1, subchild2]
        c2copy.child_elements = [subchild3, subchild4]
        self._do_two_way_compatibility_check(filled, fcopy, True)
        subsubchild = self._get_basic_elementdef(name="subsubname1", xpath="subsubpath1")
        subchild1.child_elements = [subsubchild]
        
        # fcopy actually points to subchild1. so we need to make a new copy.
        subchild1_copy = copy.deepcopy(subchild1)
        subsubchild_copy = copy.deepcopy(subsubchild)
        subchild1_copy.child_elements = [subsubchild_copy]
        c1copy.child_elements = [subchild1_copy, subchild2]
        self._do_child_attribute_check(filled, fcopy, subsubchild)
                 
    def _do_child_attribute_check(self, filled, fcopy, ccopy):
        """Checks all the version attributes of an element against a form.
           Any version changing attribute should result in a compatibility
           error, while any non-version changing attribute should not.
           Assumes the element passed in is referenced inside one of the forms,
           but it could be arbitrarily nested"""
        
        # todo: verify/modify these lists
        version_changing_attrs = ["xpath", "name", "type", "is_repeatable" ]
        nonversion_changing_attrs = ["tag"]
        for attr in version_changing_attrs:
            prev_val = getattr(ccopy, attr)
            # same caveat as above applies
            setattr(ccopy, attr, "99")
            self._do_two_way_compatibility_check(filled, fcopy, False)
            # make sure to set it back after we check
            setattr(ccopy, attr, prev_val)
            
        for attr in nonversion_changing_attrs:
            prev_val = getattr(ccopy, attr)
            # same caveat as above applies
            setattr(ccopy, attr, "99")
            self._do_two_way_compatibility_check(filled, fcopy, True)
            # make sure to set it back after we check
            setattr(ccopy, attr, prev_val)
            
    
    def _get_basic_elementdef(self, name="a name", xpath = "xpath", 
                              child_elements=[], allowable_values=[],
                              type="type", is_repeatable=False,
                              min_occurs=0, tag="tag"):
        """Make an elementdef, with as many or as few custom parameters as you want""" 
        to_return = ElementDef()
        to_return.name = name
        to_return.xpath = xpath
        to_return.child_elements = child_elements
        to_return.allowable_values = allowable_values
        to_return.type = type
        to_return.is_repeatable = is_repeatable
        to_return.min_occurs = min_occurs
        to_return.tag = tag
        return to_return

    
    def _get_basic_formdef(self, name="a name", xpath = "xpath", 
                           child_elements=[], allowable_values=[],
                           type="type", is_repeatable=False, types={},
                           version=1, uiversion=1, 
                           target_namespace="uri://my_xmlns"):
        """Make a formdef, with as many or as few custom parameters as you want""" 
        to_return = FormDef()
        to_return.name = name
        to_return.xpath = xpath
        to_return.child_elements = child_elements
        to_return.allowable_values = allowable_values
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
        
        