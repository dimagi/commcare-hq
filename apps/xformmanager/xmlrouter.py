
"""Route XML files to various processing methods.
"""


registered_methods = {}
    
def process(filename, attachment, xmlns, version=0):
    """Process an xml document, by sending it to any known registered methods.
       If no methods are registered this does nothing."""
    if xmlns in registered_methods:
        for method in registered_methods:
            method(filename, attachment)
        return True
    
def register(xmlns, method):
    """Register an xmlns to be processed by a method"""
    if xmlns in registered_methods:
        registered_methods[xmlns].append(method)
    else:
        registered_methods = [method]