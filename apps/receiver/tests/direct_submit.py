from receiver.models import *
from receiver import submitprocessor

bodyfile = 'multipart-body.txt'
headerfile = 'multipart-meta.txt'

#print 'submitting'
newsubmit = Submission()
fin = open(os.path.join(os.path.dirname(__file__),headerfile),"r")
meta= fin.read()
fin.close()

fin = open(os.path.join(os.path.dirname(__file__),bodyfile),"rb")
body = fin.read()
fin.close()

metahash = eval(meta)
submit_record = submitprocessor.save_post(metahash, body)
submitprocessor.do_submission_processing(metahash, submit_record)