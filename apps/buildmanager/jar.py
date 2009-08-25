import sys
import re
import zipfile
import os
import tempfile
import shutil
from StringIO import StringIO

from models import BuildError
from xformmanager.manager import XFormManager, form_translate

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
    os.chdir( dir )
    extracted_forms = []
    # extract files that match the xforms definition 
    for filename in filelist:
        if filename.endswith(".xml") or filename.endswith(".xhtml"):
            try:
                out = open( filename, 'wb' )
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
    os.chdir( pushd )
    return extracted_forms
    
def validate_jar(filename):
    '''Validates a jar for use with CommCare HQ.  It performs the following
       steps and checks:
        1. Ensures the jar is valid and contains at least one xform in the 
           root.
        2. Runs every found xform through the schema conversion logic and
           ensures that there are no problems.'''
    temp_directory = tempfile.mkdtemp()
    body = None
    try: 
        xforms = extract_xforms(filename, temp_directory)
        if not xforms:
            raise BuildError("Jar file must have at least 1 xform")
        # now run through each of the forms and try to convert to 
        # a schema
        for xform in xforms:
            body = open(xform, "r")
            output, errorstream, has_error = form_translate(xform, body.read())
            if has_error:
                raise BuildError("Could not convert xform (%s) to schema.  Your error is %s" % (xform, errorstream))
    finally:
        # clean up after ourselves
        if body:
            body.close()
        shutil.rmtree(temp_directory)
