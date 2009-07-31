#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import sys, os
filedir = os.path.dirname(__file__)
sys.path.append('..')

sys.path.append(os.path.join(filedir))
sys.path.append(os.path.join(filedir,'apps'))
sys.path.append(os.path.join(filedir,'rapidsms'))
sys.path.append(os.path.join(filedir,'rapidsms','apps'))

#rapidsms lib stuff
sys.path.append(os.path.join(filedir,'rapidsms','lib'))
sys.path.append(os.path.join(filedir,'rapidsms','lib','rapidsms'))
sys.path.append(os.path.join(filedir,'rapidsms','lib','rapidsms','webui'))

  

import rapidsms

# these cannot go in local.ini since local.ini is not python
# cannot go in lib/rapidsms/webui/settings.py since that's rapidsms
# cannot go in a local settings.py because we would need to duplicate
# all thes ettings in lib/rapidsms/webui/settings.py, and at some point
# when rapidsms's settings.py diverges, we would start getting weird 
# errors because we have 2 settings
# we cannot include lib/rapidsms/webui/settings.py in a local settings.py
# either (or at least i haven't figured out how).
# so here's our intermediate hack
import os
root = os.path.dirname(__file__)
if not os.path.isdir(os.path.join(root,'data')):
    os.mkdir(os.path.join(root,'data'))
if not os.path.isdir(os.path.join(root,'data','submissions')):
    os.mkdir(os.path.join(root,'data','submissions'))
if not os.path.isdir(os.path.join(root,'data','attachments')):
    os.mkdir(os.path.join(root,'data','attachments'))
if not os.path.isdir(os.path.join(root,'data','schemas')):
    os.mkdir(os.path.join(root,'data','schemas'))

if __name__ == "__main__":
    #print "rapidsms'ing"
    #print sys.argv
    #os.environ["RAPIDSMS_INI"] = 'hqsetup.ini'
    os.environ["RAPIDSMS_HOME"] = os.path.abspath(os.path.dirname(__file__))
    rapidsms.manager.start(sys.argv)
