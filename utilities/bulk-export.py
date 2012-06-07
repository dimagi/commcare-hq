#!/usr/bin/env python
__author__ = 'tbauman'

# Setting section
FORMS_DIRECTORY = 'forms'
CASES_DIRECTORY = 'cases'
REPORT_FNAME = "%%s-%m-%d-%Y.xlsx"

import os, sys
import urllib2
from datetime import date

def auth_retrieve(username, password, url, destination):
    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, username, password)
    handler = urllib2.HTTPDigestAuthHandler(password_mgr)
    opener = urllib2.build_opener(handler)
    input = opener.open(url)
    output = open(destination, 'w')
    output.write(input.read())
    output.close()
    input.close()
    print "Downloaded", url, "to", destination

def main():
    """
    Pulls in exports
    """
    args = sys.argv[1:]
    domain = args.pop(0)
    root = args.pop(0)
    username = args.pop(0)
    password = args.pop(0)
    projects = args

    for project in projects:
        report_fname = date.today().strftime(REPORT_FNAME)
        url = "%s/a/%s/reports/download/cases" % (domain, project)
        dir = os.path.join(root, project)
        if not os.path.exists(dir):
            os.makedirs(dir)
        fname = os.path.join(dir, report_fname % 'cases')
        auth_retrieve(username, password, url, fname)
        url = "%s/a/%s/reports/export/forms/all/" % (domain, project)
        if not os.path.exists(dir):
            os.makedirs(dir)
        fname = os.path.join(dir, report_fname % 'forms')
        auth_retrieve(username, password, url, fname)
    print "Done!"

if __name__ == '__main__':
    main()