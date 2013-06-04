import six
import importlib

from tastypie.fields import ApiField
from corehq.apps.api.resources import dict_object

def get_referenced_class(class_or_str):
    # Simplified from https://github.com/toastdriven/django-tastypie/blob/master/tastypie/fields.py#L519

    if not isinstance(class_or_str, basestring):
        return class_or_str

    if '.' in class_or_str:
        module_bits = class_or_str.split('.')
        module_path, class_name = '.'.join(module_bits[:-1]), module_bits[-1]
        module = importlib.import_module(module_path)
    else:
        raise ImportError("The import path to a related resource must be asolute; this is not: '%s'." % class_or_str)

    clazz = getattr(module, class_name, None)
    
    if clazz is None:
        raise ImportError("Module '%s' does not appear to have a class called '%s'." % (module_path, class_name))
    
    return clazz


class ToManyDocumentsField(ApiField):
    '''
    A field that references multiple documents in the
    couch database. It does not necessarily refer to
    something with an API URI, though it should...

    (tastypie.fields.ToManyField requires the Django ORM)
    '''

    def use_if_requested(self, bundle):
        full_name = self.instance_name + '__full'
        return bundle.request.GET.get(full_name, 'false').lower() == 'true'

    def __init__(self, to, attribute, blank=False, readonly=False, unique=False, help_text=None):
        '''
        Note that most of these options are unused as of now...
        '''
        super(ToManyDocumentsField, self).__init__(attribute=attribute,
                                                   blank=blank,
                                                   help_text=help_text,
                                                   use_in=self.use_if_requested,
                                                   unique=unique,
                                                   readonly=readonly)
        self.to = to

    @property
    def to_class(self):
        if not hasattr(self, '_to_class'):
            self._to_class = get_referenced_class(self.to)

        return self._to_class

    @property
    def related_resource(self):
        return self.to_class() # Tastypie internals are a bit more complex; it may or may not bite us that we do not share the complexity

    def dehydrate(self, bundle, for_list=True):
        if isinstance(self.attribute, six.string_types):
            accessor = lambda v: getattr(v, self.attribute)
        else:
            accessor = self.attribute

        related_resource = self.related_resource

        hydrated = accessor(bundle.obj)

        if hydrated is None:
            return None

        dehydrated = [related_resource.full_dehydrate(related_resource.build_bundle(obj=obj, request=bundle.request)).data
                      for obj in hydrated]
        
        return dehydrated

        
class ToOneDocumentField(ApiField):
    '''
    A field that reference a single document in the couch database.
    It may or may not have a URI elsewhere in the API.

    (if this looks identical to the above that is because it is for now)
    '''

    def use_if_requested(self, bundle):
        full_name = self.instance_name + '__full'
        return bundle.request.GET.get(full_name, 'false').lower() == 'true'

    def __init__(self, to, attribute, blank=False, readonly=False, unique=False, help_text=None):
        '''
        Note that most of these options are unused as of now...
        '''
        super(ToOneDocumentField, self).__init__(attribute=attribute,
                                                   blank=blank,
                                                   help_text=help_text,
                                                   use_in=self.use_if_requested,
                                                   unique=unique,
                                                   readonly=readonly)
        self.to = to

    @property
    def to_class(self):
        if not hasattr(self, '_to_class'):
            self._to_class = get_referenced_class(self.to)

        return self._to_class

    @property
    def related_resource(self):
        return self.to_class() # Tastypie internals are a bit more complex; it may or may not bite us that we do not share the complexity

    def dehydrate(self, bundle, for_list=True):
        if isinstance(self.attribute, six.string_types):
            accessor = lambda v: getattr(v, self.attribute)
        else:
            accessor = self.attribute

        related_resource = self.related_resource

        hydrated = accessor(bundle.obj)
        
        if hydrated is None:
            return None

        dehydrated = related_resource.full_dehydrate(related_resource.build_bundle(obj=accessor(bundle.obj), request=bundle.request)).data

        return dehydrated

