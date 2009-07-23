import os
import string
from random import choice
import random
import time
from datetime import timedelta


files = os.listdir('.')
usernames = ['brian','gayo','mobile1','mobile2','mobile3']



for fname in files:
    if not fname.endswith('.xml'):
        continue
    print "converting " + fname
    fin = open(fname,'r')
    lines = fin.readlines()
    fin.close()

    fout = open(fname,'w')
    for line in lines:
        if line.startswith('<username>'):
            fout.write('<username>%s</username>\n' %(choice(usernames)))
        elif line.startswith('<userid>'):
            fout.write('<userid>%s</userid>\n' %(choice(usernames)))

        elif line.startswith('<TimeStart>'):
            fout.write(line[0:11] + '2009' + line[15:])
        elif line.startswith('<TimeEnd>'):
            fout.write(line[0:9] + '2009' + line[13:])
        else:
            fout.write(line)
        
    fout.close()

    
