import inspect

def is_mod_function(mod, func):
    '''Returns whether the object is a function in the module''' 
    return inspect.isfunction(func) and inspect.getmodule(func) == mod

def get_custom_report_module(domain):
    '''Get the reports module for a domain, if it exists.  Otherwise
       this returns nothing'''
    try:
        rep_module = __import__("reports.custom.%s" % domain.name.lower(), 
                                fromlist=[''])
        return rep_module
    except ImportError:
        # this is ok, there just weren't any custom reports
        return None
        
        

def get_custom_reports(report_module):
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


