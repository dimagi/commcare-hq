
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
        
    def __str__(self):
        return "Content_type: " + str(self.content_type) + \
               "\n content_length: " + str(self.content_length) + \
               "\n guid: " + str(self.guid) + \
               "\n checksum: " + str(self.checksum) + \
               "\n file_name: " + str(self.file_name)