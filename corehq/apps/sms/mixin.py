import re
from django.core.exceptions import ValidationError
from couchdbkit.ext.django.schema import *

phone_number_re = re.compile("^\d+$")

class VerifiedNumber(Document):
    """
    There should only be one VerifiedNumber entry per (owner_doc_type, owner_id), and
    each VerifiedNumber.phone_number should be unique across all entries.
    """
    owner_doc_type  = StringProperty()
    owner_id        = StringProperty()
    phone_number    = StringProperty()

class CommCareMobileContactMixin(object):
    """
    Defines a mixin to manage a mobile contact's information. This mixin must be used with
    a class which is a Couch Document.
    """
    
    def get_time_zone(self):
        """
        This method should be implemented by all subclasses of CommCareMobileContactMixin,
        and must return a string representation of the time zone. For example, "America/New_York".
        """
        raise NotImplementedError("Subclasses of CommCareMobileContactMixin must implement method get_time_zone().")
    
    def get_verified_number(self):
        """
        Retrieves this contact's verified number by (self.doc_type, self._id).
        
        return  the VerifiedNumber
        """
        v = VerifiedNumber.view("sms/verified_number_by_doc_type_id",
            startkey=[self.doc_type, self._id],
            endkey=[self.doc_type, self._id],
            include_docs=True
        ).one()
        return v
    
    def validate_number_format(self, phone_number):
        """
        Validates that the given phone number consists of all digits.
        
        return  void
        raises  ValidationError if the phone number format is invalid
        """
        if not phone_number_re.match(phone_number):
            raise ValidationError("Phone number format must consist of only digits.")
    
    def verify_unique_number(self, phone_number):
        """
        Verifies that the given phone number is not already in use by any other contacts.
        
        return  void
        raises  ValidationError if the phone number format is invalid
        raises  ValidationError if the phone number is already in use by another contact
        """
        self.validate_number_format(phone_number)
        v = VerifiedNumber.view("sms/verified_number_by_number",
            startkey=[phone_number],
            endkey=[phone_number],
            include_docs=True
        ).one()
        if v is not None and (v.owner_doc_type != self.doc_type or v.owner_id != self._id):
            raise ValidationError("Phone number is already in use.")
    
    def save_verified_number(self, phone_number):
        """
        Saves the given phone number as this contact's verified phone number.
        
        return  void
        raises  ValidationError if the phone number format is invalid
        raises  ValidationError if the phone number is already in use by another contact
        """
        self.verify_unique_number(phone_number)
        v = self.get_verified_number()
        if v is None:
            v = VerifiedNumber(
                owner_doc_type = self.doc_type,
                owner_id = self._id
            )
        v.phone_number = phone_number
        v.save()

    def delete_verified_number(self):
        """
        Deletes this contact's phone number from the verified phone number list, freeing it up
        for use by other contacts.
        
        return  void
        """
        v = self.get_verified_number()
        if v is not None:
            v.doc_type += "-Deleted"
            v.save()



