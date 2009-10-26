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


def _safe_import(module_name):    
    try:
        return __import__(module_name, 
                                fromlist=[''])
    except ImportError:
        # this is ok, there just wasn't a module with custom reports
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


