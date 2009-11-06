"""
Utility functions for report framework
"""
import inspect
from reports.custom.all import default

def is_mod_function(mod, func):
    '''Returns whether the object is a function in the module''' 
    return inspect.isfunction(func) and inspect.getmodule(func) == mod

def get_custom_report_module(domain):
    '''Get the reports module for a domain, if it exists.  Otherwise
       this returns nothing'''
    return _safe_import("reports.custom.%s" % domain.name.lower())


def get_global_report_module(domain):
    '''Get the global reports module for a domain.'''
    module = _safe_import("reports.custom.all.%s" % domain.name.lower()) 
    if not module:
        module = default
    return module

def get_report_method(domain, report_name):
    """Gets a domained report by name, checking first the explicit
       custom reports and then the domain defaults.  If no such
       report is found, returns None"""
    report_module = get_custom_report_module(domain)
    if report_module and hasattr(report_module, report_name):
        return getattr(report_module, report_name)
    default_module = get_global_report_module(domain)
    if default_module and hasattr(default_module, report_name):
        return getattr(default_module, report_name)
    return None
    
        
def get_custom_reports(domain):
    """Gets all the custom reports for the domain (including any global 
       default reports)"""
    custom_report_module = get_custom_report_module(domain)
    if custom_report_module:
        custom = extract_custom_reports(custom_report_module)
    else:
        custom = []
    default_report_module = get_global_report_module(domain)
    custom.extend(extract_custom_reports(default_report_module))
    return custom
    
def extract_custom_reports(report_module):
    '''Given a reports module , get the list of custom reports defined
       in that class.  These are returned as dictionaries of the 
       following format:
         { "name" : function_name, "display_name" : function_doc }
       see reports/custom.py for more information 
    '''
    to_return = []
    for name in dir(report_module):
        obj = getattr(report_module, name)
        # using ismethod filters out the builtins and any 
        # other fields defined in the custom class.  
        # also use the python convention of keeping methods
        # that start with an "_" private.
        if is_mod_function(report_module, obj) and\
          not obj.func_name.startswith("_"):
            obj_rep = {"name" : obj.func_name,
                       "display_name" : obj.__doc__   
                       } 
            to_return.append(obj_rep)
    return to_return

def get_whereclause(params):
    """Given a dictionary of params {key1: val1, key2: val2 } 
       return a partial query like:
       WHERE key1 = val1
       AND   key2 = val2 
       ...
    """
    query_parts = []
    first = False
    for key, val in params.items():
        if not first:
            first = True
            query_parts.append("WHERE %s = '%s'" % (key, val))
        else:
            query_parts.append("AND %s = '%s'" % (key, val))
    return " ".join(query_parts)
def _safe_import(module_name):    
    try:
        return __import__(module_name, 
                                fromlist=[''])
    except ImportError:
        # this is ok, there just wasn't a module with custom reports
        return None

