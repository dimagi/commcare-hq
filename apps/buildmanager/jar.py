import sys
import re
import zipfile
import os
import tempfile
import shutil
import logging
from StringIO import StringIO

from buildmanager import xformvalidator
from buildmanager.exceptions import BuildError

from xformmanager.models import MetaDataValidationError
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
    
def validate_jar(filename, include_xforms=True):
    '''Validates a jar for use with CommCare HQ.  It performs the following
       steps and checks:
        1. Ensures the jar is valid and contains at least one xform in the 
           root.
        == If include_xforms is True ==
        2. Runs every found xform through the schema conversion logic and
           ensures that there are no problems.
        3. Runs every generated schema through validation that checks for
           the existence of a <meta> block, and that there are no missing/
           duplicate/extra tags in it.'''
    temp_directory = tempfile.mkdtemp()
    try: 
        xforms = extract_xforms(filename, temp_directory)
        if not xforms:
            raise BuildError("Jar file must have at least 1 xform")
        
        # when things go wrong we'll store them here.  
        # we'll throw a big fat exception at the end, that
        # will wrap all the other ones.
        errors = []
        if include_xforms:
            # now run through each of the forms and try to convert to 
            # a schema, as well as adding all kinds of validation checks
            for xform in xforms:
                try:
                    xformvalidator.validate(xform)
                except Exception, e:
                    errors.append(e)
        if errors:
            raise BuildError("Problem validating jar!", errors)
        
    finally:
        # clean up after ourselves
        shutil.rmtree(temp_directory)
