from submitlogger.models import *
from submitlogger import submitprocessor

bodyfile = 'multipart-body.txt'
headerfile = 'multipart-meta.txt'

print 'submitting'
newsubmit = SubmitLog()
fin = open(os.path.join(os.path.dirname(__file__),headerfile),"r")
meta= fin.read()
fin.close()

fin = open(os.path.join(os.path.dirname(__file__),bodyfile),"rb")
body = fin.read()
fin.close()

metahash = eval(meta)
submitprocessor.do_raw_submission(metahash, body)