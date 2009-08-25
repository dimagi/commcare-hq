import sys
import re
import zipfile
import os
from StringIO import StringIO

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
    

