import sys
import os
import urllib2
import shutil

import tempfile as tmp
from zipfile import ZipFile 
from cStringIO import StringIO

# import re
# import logging

# from buildmanager import xformvalidator
# from buildmanager.exceptions import BuildError

# from xformmanager.models import MetaDataValidationError
# from xformmanager.xformdef import FormDef, ElementDef


def add_to_jar(jar_file, path_to_add):
    '''adds files under /path_to_add to jar_file, return path to the new JAR'''
    if not os.path.isdir(path_to_add):
        raise "Trying to add non-existant directory '%s' to JAR" % path_to_add
        
    if not jar_file.endswith('.jar') or not os.path.isfile(jar_file):
        raise "'%s' isn't a JAR file" % jar_file

    tmpjar = os.path.join(tmp.mkdtemp(), os.path.basename(jar_file))
    shutil.copy2(jar_file, tmpjar)
    
    zf = ZipFile(tmpjar, 'a')
    
    for f in os.listdir(path_to_add):
        zf.write(os.path.join(path_to_add, f))
        
    zf.close
    
    return tmpjar


def modify_jad(jad_file, jar_file):
    tmpjad = os.path.join(tmp.mkdtemp(), os.path.basename(jad_file))
    shutil.copy2(jad_file, tmpjad)

    # modify tmpjad here...
    
    return tmpjad
    
    
def create_zip(target, files):
    ''' create zip from files list, returns created zip file'''
    print target, files
    zf = ZipFile(target, 'w')
    for f in files:
        zf.write(f)
    
    zf.close()
    return target
    
    
# http://bitbucket.org/ctsims/resourcetest/get/tip.zip
def grab_from(url):
    '''copy a file from a URL to a local tmp dir, returns path to local copy'''
    u = urllib2.urlopen(url)
    u = u.read()
    
    x, tmpfile = tmp.mkstemp()
    f = open(tmpfile, 'w')
    f.write(u)
    f.close()
    
    return tmpfile


def unzip_to_tmp(zip_file):
    '''
    extracts a resources zip.
    assumes that all files are on one root dir
    returns path of extracted files
    '''
    zf = ZipFile(zip_file)
    target_dir = tmp.mkdtemp()
    
    namelist = zf.namelist()
    filelist = filter( lambda x: not x.endswith( '/' ), namelist )

    for filename in filelist:
        basename = os.path.basename(filename)
        if basename.startswith('.'): continue #filename.endswith(".xml") or filename.endswith(".xhtml"):

        target_file = os.path.join(target_dir, basename)

        out = open(target_file, 'wb')

        buffer = StringIO( zf.read(filename))
        buflen = 2 ** 20
        datum = buffer.read(buflen)

        while datum:
            out.write(datum)
            datum = buffer.read(buflen)
        out.close()
        
    return target_dir
