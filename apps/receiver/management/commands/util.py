""" Utility functions used by various xformmanager.management.commands """
import sys
import urllib, urllib2, httplib
import logging
import os.path
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
        pass
        #Windows always returns a 'file is in use' error when we try
        #to clean up after ourselves
        #process_folder(folder_name, os.remove)
        #os.rmdir(folder_name)
        
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

def submit_form(filename, destination_url):
    """ Submits a submission to a CommCareHQ server
    
    filename: name of submission file
    destination_url: server to submit to
    """
    fin = open(filename, "rb")
    # first line is the header dictionary
    dict_string = fin.readline()
    submit_dict = simplejson.loads(dict_string)
    # next line is empty
    fin.readline()
    # after that is everything else
    data = fin.read()
    fin.close()
    real_size = len(data)
    content_length = submit_dict['content-length']
    domain_name = submit_dict["domain"]
    if int(real_size) != int(content_length):
        print "form %s has mismatched size and content-length %s != %s" + \
              ", automatically fixing!" % (filename, real_size, content_length)
        submit_dict['content-length'] = real_size
    parsed_url = urlparse('http://%s/receiver/resubmit/%s' % (destination_url, domain_name))
    submit_dict["is_resubmission" ] =  "True" 
    submit_dict['User-Agent'] = 'CCHQ-submitfromfile-python-v0.1'
    try:
        #print "submitting from %s to: %s" % (filename, parsed_url.path)
        conn = httplib.HTTPConnection(parsed_url.netloc)
        conn.request('POST', parsed_url.path, data, submit_dict)
        resp = conn.getresponse()
        results = resp.read()
        if not "thank you" in results:
            print "unexpected response for %s\n%s" % (filename, results)
    except Exception, e:
        print"problem submitting form: %s" % filename 
        print e
        return None

def POST_file(buffer, url):
    # Create the form with simple fields
    form = MultiPartForm()
    # Add a fake file
    form.add_buffer('file', 'file', buffer=buffer)

    # Build the request
    request = urllib2.Request(url)
    request.add_header('User-agent', 'CommCareHQ')
    body = str(form)
    request.add_header('Content-type', form.get_content_type())
    request.add_header('Content-length', len(body))
    request.add_data(body)
    # outoing_data = request.get_data()
    urllib2.urlopen(request)
