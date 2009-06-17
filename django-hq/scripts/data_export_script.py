#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import settings 
from django.core.management import setup_environ
import os
import json

# this script walks through all the submissions and bundles them 
# in an exportable format with the original submitting IP and 
# time, as well as a reference to the original post
setup_environ(settings)
from receiver.models import Submission
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
    #print pickled
    fout.write(jsoned)
    fout.write("\n\n")
    payload = post_file.read()
    fout.write(payload)
    fout.close()
        
