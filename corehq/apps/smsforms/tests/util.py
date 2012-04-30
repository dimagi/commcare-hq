class MockContact(object):
    """
    Mock contact implements the contact API
    """
    def __init__(self, id, username, language=""):
        self.get_id = id
        self.raw_username = username
        self.language = language
        
    def get_language_code(self):
        return self.language
