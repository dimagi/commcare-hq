import bz2
import sys
import urllib, urllib2, httplib
import logging
import os.path
import cStringIO
import simplejson
from stat import S_ISDIR, S_ISREG, ST_MODE
from urlparse import urlparse
import tarfile

def are_you_sure():
    should_proceed = raw_input("Are you sure you want to proceed? (yes or no) ")
    if should_proceed != "yes":
        print "Ok, exiting."
        sys.exit()
    
def login(url, username, password):
    params = urllib.urlencode({'username': username, 'password': password})
    headers = {"Content-type": "application/x-www-form-urlencoded",
                "Accept": "text/plain"}
    conn = httplib.HTTPConnection(url)
    conn.request("POST", "/accounts/login/", params, headers)
    response = conn.getresponse()
    print "Attempting login using supplied credentials"
    print "Response: ", response.status, response.reason
    print "Response:  ", response.read()
    conn.close()
    # 302 (redirect) means login was successful
    if response.status == 302:
        return True
    else:
        return False

def extract_and_process(file_name, callback, *additional_args):
    """ Extracts a tar file and runs 'callback' on all files inside 
    
    file_name: tar file to extract
    callback: function to run on all files
    additional_args: optional, additional arguments for callback
    """
    folder_name = os.path.basename(file_name).split('.')[0]
    if os.path.exists(folder_name):
        print "This script will delete the folder" + \
              "'%s' and all its contents" % folder_name
        are_you_sure()
        process_folder(folder_name, os.remove)
        os.rmdir(folder_name)
    os.mkdir(folder_name)
    try:
        print "Extracting %s to %s" % (file_name, folder_name)
        if not tarfile.is_tarfile(file_name): raise Exception("Not a tarfile")
        tar = tarfile.open(file_name)
        tar.extractall(folder_name)
        tar.close()
        print "Extraction successful."

        process_folder(folder_name, callback, *additional_args)
    finally:
        process_folder(folder_name, os.remove)
        os.rmdir(folder_name)
        
def process_folder(folder_name, callback, *additional_arg):
    """ Runs 'callback' on all files inside folder_name
    
    folder_name: folder to process
    callback: function to run on all files
    additional_args: optional, additional arguments for callback
    """
    for filename in os.listdir(folder_name):
        pathname = os.path.join (folder_name, filename)
        mode = os.stat(pathname)[ST_MODE]
        if S_ISDIR(mode):
            # Ignore subfolders
            continue
        elif S_ISREG(mode):
            # It's a file, call the callback function
            print "%s %s" % (callback, pathname)
            callback(pathname, *additional_arg)

def get_stack_diff(small_stack, big_stack):
    # compare the list of received MD5's with the local mD5
    counter_small = 0
    counter_big = 0
    results = []
    while True:
        if counter_small == len(small_stack):
            results.extend(big_stack[counter_big:])
            break
        if counter_big == len(big_stack):
            # Reached the end of the list of local submissions before reaching
            # the end of received mD5s. This should really never happen. 
            # But might, if you were syncing with two different cchq servers.
            logging.warn("Local submission count less than received submission count!")
            break
        if small_stack[counter_small] == big_stack[counter_big]:
            counter_small = counter_small + 1
            counter_big = counter_big + 1
        elif small_stack[counter_small] > big_stack[counter_big]:
            # found an entry in local which is not in received
            results.append( big_stack[counter_big] )
            counter_big = counter_big + 1
        else:
            # found an entry in received which is not in local
            # skip it
            logging.error("Skipping unrecognized received MD5!")
            counter_small = counter_small + 1
    return results

def bz2_to_list(buffer):
    string_of_values = bz2.decompress(buffer)
    stream_of_values = cStringIO.StringIO(string_of_values)
    list_ = []
    line = stream_of_values.readline()
    while len(line)>0:
        # assume we receive an ordered list of MD5
        list_.append( line.strip() )
        line = stream_of_values.readline()
    return list_

        
def get_field_as_bz2(django_model, field_name, debug=False):
    """ generate a string with all MD5s.
    Some operations require a buffer...
    
    django_model - django model with a 'target_namespace' property
                   which we will POST in a tarfile
    """
    string = cStringIO.StringIO()
    if not debug:
        objs = django_model.objects.all().order_by(field_name)
    else:
        print "DEBUG MODE: Only generating some schemata"
        # arbitrarily return only 10 of the MD5s
        objs = django_model.objects.all().order_by(field_name)[:5]
    for obj in objs:
        string.write(unicode( getattr(obj, field_name) ) + '\n')
    return bz2.compress(string.getvalue())