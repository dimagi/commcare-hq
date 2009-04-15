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
        if line.count('<pathfinder_registration>') > 0:
            line= line.replace('<pathfinder_registration>',
                                '<pathfinder_registration xmlns="http://www.commcare.org/MVP/safe_motherhood/registration_v0.1">')
            
        
        elif line.count('<pathfinder_followup>') > 0:
            line = line.replace('<pathfinder_followup>',
                                '<pathfinder_followup xmlns="http://www.commcare.org/MVP/safe_motherhood/followup_v0.1">')            
        
        elif line.count('<pathfinder_referral>') > 0:
            line = line.replace('<pathfinder_referral>',
                                '<pathfinder_referral xmlns="http://www.commcare.org/MVP/safe_motherhood/referral_v0.1">')            

        
        fout.write(line)
        
    fout.close()

    
