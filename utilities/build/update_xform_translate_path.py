#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

"""
The sole purpose of the following script is to update the
local.ini file used by the dimagi teamcity buildserver
so that the path to xform_translate.jar is updated dynamically.

It does this by identifying the jar_path_placeholder in the file
identified by the environment variable RAPIDSMS_INI and replacing
it with the value of {project.dir}/lib

CONFIGURATION
jar_path_placeholder: the setting in local.build.ini which we 
want to update dynamically 

"""
jar_path_placeholder = 'DYNAMIC_PATH_TO_XFORM_TRANSLATE_JAR'

import sys, os
if 'RAPIDSMS_INI' not in os.environ:
    print "RAPIDSMS_INI NOT FOUND"
    sys.exit()
local_ini = os.environ['RAPIDSMS_INI']
fin = open(local_ini,"r")
ini = fin.read()
fin.close()

if jar_path_placeholder in ini:
    filedir = os.path.dirname(__file__)
    xform_jar_path = os.path.abspath(os.path.join(filedir,'..','..','lib'))
    ini = ini.replace(jar_path_placeholder, xform_jar_path)
    fin = open(local_ini,"w")
    fin.write(ini)
    fin.close()
    print "Updated %s with %s" % (local_ini, xform_jar_path)

