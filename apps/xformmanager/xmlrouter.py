
"""Route XML files to various processing methods.
"""


registered_methods = {}
    
def process(attachment, xmlns, version=0):
    """Process an xml document, by sending it to any known registered methods.
       If no methods are registered this does nothing."""
    global registered_methods
    if xmlns in registered_methods:
        for method in registered_methods[xmlns]:
            method(attachment)
        return True
    
def register(xmlns, method):
    """Register an xmlns to be processed by a method.  If the method is already
       registered this has no effect."""
    global registered_methods
    if xmlns in registered_methods:
        if not method in registered_methods[xmlns]:
            registered_methods[xmlns].append(method)
    else:
        registered_methods[xmlns] = [method]
        
def is_registered(xmlns, method):
    """Whether a particular method is registered with an xmlns.""" 
    global registered_methods
    if xmlns in registered_methods:
        return method in registered_methods[xmlns]
    return False

def reset():
    """Reset the list of registered methods""" 
    global registered_methods
    registered_methods = {} 