#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

"""
The sole purpose of the following script is to update the
local.ini file used by the dimagi teamcity buildserver
so that xform_translate_path gets updated to point to the folder 
{project.dir}/lib

"""
JAR_PATH_SETTING = 'xform_translate_path'

import sys, os
if 'RAPIDSMS_INI' not in os.environ:
    print "RAPIDSMS_INI NOT FOUND"
    sys.exit()
local_ini = os.environ['RAPIDSMS_INI']

filedir = os.path.dirname(__file__)
xform_jar_path = os.path.abspath(os.path.join(filedir,'..','..','lib'))
ini = ""
should_update = False
fin = open(local_ini,"r")
for line in fin:
    if JAR_PATH_SETTING in line:
        line = 'xform_translate_path=%s\n' % xform_jar_path
        should_update = True
    ini = ini + line
fin.close()

if should_update:
    fin = open(local_ini,"w")
    fin.write(ini)
    fin.close()
    print "Updated %s with %s" % (local_ini, xform_jar_path)
else:
    print "Nothing to update"

