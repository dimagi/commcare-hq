
class SubmitRecord(object):
    '''A simple data class for holding some metadata about a submission'''
    
    # these should probably be encapsulated, but it's such a simple classs....
    content_type = ""
    content_length = ""
    guid = ""
    checksum = ""
    file_name = ""
    
    def __init__(self, content_type, content_length, guid, checksum, file_name):
        self.content_type = content_type
        self.content_length = content_length
        self.guid = guid
        self.checksum = checksum
        self.file_name = file_name
        
    def __unicode__(self):
        return "Content_type: " + unicode(self.content_type) + \
               "\n content_length: " + unicode(self.content_length) + \
               "\n guid: " + unicode(self.guid) + \
               "\n checksum: " + unicode(self.checksum) + \
               "\n file_name: " + unicode(self.file_name)

    def __str__(self):
        return unicode(self).encode('utf-8')