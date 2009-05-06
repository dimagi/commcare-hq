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
#        if line.count('http://www.commcare.org/MVP/pf/safe_motherhood/registration_v0.1') > 0:
#                        line= line.replace('http://www.commcare.org/MVP/pf/safe_motherhood/registration_v0.1',
#                                'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_batch_registration_0.0.2a')
#                        
#        if line.count('http://www.commcare.org/MVP/pf/safe_motherhood/followup_v0.1') > 0:
#                        line = line.replace('http://www.commcare.org/MVP/pf/safe_motherhood/followup_v0.1',
#                                            'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_follow_0.0.2a')
#        
#        if line.count('http://www.commcare.org/MVP/pf/safe_motherhood/referral_v0.1') > 0:
#                        line = line.replace('http://www.commcare.org/MVP/pf/safe_motherhood/referral_v0.1',
#                                            'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_resolution_0.0.2a')
#        
        
        if line.count('<pathfinder_registration') > 0:
            line= line.replace('http://dev.commcarehq.org/Pathfinder/pathfinder_cc_batch_registration_0.0.2a',
                                'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_registration_0.0.2a')
            
        
        elif line.count('<pathfinder_followup>') > 0:
            line = line.replace('<pathfinder_followup>',
                                '<pathfinder_followup xmlns="http://dev.commcarehq.org/Pathfinder/pathfinder_cc_follow_0.0.2a">')            
        
#        elif line.count('<pathfinder_referral>') > 0:
#            line = line.replace('<pathfinder_referral>',
#                                '<pathfinder_referral xmlns="http://www.commcare.org/MVP/pf/safe_motherhood/referral_v0.1">')

        elif line.count('<pathfinder_referral') > 0:
            line = line.replace('http://www.commcare.org/MVP/pf/safe_motherhood/referral_v0.1',
                                    'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_resolution_0.0.2a')            

        
        fout.write(line)
        
    fout.close()

    
