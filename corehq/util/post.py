from urlparse import urlparse
import httplib
import subprocess
import tempfile
from subprocess import PIPE


def post_data(data, url,curl_command="curl", use_curl=False,
                  content_type = "text/xml"):
    """Do a POST of data with some options."""     
    file = tempfile.TemporaryFile()
    tmp_file_path = tempfile.TemporaryFile().name
    tmp_file = open(tmp_file_path, "w")
    tmp_file.write(data)
    tmp_file.close()
    return post_file(tmp_file_path, url, curl_command, use_curl, content_type)
    
def post_file(filename, url,curl_command="curl", use_curl=False,
              content_type = "text/xml"):
    """Do a POST from file with some options."""     
    up = urlparse(url)
    dict = {}
    results = None
    errors = None
    try:
        f = open(filename, "rb")
        data = f.read()
        dict["content-type"] = content_type
        dict["content-length"] = len(data)
        if use_curl:
            p = subprocess.Popen([curl_command,
                                  '--header','Content-type:%s' % content_type, 
                                  '--header','"Content-length:%s' % len(data), 
                                  '--data-binary', '@%s' % filename, 
                                  '--request', 'POST', 
                                  url],
                                  stdout=PIPE,stderr=PIPE,shell=False)
            errors = p.stderr.read()
            results = p.stdout.read()
        else:
            conn = httplib.HTTPConnection(up.netloc)
            conn.request('POST', up.path, data, dict)
            resp = conn.getresponse()
            results = resp.read()
    except Exception, e:
        errors = str(e)
    return (results,errors)
    
        
print post_file(r"C:\Users\czue\Desktop\schema_moz_moz_sarahdemo_2_2010-06-11_23-26-11.xml",
          "http://datahq.org/receiver/submit/moz")