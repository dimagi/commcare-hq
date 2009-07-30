import os
import string
from random import choice
import random
import time
from datetime import timedelta


files = os.listdir('.')

for fname in files:
    if not fname.endswith('.xml'):
        continue
    print "Putting namespace " + fname
    fin = open(fname,'r')
    lines = fin.readlines()
    fin.close()

    fout = open(fname,'w')
    for line in lines:
        #if line.count('<brac>') > 0:
        line = line.replace('<brac xmlns="http://www.commcare.org/BRAC/CHW/CHWVisit_v0.0.1">',
                                '<brac xmlns="http://dev.commcarehq.org/BRAC/CHW/CHWVisit_v0.0.1">')
        
        fout.write(line)
        
    fout.close()

    
