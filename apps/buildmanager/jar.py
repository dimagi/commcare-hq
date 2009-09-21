import sys
import re
import zipfile
import os
import tempfile
import shutil
import logging
from StringIO import StringIO

from models import BuildError
from xformmanager.models import MetaDataValidationError
from xformmanager.manager import XFormManager, form_translate
from xformmanager.xformdef import FormDef, ElementDef

def extract_xforms( filename, dir ):
    '''Extracts the xforms from a jar file to a given directory.  
       Assumes that all xforms will be at the root of the jar.
       Returns a list of the extracted forms with absolute paths'''
    
    # hat tip: http://code.activestate.com/recipes/465649/
    zf = zipfile.ZipFile( filename )
    namelist = zf.namelist()
    filelist = filter( lambda x: not x.endswith( '/' ), namelist )
    # make base directory if it doesn't exist
    pushd = os.getcwd()
    if not os.path.isdir( dir ):
        os.mkdir( dir )
    extracted_forms = []
    # extract files that match the xforms definition 
    for filename in filelist:
        if filename.endswith(".xml") or filename.endswith(".xhtml"):
            try:
                out = open( os.path.join(dir,filename), 'wb' )
                buffer = StringIO( zf.read( filename ))
                buflen = 2 ** 20
                datum = buffer.read( buflen )
                while datum:
                    out.write( datum )
                    datum = buffer.read( buflen )
                out.close()
                extracted_forms.append(os.path.join(dir, filename))
            except Exception, e:
                logging.error("Problem extracting xform: %s, error is %s" % filename, e)
    return extracted_forms
    
def validate_jar(filename):
    '''Validates a jar for use with CommCare HQ.  It performs the following
       steps and checks:
        1. Ensures the jar is valid and contains at least one xform in the 
           root.
        2. Runs every found xform through the schema conversion logic and
           ensures that there are no problems.
        3. Runs every generated schema through validation that checks for
           the existence of a <meta> block, and that there are no missing/
           duplicate/extra tags in it.'''
    temp_directory = tempfile.mkdtemp()
    body = None
    try: 
        xforms = extract_xforms(filename, temp_directory)
        if not xforms:
            raise BuildError("Jar file must have at least 1 xform")
        
        # when things go wrong we'll store them here.  
        # we'll throw a big fat exception at the end, that
        # will wrap all the other ones.
        errors = []
        
        # now run through each of the forms and try to convert to 
        # a schema, as well as adding all kinds of validation checks
        for xform in xforms:
            try:
                body = open(xform, "r")
                form_display = os.path.basename(xform)
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
                    
                # check xmlns not none
                if not formdef.target_namespace:
                    raise BuildError("No namespace found in submitted form: %s" % form_display)

                # all the forms in use today have a superset namespace they default to
                # something like: http://www.w3.org/2002/xforms
                if formdef.target_namespace.lower().find('www.w3.org') != -1:
                    raise BuildError("No namespace found in submitted form: %s" % form_display)
                
                meta_element = formdef.get_meta_element()
                if not meta_element:
                    raise BuildError("From %s had no meta block!" % form_display)
                
                meta_issues = FormDef.get_meta_validation_issues(meta_element)
                if meta_issues:
                    mve = MetaDataValidationError(meta_issues, form_display)
                    # until we have a clear understanding of how meta versions will work,
                    # don't fail on issues that only come back with "extra" set.  i.e.
                    # look for missing or duplicate
                    if mve.duplicate or mve.missing:
                        raise mve
                    else:
                        logging.warning("Found extra meta fields in xform %s: %s" % 
                                        (form_display, mve.extra))
                
                # if we made it here we're all good
            except Exception, e:
                errors.append(e)
        if errors:
            raise BuildError("Problem validating jar!", errors)
        
    finally:
        # clean up after ourselves
        if body:
            body.close()
        shutil.rmtree(temp_directory)
