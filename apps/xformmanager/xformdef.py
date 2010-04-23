from xformmanager.util import *
# unfortunately, have to do something like this because of semi-circular dependencies
import xformmanager as xfm
from lxml import etree
import logging

XPATH_SEPARATOR = "/"

class ElementDef(object):
    """ Stores metadata about simple and complex types """
 
    def __init__(self, name='', is_repeatable=False, domain=None):
        self.name = name
        self.xpath = ''
        if domain and not self.getattr("domain", None):
            self.domain=domain
        self.child_elements = []
        self.type = ''
        self.is_repeatable = is_repeatable
        #self.attributes - not supported yet
        # this var is a device for getting diffs between defs
        self._visited = False
      
    def __unicode__(self):
        return unicode(self.xpath)
        
    def __str__(self):
        return unicode(self).encode('utf-8')
    
    @property
    def short_name(self):
        """ This is the unqualified tag of the element
            (without qualifying namespace or xpath) """
        c = unicode(self.xpath).rsplit(XPATH_SEPARATOR, 1)
        if len(c)==2:
            return c[1]
        return c[0]
    
    def to_str(self, depth=0, string=''):
        """ Dumps the entire contents of this to a string """
        indent = ' '*depth
        string = indent + "xpath=" + str(self.xpath) + "\n"
        string = string + indent + \
                 "name=" + str(self.name) + \
                 ", type=" + str(self.type) + \
                 ", repeatable=" + str(self.is_repeatable)  + "\n"
        for child in self.child_elements:
            string = string + child.to_str(depth+1, string)
        return string

    def isValid(self): 
        # TODO: place restriction functions in here
        pass

    def addChild(self, element_def):
        self.child_elements.append(element_def)

    def populateElementFields(self, input_node, xpath, full_name):
        if not self.name: self.name = full_name
        self.type = input_node.get('type')
        if xpath: 
            self.xpath = xpath + XPATH_SEPARATOR + input_node.get('name')
        else: 
            self.xpath = input_node.get('name')
    
    def find_child(self, child):
        """ Looks for child among child_elements of self.
        Equivalence is currently based on short_name. """
        for candidate in self.child_elements:
            if candidate.short_name == child.short_name:
                return candidate
        return None
    
    def _clear_visited(self):
        """ _visited is a device for getting diffs between defs """
        for child in self.child_elements:
            child._visited = False
            child._clear_visited()

    def _get_unvisited(self, root=None):
        """ _visited is a device for getting diffs between defs """
        d = []
        if root is None:
            # hm, I guess you can't pass 'self' as a default argument...
            root = self
        for child in root.child_elements:
            if not child._visited:
                d.append( child )
            d = d + self._get_unvisited(child)
        return d

    def _get_elementdef_diff(self, otherdef):
        """ Determines whether two elementdef leaves are equivalent
        (but does not check for children equivalency) We can always 
        extend this later to provide richer diff information """
        d = Differences()
        if self.name != otherdef.name or \
           self.xpath != otherdef.xpath or \
           self.type != otherdef.type or \
           self.is_repeatable != otherdef.is_repeatable:
               d.fields_changed.append( otherdef )
        otherdef._visited = True
        return d
    
    def _get_children_diff(self, otherdef):
        d = Differences()
        for child in self.child_elements:
            # find matching child in otherdef
            # assumption: the schemas provided are well-formed
            # and do not contain duplicate children
            otherchild = otherdef.find_child( child )
            if not otherchild:
                d.fields_removed.append(child)
            else:
                d = d + child._get_elementdef_diff(otherchild)
                d = d + child._get_children_diff(otherchild)
        return d
    
class FormDef(ElementDef):
    """Stores metadata about forms""" 
    
    # When this code was written, I didn't realize XML requires having
    # only one root element. Ergo, the root of this xml is accessed via
    # FormDef.root (rather than just FormDef)
    
    def __init__(self, input_stream=None, child_element=None, domain=None,
                 **kwargs):
        """Either a stream pointer to an XML stream to populate this form
           or a child element to a valid element_def should be provided.
           If neither is, this is a pretty useless form"""
        # call the base class to initialize some more properties
        super(FormDef, self).__init__(**kwargs) 
        # set some high level concepts
        self.types = {}
        self.version = None
        self.uiversion = None
        self.target_namespace = ''
        if input_stream is not None and child_element is not None:
            # log this, cause it's a bad idea
            logging.error("""Both XML and a child element explicitly passed to
                             create a new formdef.  The child element %s will be
                             ignored""" % child_element) 
        if input_stream is not None:
            # populate all of the child elements 
            payload = get_xml_string(input_stream)
            self.populateFromXmlString(payload)
        elif child_element is not None:
            self.child_elements = [child_element]
        if len(self.child_elements)>1:
            # fail hard on too many children, since it's bad xml
            raise Exception("Poorly formed XML. Multiple root elements!")
        if not self.child_elements:
            logging.info("You just created a formdef %s with no children.  Why?!" % self)
            #logging.error("You just created a formdef %s with no children.  Why?!" % self)
        else:
            # safe to set a root node here
            self.root = self.child_elements[0]
            
        self.domain = domain
        
    
    def __unicode__(self):
        return unicode(self.target_namespace)

    def __str__(self):
        return unicode(self).encode('utf-8')

    @classmethod
    def from_file(cls, file, valid=True):
        """ By default, schemas read off of the file system are forced to be valid
        (for now, this just means that poorly formatted versions are forced to None)
        """
        fin = open(file, 'r')
        formdef = FormDef(fin)
        if valid:
            formdef.force_to_valid()
        fin.close()
        return formdef

    def to_str(self):
        """ Dumps the entire contents of this to a string """
        string =  "\nDEFINITION OF " + str(self.name) + "\n"
        string = string + "TYPES: \n"
        for t in self.types:
            string = string + self.types[t].name + "\n" 
            for allowable_value in self.types[t].allowable_values:
                string = string + " allowable_value: " + allowable_value + "\n"                 
            for multiselect_value in self.types[t].multiselect_values:
                string = string + " multiselect_value: " + multiselect_value + "\n"                 
        string = string + "ELEMENTS: \n"
        return string + ElementDef.to_str(self)
        
    
    def populateFromXmlString(self, string):
        """ Populates formdef with data from xml string
        
            Note that we currently allow 'bad form' xforms 
            (e.g. bad metadata, bad version numbers)
            Such errors can be caught/reported using FormDef.validate()
        """
        
        root = etree.XML(string)

        self.version = case_insensitive_attribute(root, "version")
        self.uiversion = case_insensitive_attribute(root, "uiversion")
        self.target_namespace = case_insensitive_attribute(root, 'targetNamespace')
        
        if not self.target_namespace:
            logging.error("Target namespace is not found in xsd schema")
        
        ElementDef.__init__(self, self.target_namespace)

        self.xpath = ""
        self._addAttributesAndChildElements(self, root, '')
    
    @property
    def root_element(self):
        '''Get the root ElementDef for this form.  This will throw an
           exception if there is more than one root child defined.'''  
        if len(self.child_elements) != 1:
            raise Exception("Tried to get the single root from %s but found %s nodes"
                             % (self, len(self.child_elements)))
        return self.child_elements[0]
    
    @property
    def domain_name(self):
        """Get the domain name, or an empty string if none found"""
        if self.domain:
            return self.domain.name
        return ""
    
    def get_meta_element(self):
        '''Gets the meta element from the form, if it exists.
           Meta is defined as a top-level child of the form with
           the name "meta" (case insenitive).  If no meta block
           is found, this returns nothing''' 
        for child in self.root_element.child_elements:
            if child.short_name.lower() == "meta":
                return child
        
    @classmethod
    def get_meta_validation_issues(cls, element):
        '''Validates an ElementDef, assuming it is a meta block.  Ensures
           that every field we expect to find in the meta is there, and 
           that there are no extra fields.  Returns a dictionary of
           of any errors/warnings found in the following format:
           { "missing" : [list, of, missing, expected, fields]
             "duplicate" : [list, of, duplicate, fields]
             "extra" : [list, of, unexpected, fields]
           }
           If any of these lists are empty they won't be in the dictionary,
           and therefore if all are empty this method will return an empty
           dictionary.
        '''
        
        missing_fields = []
        extra_fields = []
        duplicate_fields = []
        found_fields = []
        missing_fields.extend(xfm.models.Metadata.fields)
        
        # hackily remove some stuff we no longer want to require
        missing_fields.remove('formname')
        missing_fields.remove('formversion')
        for field in element.child_elements:
            field_name = field.short_name.lower()
            if field_name in missing_fields:
                missing_fields.remove(field_name)
                found_fields.append(field_name)
            elif field_name in found_fields:
                # it was already found, therefore it must be 
                # a duplicate
                duplicate_fields.append(field_name)
            else:
                # it wasn't in the expected list, and wasn't a 
                # dupe, it must be an extra
                extra_fields.append(field_name)
        to_return = {}
        if missing_fields:
            to_return["missing"] = missing_fields
        if duplicate_fields:
            to_return["duplicate"] = duplicate_fields
        if extra_fields:
            to_return["extra"] = extra_fields
        return to_return

    def _addAttributesAndChildElements(self, element, input_tree, name_prefix):
        for input_node in etree.ElementChildIterator(input_tree):
            name = str(input_node.get('name'))
            if (str(input_node.tag)).find("element") > -1:
                next_name_prefix = ''
                if input_node.get('maxOccurs') > 1:
                    child_element = ElementDef(is_repeatable=True)
                    child_element.populateElementFields(input_node, element.xpath, name)
                else:
                    child_element = ElementDef()
                    # discard parent_name
                    next_name_prefix = join_if_exists( name_prefix, name )
                    full_name = next_name_prefix
                    child_element.populateElementFields(input_node, element.xpath, full_name)
                element.addChild(child_element)
                # theoretically, simpleType enumerations and list values can be
                # defined inside of elements in practice, this isn't how things
                # are currently generated in the schema generator, so we don't 
                # support that (yet)
                self._addAttributesAndChildElements(child_element, input_node, next_name_prefix )
            elif (str(input_node.tag)).find("simpleType") > -1:
                simpleType = SimpleType( str(input_node.get('name')) )
                child = input_node[0]
                if (str(child.tag)).find("restriction") > -1:
                    for enum in child:
                        if (str(enum.tag)).find("enumeration") > -1:
                            simpleType.allowable_values.append( sanitize(enum.get("value")) )
                elif (str(child.tag)).find("list") > -1:
                    multiselect_name = child.get("itemType")
                    if self.types[multiselect_name] is not None:
                        simpleType.multiselect_values = self.types[multiselect_name].allowable_values
                # add new type definition
                self.types[simpleType.name] = simpleType
            else:
                # Skip non-elements (e.g. <sequence>, <complex-type>
                self._addAttributesAndChildElements(element, input_node, name_prefix)

    def validate(self):
        # check xmlns not none
        namespace_help_text = "You should find the block in your xform labeled <instance> and " + \
                              "add an xmlns attribute to the first element so it looks like: " + \
                              '<instance><node xmlns="http://your.xmlns.goes/here">.  An xmlns ' + \
                              "is a unique attribute that helps identify the form"
                                       
        if not self.target_namespace:
            raise FormDef.FormDefError("No namespace (xmlns) found in submitted form: %s" % \
                                       self.name, FormDef.FormDefError.ERROR, namespace_help_text)

        # all the forms in use today have a superset namespace they default to
        # something like: http://www.w3.org/2002/xforms
        if self.target_namespace.lower().find('www.w3.org') != -1:
            raise FormDef.FormDefError("No unique namespace (xmlns) found in submitted form: %s" % \
                                       self.target_namespace, FormDef.FormDefError.ERROR,
                                       namespace_help_text)
        
        if self.version is None or self.version.strip() == "":
            raise FormDef.FormDefError("No version number found in submitted form: %s" % \
                                       self.target_namespace, FormDef.FormDefError.WARNING)
        if not self.version.strip().isdigit():
            # should make this into a custom exception
            raise FormDef.FormDefError("Version attribute must be an integer in xform %s but was %s" % \
                                       (self.target_namespace, self.version), FormDef.FormDefError.WARNING)

        meta_element = self.get_meta_element()
        if not meta_element:
            raise FormDef.FormDefError("From %s had no meta block!" % self.target_namespace, FormDef.FormDefError.WARNING)
        
        meta_issues = FormDef.get_meta_validation_issues(meta_element)
        if meta_issues:
            mve = xfm.models.MetaDataValidationError(meta_issues, self.target_namespace)
            # until we have a clear understanding of how meta versions will work,
            # don't fail on issues that only come back with "extra" set.  i.e.
            # look for missing or duplicate
            if mve.duplicate or mve.missing:
                raise mve
            else:
                logging.warning("Found extra meta fields in xform %s: %s" % 
                                (self.target_namespace, mve.extra))
        # validated! 
        return True
    
    def force_to_valid(self):
        if self.version and self.version.strip().isdigit():
            self.version = int(self.version.strip())
        else:
            self.version = None
        if self.uiversion and self.uiversion.strip().isdigit():
            self.uiversion = int(self.uiversion.strip())
        else:
            self.uiversion = None

    def is_compatible_with(self, otherdef):
        """ are these two formdef's compatible 
        i.e. can they share the same raw data tables
        """
        return self.get_differences(otherdef).is_empty()

    def get_differences(self, otherdef):
        # Not sure if it's bad form to be relying on modifying this
        # '_visited' variable, but this seems like the most
        # straightforward solution for now
        otherdef._clear_visited()
        d = self._get_formdef_diff(otherdef)
        d = d + self._get_children_diff(otherdef)
        d.fields_added = otherdef._get_unvisited()
        return d

    def _get_formdef_diff(self, otherdef):
        d = self._get_elementdef_diff(otherdef)
        # currently, the only relevant differences to check per formdef
        # are the type definitions
        for i in self.types:
            if i in otherdef.types:
                if self.types[i] != otherdef.types[i]:
                    d.types_changed.append(otherdef.types[i])
            # if i not in otherdef.types
            # this is fine, as long as it's not referenced somewhere
            # if it's references somewhere, that'll be captured as
            # a field_changed diff
        # we don't need to check for types added
        # since this will be reported in the form of 'field added' or 'field changed'
        return d
    
    class FormDefError(Exception):
        """Error from FormDef Processing.  Allows for specification
           of an additional 'category' which can separate true errors
           from warning-type errors."""
        
        ERROR = 1
        WARNING = 2
        
        def __init__(self, message, category, help_text=""):
            super(FormDef.FormDefError, self).__init__(message)
            self.category = category
            self.help_text = help_text
            
        

class SimpleType(object):
    """ Stores type definition for simple types """
    def __init__(self, name=''):
        self.allowable_values = []
        self.multiselect_values = []
        self.name = name
    
    def __ne__(self, other):
        """ case-insensitive comparison """
        # we do case-sensitive comparison, since xml is case-sensitive
        return not (self == other)

    def __eq__(self, other):
        """ case-insensitive comparison """
        # we do case-sensitive comparison, since xml is case-sensitive
        return (self.multiselect_values == other.multiselect_values) and \
                (self.allowable_values == other.allowable_values) and \
                (self.name == other.name)
        """ we may want case-insensitive comparison later, which would be:
        return ([i.lower() for i in self.multiselect_values] == \
                [j.lower() for j in other.multiselect_values]) and \
                ([i.lower() for i in self.allowable_values] == \
                [j.lower() for j in other.allowable_values]) and \
                (self.name.lower() == other.name.lower())
        """
        

class Differences(object):
    """ Data structure to represent the differences between this and another formdef """
    def __init__(self):
        self.otherdef = None
        self.fields_added = []
        self.fields_removed = []
        self.fields_changed = []
        # types added is not required for now, since it will also 
        # be caught by fields_changed or fields_added
        self.types_changed = []
        
    def __add__(self, other):
        d = Differences()
        d.fields_added = self.fields_added + other.fields_added
        d.fields_removed = self.fields_removed + other.fields_removed
        d.fields_changed = self.fields_changed + other.fields_changed
        d.types_changed = self.types_changed + other.types_changed
        return d
    
    def is_empty(self):
        '''Return whether this is meaningfully empty (i.e. representing 
           no differences'''
        return not (self.fields_added or self.fields_changed or \
                    self.fields_removed or self.types_changed)
        
    def __unicode__(self):
        if self.is_empty():
            return "No differences"
        else:
            attrs = ["fields_added", "fields_removed", "fields_changed", "types_changed"]
            msgs = [self._display_string(attr) for attr in attrs]
            return "\n".join([display for display in msgs if display])
    
    def __str__(self):
        return unicode(self).encode('utf-8')

    def _display_string(self, attr):
        if hasattr(self, attr):
            vals = getattr(self, attr)
            if vals:
                val_strs = [str(val) for val in vals]
                return "%s %s: %s" % (len(val_strs), 
                                      attr.replace("_", " "), 
                                      ",".join(val_strs))
        return ""