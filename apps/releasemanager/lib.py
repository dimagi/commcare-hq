import sys
import os
import urllib2
import tempfile 
import shutil
import re
import shlex

from django.middleware.common import *

import tempfile as tmp
from zipfile import ZipFile 
from cStringIO import StringIO

from subprocess import Popen, PIPE
from releasemanager import xformvalidator
from django.conf import settings
from releasemanager.jar import extract_xforms

from xformmanager.models import FormDefModel

from xformmanager.manager import XFormManager
import logging
import traceback
from xformmanager.xformdef import FormDef
from releasemanager.exceptions import XFormConflictError, FormReleaseError


UNKNOWN_IP = "0.0.0.0"

def rlistdir(start_path, paths=[], prepend='', ignore_hidden=True):
    ''' list dirs recursively '''
    
    for f in os.listdir(start_path):
        if ignore_hidden and f.startswith('.'): continue
        full_path = os.path.join(start_path, f)
        if os.path.isdir(full_path):
            rlistdir(full_path, paths, f)
        
        paths.append(os.path.join(prepend, f))

    return paths


def add_to_jar(jar_file, path_to_add):
    '''adds files under /path_to_add to jar_file, return path to the new JAR'''
    if not os.path.isdir(path_to_add):
        raise "Trying to add non-existant directory '%s' to JAR" % str(path_to_add)

    if not jar_file.endswith('.jar') or not os.path.isfile(jar_file):
        raise "'%s' isn't a JAR file" % jar_file

    newjar_filename = os.path.join(tmp.mkdtemp(), os.path.basename(jar_file))

    oldjar = ZipFile(jar_file, 'r')
    newjar = ZipFile(newjar_filename, 'w')
    
    # Here we do some juggling, since ZipFile doesn't have a delete method
    
    # first, add all the resource set files
    files = rlistdir(path_to_add)    
    
    for f in files:
        full_path = os.path.join(path_to_add, f)
        if os.path.isdir(full_path): continue
        newjar.write(full_path, str(f))
        
    # now add the JAR files, taking care not to add filenames that already exist in the resource set
    existing_files = newjar.namelist()
    
    for f in oldjar.infolist():
        if f.filename in existing_files: 
            continue
        buffer = oldjar.read(f.filename)
        newjar.writestr(f, buffer)
    
    newjar.close()
    oldjar.close()
    
    return newjar_filename
        

def jad_to_dict(jad_contents):
    jad = {}
    for line in jad_contents.strip().split("\n"):
        key, val = line.split(':',1)
        jad[key] = val.strip()
    
    return jad


def modify_jad(jad_file, modify_dict):
    jad = jad_to_dict(open(jad_file).read())

    for i in modify_dict:
        jad[i] = modify_dict[i]

    # create new JAD
    new_content = ''
    for i in jad:
        new_content += "%s: %s\n" % (i, jad[i])

    f = open(jad_file, 'w')
    f.write(new_content)
    f.close()

    return jad_file
    
    
def create_zip(target, jar_file, jad_file):
    ''' create zip from the jar & jad '''
    target = str(target) ; jar_file = str(jar_file) ; jad_file = str(jad_file)
    
    zf = ZipFile(target, 'w')
    
    zf.write(jar_file, os.path.basename(jar_file))
    zf.write(jad_file, os.path.basename(jad_file))
    
    zf.close()
    return target
    

# #### Deprecating ZIP URL #####
# # http://bitbucket.org/ctsims/resourcetest/get/tip.zip
# def grab_from(url):
#     '''copy a file from a URL to a local tmp dir, returns path to local copy'''
#     u = urllib2.urlopen(url)
#     u = u.read()
#     
#     x, tmpfile = tmp.mkstemp()
#     f = open(tmpfile, 'w')
#     f.write(u)
#     f.close()
#     
#     return tmpfile
# 
# 
# def unzip(zip_file, target_dir=None):
#     '''
#     extracts a resources zip.
#     assumes that all files are on one root dir
#     returns path of extracted files
#     '''
#     zf = ZipFile(zip_file)
#     if target_dir is None:
#         target_dir = tmp.mkdtemp()
#     elif not os.path.exists(target_dir):
#         os.makedirs(target_dir)
#     
#     namelist = zf.namelist()
#     filelist = filter( lambda x: not x.endswith( '/' ), namelist )
# 
#     for filename in filelist:
#         basename = os.path.basename(filename)
#         if basename.startswith('.'): continue #filename.endswith(".xml") or filename.endswith(".xhtml"):
# 
#         target_file = os.path.join(target_dir, basename)
# 
#         out = open(target_file, 'wb')
# 
#         buffer = StringIO( zf.read(filename))
#         buflen = 2 ** 20
#         datum = buffer.read(buflen)
# 
#         while datum:
#             out.write(datum)
#             datum = buffer.read(buflen)
#         out.close()
#         
#     return target_dir


def clone_from(url):
    if re.match(r'https?:\/\/.*bitbucket.org\/', url) is not None:
        # hg won't clone to an existing directory, and tempfile won't return just a name without creating a dir
        # so just delete the new tmp dir and let hg recreate it in clone
        tmpdir = tmp.mkdtemp()
        os.rmdir(tmpdir)

        # obviously, this depends on a particular URL format.
        # if we stick with bitbucket, standardize on an expected URL.
        hg_root, path = url.split('/src')
        path = path.replace('/tip', '')
        path = path.lstrip('/') # dont confuse os.path.join
        
        clone_cmd = ["hg", "clone", hg_root, tmpdir]
        p = Popen(clone_cmd, stdout=PIPE, stderr=PIPE, shell=False)
        err = p.stderr.read().strip()
        
        if err != '': raise err

        return os.path.join(tmpdir, path)

    else:
        raise "Unknown SCM URL"
    

# unused for now. move it later to a short_url app as HQ-wide service.
def get_bitly_url_for(url):
    try:
        bitly_login  = settings.RAPIDSMS_APPS['releasemanager']['bitly_login']
        bitly_apikey = settings.RAPIDSMS_APPS['releasemanager']['bitly_apikey']
    except:
        return False

    bitly_url = "http://api.bit.ly/v3/shorten?login=dmgi&apiKey=R_af7d5c0d899197fe43e18acceebd5cdb&uri=%s&format=txt" % url
    
    u = urllib2.urlopen(bitly_url)
    short_url = u.read().strip()
    
    if short_url == '': return False
    
    return short_url
    

def validate_resources(resources):
    """
    Validate a list of resources, currently by trying to parse everything
    like an xform and then register it.  Returns a dictionary of resource names
    with values either None if validaiton was successful, otherwise the 
    exception that was thrown during validation.
    """
    errors = {}
    for file in os.listdir(resources):
        if file.endswith(".xml") or file.endswith(".xhtml"):
            try:
                xformvalidator.validate(os.path.join(resources, file))
                errors[file] = None
                logging.debug("%s validates successfully" % file) 
            except Exception, e:
                errors[file] = e
    return errors
    

def register_forms(build, good_forms):
    """Try to register the forms from jar_file."""
    # this was copied and modified from buildmanager models. 
    errors = {}
    to_skip = []
    to_register = []
    path = tempfile.tempdir
    xforms = extract_xforms(build.jar_file, path)
    for form in xforms:
        if os.path.basename(form) not in good_forms:
            logging.debug("skipping %s, not a good form" % form)
            continue
        try:
            formdef = xformvalidator.validate(form)
            modelform = FormDefModel.get_model(formdef.target_namespace,
                                               build.resource_set.domain, 
                                               formdef.version)
            if modelform:
                # if the model form exists we must ensure it is compatible
                # with the version we are trying to release
                existing_formdef = modelform.to_formdef()
                differences = existing_formdef.get_differences(formdef)
                if differences.is_empty():
                    # this is all good
                    to_skip.append(form)
                else:
                    raise XFormConflictError(("Schema %s is not compatible with %s."  
                                              "Because of the following differences:" 
                                              "%s"
                                              "You must update your version number!")
                                                    % (existing_formdef, formdef, differences))
            else:
                # this must be registered
                to_register.append(form)
        except FormDef.FormDefError, e:
            # we'll allow warnings through
            if e.category == FormDef.FormDefError.WARNING:  pass
            else:                                           errors[form] = e
        except Exception, e:
            info = sys.exc_info()
            logging.error("Error preprocessing form in build manager: %s\n%s" % \
                          (e, traceback.print_tb(info[2])))
            errors[form] = e
    if errors:
        return errors
    # finally register
    manager = XFormManager()
    # TODO: we need transaction management
    for form in to_register:
        try:
            formdefmodel = manager.add_schema(os.path.basename(form),
                                              open(form, "r"),
                                              build.resource_set.domain)
            
            # TODO, find better values for these?
            formdefmodel.submit_ip = UNKNOWN_IP
            user = None
            formdefmodel.uploaded_by = user
            formdefmodel.bytes_received =  len(form)
            formdefmodel.form_display_name = os.path.basename(form)
            formdefmodel.save()
            errors[form] = None                
        except Exception, e:
            # log the error with the stack, otherwise this is hard to track down
            info = sys.exc_info()
            logging.error("Error registering form in build manager: %s\n%s" % \
                          (e, traceback.print_tb(info[2])))
            errors[form] = FormReleaseError("%s" % e)
    return errors
    

def sign_jar(jar_file, jad_file):
    ''' run jadTool on the newly created JAR '''
    jad_tool    = settings.RAPIDSMS_APPS['releasemanager']['jadtool_path']
    key_store   = settings.RAPIDSMS_APPS['releasemanager']['key_store']
    key_alias   = settings.RAPIDSMS_APPS['releasemanager']['key_alias']
    store_pass  = settings.RAPIDSMS_APPS['releasemanager']['store_pass']
    key_pass    = settings.RAPIDSMS_APPS['releasemanager']['key_pass']
    
    cmd = "java -jar %s -addjarsig -jarfile %s -alias %s -keystore %s -storepass %s -keypass %s -inputjad %s -outputjad %s" % \
                    (jad_tool, jar_file, key_alias, key_store, store_pass, key_pass, jad_file, jad_file)
    
    p = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE, shell=False)
    err = p.stderr.read().strip()
    if err != '': raise err

    jad_file = modify_jad(jad_file, {
                "MIDlet-Permissions": "javax.microedition.media.control.RecordControl,javax.microedition.io.Connector.file.write,javax.microedition.io.Connector.file.read",
                "MIDlet-Permissions-Opt": "javax.microedition.media.protocol.Datasource,javax.microedition.media.control.RecordControl,javax.microedition.media.control.VideoControl.getSnapshot,javax.microedition.media.Player,javax.microedition.media.Manager"
                })
                
    return jar_file, jad_file
    
    
    