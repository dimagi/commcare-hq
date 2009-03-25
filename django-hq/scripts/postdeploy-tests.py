import httplib
import os

from urllib import urlencode
from urllib2 import urlopen, Request,FileHandler
import urllib2, sys



def test_post_form(host,header_hash,body):
    h = httplib.HTTP(host)
    h.putrequest('POST','/formreceiver/submit/')
    for item in header_hash.keys():        
        if item == 'HTTP_CONTENT_TYPE':
            print header_hash[item]
            h.putheader("Content-type",str(header_hash[item]))    
            h.putheader("HTTP_Content-type",str(header_hash[item]))
        if item == 'HTTP_CONTENT_LENGTH':
            print header_hash[item]
            h.putheader("Content-length",header_hash[item])
            h.putheader('HTTP-Content-length',header_hash[item])
    h.endheaders()    
    h.send(body)
    errcode, errmsg, headers = h.getreply()    
    return h.file.read()

if __name__ == "__main__":    

   
    bodyfile = 'testdata/simple-body.txt'
    headerfile = 'testdata/simple-meta.txt'     
        
    fin = open(headerfile,"r")
    meta= fin.read()
    fin.close()
    
    fin = open(bodyfile,"r")
    body = fin.read()
    fin.close()
    
    print test_post_form('test.commcarehq.org',eval(meta),body)
     



#    #binary data don't work for httplib!!!!
#    bodyfile = 'testdata/multipart-body.txt'
#    headerfile = 'testdata/multipart-meta.txt'        
#    fin = open(headerfile,"r")
#    meta= fin.read()
#    fin.close()
#    
#    fin = open(bodyfile,"r")
#    body = fin.read()
#    fin.close()
#    #print test_post_form('localhost:8000',eval(meta), cbody)
#    
#
#    
#    opener = urllib2.build_opener(FileHandler)
#    header_hash = eval(meta)
#    headers = []
#    
#    for key in header_hash.keys():        
#        if key == 'HTTP_CONTENT_TYPE':
#            print header_hash[key]
#            headers.append(("Content-type",str(header_hash[key])))    
#            headers.append(("HTTP_Content-type",str(header_hash[key])))
#        if key == 'HTTP_CONTENT_LENGTH':
#            print header_hash[key]
#            headers.append(("Content-length",header_hash[key]))
#            headers.append(('HTTP-Content-length',header_hash[key]))    
#    
#    
#        
#    opener.addheaders = headers    
#    
#    a = opener.open('http://localhost:8000/formreceiver/submit/',body)
#    text = a.read()
#    print text
#    
#    req = urllib2.Request(url='http://localhost:8000/formreceiver/submit/')
    
    
    
    
    
    
    
    
    
    
