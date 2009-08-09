None
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
# simple json is a python 2.5 library you need to install
import json
# json comes bundled with python 2.6.  use one or the other
#import json


def run():
    print "starting"
    from receiver.models import Submission
    from xformmanager.models import FormDefModel
    # this part of the script walks through all the registered
    # form definitions and bundles them with the original xsd
    # schema for resubmission
   
    domain = None
    # you can manually set a single domain here.  if you don't then
    # all the data will be exported.
    domain = "Grameen"
    if domain:
        all_schemas = FormDefModel.objects.filter(domain__name__iexact=domain)
    else:
        all_schemas = FormDefModel.objects.all()
 
    for schema in all_schemas:
        print "processsing %s" % schema
        file_loc = schema.xsd_file_location
        print "xsd file: %s" % file_loc
        if file_loc:
            headers = {
                "original-submit-time" : str(schema.submit_time),
                "original-submit-ip" : str(schema.submit_ip),
                "bytes-received" : schema.bytes_received,
                "form-name" : schema.form_name,
                "form-display-name" : schema.form_display_name,
                "target-namespace" : schema.target_namespace,
                "date-created" : str(schema.date_created),
                "domain" : str(schema.get_domain)
                }
            
    
            dir, filename = os.path.split(file_loc)
            new_dir = os.path.join(dir, "export")
            if not os.path.exists(new_dir):
                os.makedirs(new_dir)
            write_file = os.path.join(new_dir, filename.replace(".xml", ".xsdexport"))
            fout = open(write_file, 'w')
            jsoned = json.dumps(headers)
            print jsoned
            fout.write(jsoned)
            fout.write("\n\n")
            xsd_file = open(file_loc, "r")
            payload = xsd_file.read()
            xsd_file.close() 
            fout.write(payload)
            fout.close()
            
        
    # this part of the script walks through all the submissions 
    # and bundles them in an exportable format with the original 
    # submitting IP and time, as well as a reference to the 
    # original post
    #all_submissions = Submission.objects.all()
    if domain:
        all_submissions = Submission.objects.filter(domain__name__iexact=domain)
    else:
        all_submissions = Submission.objects.all()
    for submission in all_submissions:
        #print "processing %s (%s)" % (submission,submission.raw_post)
        post_file = open(submission.raw_post, "r")
        submit_time = str(submission.submit_time)
        # first line is content type
        content_type = post_file.readline().split(":")[1].strip()
        # second line is content length
        content_length = post_file.readline().split(":")[1].strip()
        # third line is empty
        post_file.readline()
        # the rest is the actual body of the post
        headers = { "content-type" : content_type, 
                    "content-length" : content_length,
                    "time-received" : str(submission.submit_time),
                    "original-ip" : str(submission.submit_ip),
                    "domain" : submission.domain.name
                   }
    
        # check the directory and create it if it doesn't exist
        dir, filename = os.path.split(submission.raw_post)
        new_dir = os.path.join(dir, "export")
        if not os.path.exists(new_dir):
            os.makedirs(new_dir)
        # the format will be:
        # {headers} (dict)
        #           (empty line)
        # <body>   
        write_file = os.path.join(new_dir, filename.replace("postdata", "postexport"))
        fout = open(write_file, 'w')
        jsoned = json.dumps(headers)
        fout.write(jsoned)
        fout.write("\n\n")
        try:
            payload = post_file.read()
            fout.write(payload)
        except Exception:
            print "error processing %s" % write_file
        fout.close()
    print "done"
            
