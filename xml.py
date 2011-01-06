import logging

RESTOREDATA_TEMPLATE =\
"""<?xml version='1.0' encoding='UTF-8'?>
<restoredata>
<restore_id>%(restore_id)s</restore_id>%(registration)s%(case_list)s
</restoredata>
"""

# Response template according to 
# https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest

RESPONSE_TEMPLATE = \
'''<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
    <message>%(message)s</message>%(extra_xml)s
</OpenRosaResponse>'''

def get_response(message, extra_xml):
    return RESPONSE_TEMPLATE % {"message": message,
                                "extra_xml": extra_xml}
