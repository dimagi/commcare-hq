#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import hashlib
import random
import threading

from django.core.management import execute_manager
import sys, os

filedir = os.path.dirname(__file__)
sys.path.append(os.path.join(filedir))
sys.path.append(os.path.join(filedir,'apps'))
sys.path.append(os.path.join(filedir,'submodules'))
sys.path.append(os.path.join(filedir,'submodules','casexml-src'))
sys.path.append(os.path.join(filedir,'submodules','core-hq-src'))
sys.path.append(os.path.join(filedir,'submodules','core-hq-src','corehq'))
sys.path.append(os.path.join(filedir,'submodules','core-hq-src','lib'))
sys.path.append(os.path.join(filedir,'submodules','couchforms-src'))
sys.path.append(os.path.join(filedir,'submodules','couchexport-src'))
sys.path.append(os.path.join(filedir,'submodules','couchlog-src'))
sys.path.append(os.path.join(filedir,'submodules','djangocouch-src'))
sys.path.append(os.path.join(filedir,'submodules','django-soil-src'))
sys.path.append(os.path.join(filedir,'submodules','dimagi-utils-src'))
sys.path.append(os.path.join(filedir,'submodules','formtranslate-src'))
sys.path.append(os.path.join(filedir,'submodules','receiver-src')) 
sys.path.append(os.path.join(filedir,'submodules','auditcare-src'))
sys.path.append(os.path.join(filedir,'submodules','commcare-translations'))
sys.path.append(os.path.join(filedir,'submodules','langcodes'))
sys.path.append(os.path.join(filedir,'submodules','sofabed-src'))
sys.path.append(os.path.join(filedir,'submodules','touchforms-src'))
sys.path.append(os.path.join(filedir,'submodules','django-digest-src'))
sys.path.append(os.path.join(filedir,'submodules','python-digest'))
sys.path.append(os.path.join(filedir,'submodules','phonelog'))
sys.path.append(os.path.join(filedir,'submodules','pathfinder-reports'))
sys.path.append(os.path.join(filedir,'submodules','hsph-reports'))
sys.path.append(os.path.join(filedir,'submodules','pathindia-reports'))
sys.path.append(os.path.join(filedir,'submodules','payments'))
sys.path.append(os.path.join(filedir,'submodules','dca-reports'))
sys.path.append(os.path.join(filedir,'submodules','couchdbkit-debugpanel-src'))
sys.path.append(os.path.join(filedir,'submodules','hutch-src'))
sys.path.append(os.path.join(filedir,'submodules','cchq-load-testing'))
sys.path.append(os.path.join(filedir,'submodules','a5288-reports'))

try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

#def monkey_patch_couchdbkit():
#    from dimagi.utils.make_uuid import random_hex
#    from couchdbkit.schema import Document
#    def randstate():
#        return hashlib.md5(str(random.getstate())).hexdigest()
#    def save(self, *args, **kwargs):
#        if '_id' not in self:
#            self._id = random_hex() + str(os.getpid())
#            if self.doc_type == "ExceptionRecord":
#                print self._id, self.message, randstate(), os.getpid()
#        self._old_save(*args, **kwargs)
#    Document._old_save = Document.save
#    Document.save = save

if __name__ == "__main__":
#    monkey_patch_couchdbkit()
    execute_manager(settings)
