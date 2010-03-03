#!/usr/bin/env python

import random

# Tack this on to the end of the exiting domain fixture - just sets
# memberships up. OUTPUT OF THIS SCRIPT MUST BE APPENDED TO A DUMP
# THAT CONTAINS DOMAINS THEMSELVES! I typically generate this with
# a call to dump_database.py, then >> the output of this script to 
# that dump.

PK_OFFSET = 2 # will vary depending on how many users are set up

###############################################################

def gen_membership(domain, member_id, pk):
    s ="""
- fields: {{domain: %s, is_active: 1, member_id: %s, member_type: 15}}
  model: domain.membership
  pk: %s"""
    output = s % (domain, member_id, pk)
    return output

###############################################################
            
def main():
    random.seed(0) # Make this repeatable
    lis = [ gen_membership(random.randint(1,2), 
                           member_id,
                           member_id+PK_OFFSET) for member_id in range(1,157)]

    print ''.join(lis)
            
###############################################################

if __name__ == '__main__':
    main()
