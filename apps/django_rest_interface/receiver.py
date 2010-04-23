"""
MORE INFO AT: http://code.google.com/p/django-rest-interface/wiki/RestifyDjango
Data format classes that can be plugged into 
model_resource.ModelResource and determine how submissions
of model data need to look like (e.g. form submission MIME types,
XML, JSON, ...).
"""
from django.core import serializers
from django.forms import model_to_dict

class InvalidFormData(Exception):
    """
    Raised if form data can not be decoded into key-value
    pairs.
    """

class Receiver(object):
    """
    Base class for all "receiver" data format classes.
    All subclasses need to implement the method
    get_data(self, request, method).
    """
    def get_data(self, request, method):
        raise Exception("Receiver subclass needs to implement get_data!")
    
    def get_post_data(self, request):
        return self.get_data(request, 'POST')
    
    def get_put_data(self, request):
        return self.get_data(request, 'PUT')

class FormReceiver(Receiver):
    """
    Data format class with standard Django behavior: 
    POST and PUT data is in form submission format.
    """
    def get_data(self, request, method):
        return getattr(request, method)

class SerializeReceiver(Receiver):
    """
    Base class for all data formats possible
    within Django's serializer framework.
    """
    def __init__(self, format):
        self.format = format
    
    def get_data(self, request, method):
        try:
            deserialized_objects = list(serializers.deserialize(self.format, request.raw_post_data))
        except serializers.base.DeserializationError:
            raise InvalidFormData
        if len(deserialized_objects) != 1:
            raise InvalidFormData
        model = deserialized_objects[0].object
        
        return model_to_dict(model)

class JSONReceiver(SerializeReceiver):
    """
    Data format class for form submission in JSON, 
    e.g. for web browsers.
    """
    def __init__(self):
        self.format = 'json'

class XMLReceiver(SerializeReceiver):
    """
    Data format class for form submission in XML, 
    e.g. for software clients.
    """
    def __init__(self):
        self.format = 'xml'
