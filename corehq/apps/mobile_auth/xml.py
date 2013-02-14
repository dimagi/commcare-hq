"""
    This file contains the spec for the XML for mobile auth
    (from https://bitbucket.org/commcare/commcare/wiki/CentralAuthAPI)

    <!-- Exactly one. The block of auth key records.-->
    <!-- @domain: Exactly one. The client should only accept keys from domains that match the request -->
    <!-- @issued: Exactly one. An ISO8601 timestamp from the server which denotes the date and time that the key requests were processed. This is the value that should be provided as the {{{last_issued}}} parameter to future requests. -->
    <auth_keys domain="" issued="">
        <!-- At Least One: A record for a key that the authenticating user has access to -->
        <!-- @valid:  Exactly one - The first date on which this key should be trusted -->
        <!-- @expires:  At Most one - A date on which the key was supplanted. If expires is not present, the phone will assume that it is currently valid -->
        <key_record valid="" expires="">
            <!-- Exactly One: A unique ID for this key. The same key record can be issued to multiple users (for superuser functions, etc). -->
            <!-- @title: At most one. An optional description of the sandbox, to allow differentiating between different datastores -->
            <uuid title=""/>
            <!-- Exactly One: The key content. Should be Base64 Encoded -->
            <!-- @type: Exactly one. The type of key being shared. Currently only AES256 is supported as either (AES, AES256) -->
            <key type=""/>
        </key_record>
    </auth_keys>
"""
from datetime import datetime
from eulxml.xmlmap import XmlObject, StringField, DateTimeField, NodeListField, NodeField

def CustomDateTimeField(*args, **kwargs):
    return DateTimeField(format='%Y-%m-%dT%H:%M:%SZ', *args, **kwargs)

class KeyRecord(XmlObject):
    ROOT_NAME = 'key_record'
    valid = CustomDateTimeField('@valid', required=True)
    expires = CustomDateTimeField('@expires', required=False)

    uuid = StringField('uuid', required=True)
    type = StringField('key/@type', choices=['AES256'], required=True)
    key = StringField('key', required=True)

class AuthKeys(XmlObject):
    ROOT_NAME = 'auth_keys'
    domain = StringField('@domain', required=True)
    issued = CustomDateTimeField('@issued', required=True)

    key_records = NodeListField('key_record', KeyRecord, required=True)

class OpenRosaResponse(XmlObject):
    ROOT_NAME = 'OpenRosaResponse'

    xmlns = StringField('@xmlns')
    message_nature = StringField('message/@nature')
    message = StringField('message')

    auth_keys = NodeField('auth_keys', AuthKeys)

    def __init__(self, *args, **kwargs):
        super(OpenRosaResponse, self).__init__(*args, **kwargs)
        self.xmlns = 'http://openrosa.org/http/response'
        self.message_nature = 'submit_success'
