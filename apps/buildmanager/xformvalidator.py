import os
from StringIO import StringIO

from xformmanager.xformdef import FormDef
from xformmanager.manager import form_translate

import buildmanager.xformvalidator




def validate(xform_filename):
    '''Validates an xform from a passed in file.  Returns nothing
       if validation succeeds.  Raises an exception if validation
       fails.'''
    body = None
    try:
        body = open(xform_filename, "r")
        form_display = os.path.basename(xform_filename)
        output, errorstream, has_error = form_translate(body.read())
        if has_error:
            raise BuildError("Could not convert xform (%s) to schema.  Your error is %s" % 
                             (form_display, errorstream))
        # if no errors, we should have a valid schema in the output
        # check the meta block, by creating a formdef object and inspecting it
        formdef = FormDef(StringIO(output))
        if not formdef:
            raise BuildError("Could not get a valid form definition from the xml file: %s"
                              % form_display)
            
        #formdef.validate() throws errors on poor validation
        formdef.validate()
        
        # if we made it here we're all good
    finally:
        # cleanup
        if body:
            body.close()
