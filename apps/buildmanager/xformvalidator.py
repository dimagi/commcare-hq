import os
from StringIO import StringIO

from xformmanager.xformdef import FormDef
from xformmanager.manager import form_translate

import buildmanager.xformvalidator
from buildmanager.exceptions import BuildError



def validate(xform_filename):
    '''Validates an xform from a passed in file.  Returns the 
       generated FormDef object if validation succeeds.   
       Raises an exception if validation fails.'''
    body = None
    try:
        body = open(xform_filename, "r")
        form_display = os.path.basename(xform_filename)
        full_text = body.read()
        return validate_xml(full_text, form_display)
    finally:
        # cleanup
        if body:
            body.close()

def validate_xml(xml_body, display_name="your xform", do_hq_validation=True):
    """Validates an xform from the raw text, and takes in a display
       name to use in throwing erros. Returns the generated FormDef
       or thows an exception on failure."""
    output, errorstream, has_error = form_translate(xml_body)
    if has_error:
        raise BuildError("Could not convert xform (%s) to schema.  Your error is %s" % 
                         (display_name, errorstream))
    # if no errors, we should have a valid schema in the output
    # check the meta block, by creating a formdef object and inspecting it
    formdef = FormDef(StringIO(output))
    if not formdef:
        raise BuildError("Could not get a valid form definition from the xml file: %s"
                          % form_display)
    
    if do_hq_validation:    
        #formdef.validate() throws errors on poor validation
        formdef.validate()
    
    # if we made it here we're all good
    return formdef