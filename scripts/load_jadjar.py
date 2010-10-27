from corehq.apps.app_manager.models import *

def run():
    jadjar = JadJar.new(open('CommCare.jad'), open('CommCare.jar'))
    print jadjar._id