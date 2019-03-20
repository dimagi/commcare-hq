'''
Fields for use in Tastypie Resources
'''

from __future__ import absolute_import
from __future__ import unicode_literals
import six

from tastypie.fields import ApiField, CharField
import dimagi.utils.modules

from corehq.util.python_compatibility import soft_assert_type_text


def get_referenced_class(class_or_str):
    # Simplified from https://github.com/toastdriven/django-tastypie/blob/master/tastypie/fields.py#L519

    if isinstance(class_or_str, six.string_types):
        soft_assert_type_text(class_or_str)
        return dimagi.utils.modules.to_function(class_or_str)
    else:
        return class_or_str


class AttributeOrCallable(object):

    def __init__(self, attribute):
        self.attribute = attribute

    def __call__(self, v):
        if isinstance(self.attribute, six.string_types):
            soft_assert_type_text(self.attribute)
            accessor = lambda v: getattr(v, self.attribute)
        else:
            accessor = self.attribute

        return accessor(v)


class UseIfRequested(object):
    '''
    Returns a field identical to the one provided in
    every way EXCEPT that this one will only appear in
    the API output if <fieldname>__full=true is passed
    on the querystring
    '''

    def __init__(self, underlying_field):
        self.underlying_field = underlying_field

    def use_in(self, bundle):
        full_name = self.instance_name + '__full'
        return bundle.request.GET.get(full_name, 'false').lower() == 'true'

    def __getattr__(self, attr):
        if attr == 'underlying_field':
            return None
        return getattr(self.underlying_field, attr)


class CallableApiField(ApiField):
    """
    A minor fix to Tastypie's ApiField to actually support callable attributes in general.
    """

    def dehydrate(self, bundle):
        if callable(self.attribute):
            return self.convert(self.attribute(bundle.obj))
        else:
            return super(CallableApiField, self).dehydrate(bundle)


class CallableCharField(CharField, CallableApiField):
    pass


class ToManyDocumentsField(ApiField):
    '''
    A field that references multiple documents in the
    couch database. It does not necessarily refer to
    something with an API URI, though it should...

    (tastypie.fields.ToManyField requires the Django ORM)
    '''

    def __init__(self, to, attribute, blank=False, readonly=False, unique=False, help_text=None):
        '''
        Note that most of these options are unused as of now...
        '''
        super(ToManyDocumentsField, self).__init__(attribute=attribute,
                                                   blank=blank,
                                                   help_text=help_text,
                                                   unique=unique,
                                                   readonly=readonly)
        self.to = to
        self.attribute = AttributeOrCallable(attribute)

    @property
    def to_class(self):
        if not hasattr(self, '_to_class'):
            self._to_class = get_referenced_class(self.to)

        return self._to_class

    @property
    def related_resource(self):
        return self.to_class() # Tastypie internals are a bit more complex; it may or may not bite us that we do not share the complexity

    def dehydrate(self, bundle, for_list=True):
        hydrated = self.attribute(bundle.obj)

        if hydrated is None:
            return None
        else:
            return [self.related_resource.full_dehydrate(self.related_resource.build_bundle(obj=obj, request=bundle.request)).data
                    for obj in hydrated]


class ToManyDictField(ApiField):
    '''
    A field that references multiple documents in the couch database.
    It assumes, for purposes of dehydrating correctly, that the documents
    are stored in a dictionary by e.g. ID, like so:
    {
        subcase_foo: <CommCareCase object>,
        subcase_bar: <CommCareCase object>
    }
    
    It does not necessarily refer to something with an API URI, though it should...

    (tastypie.fields.ToManyField requires the Django ORM)
    '''

    def __init__(self, to, attribute, blank=False, readonly=False, unique=False, help_text=None):
        super(ToManyDictField, self).__init__(attribute=attribute,
                                              blank=blank,
                                              help_text=help_text,
                                              unique=unique,
                                              readonly=readonly)
        self.to = to
        self.attribute = AttributeOrCallable(attribute)

    @property
    def to_class(self):
        if not hasattr(self, '_to_class'):
            self._to_class = get_referenced_class(self.to)

        return self._to_class

    @property
    def related_resource(self):
        return self.to_class() # Tastypie internals are a bit more complex; it may or may not bite us that we do not share the complexity

    def dehydrate(self, bundle, for_list=True):
        hydrated = self.attribute(bundle.obj)

        if hydrated is None:
            return None
        else:
            return dict([(key, self.related_resource.full_dehydrate(self.related_resource.build_bundle(obj=obj, request=bundle.request)).data)
                         for key, obj in hydrated.items()])


class ToManyListDictField(ApiField):
    '''
    A field that references multiple documents in the couch database
    that may be non-uniquely grouped by a particular key.
    It assumes, for purposes of dehydrating correctly, that the documents
    are stored in a dictionary by e.g. ID, like so:
    {
        <xform_id1>: [<XFormInstance object>, <XFormInstance object>, ...]
        <xform_id2>: [<XFormInstance object>, <XFormInstance object>, ...]
    }

    It does not necessarily refer to something with an API URI, though it should...

    (tastypie.fields.ToManyField requires the Django ORM)
    '''

    def __init__(self, to, attribute, blank=False, readonly=False, unique=False, help_text=None):
        super(ToManyListDictField, self).__init__(
            attribute=attribute,
            blank=blank,
            help_text=help_text,
            unique=unique,
            readonly=readonly
        )
        self.to = to
        self.attribute = AttributeOrCallable(attribute)

    @property
    def to_class(self):
        if not hasattr(self, '_to_class'):
            self._to_class = get_referenced_class(self.to)

        return self._to_class

    @property
    def related_resource(self):
        return self.to_class() # Tastypie internals are a bit more complex; it may or may not bite us that we do not share the complexity

    def dehydrate(self, bundle, for_list=True):
        hydrated = self.attribute(bundle.obj)

        if hydrated is None:
            return None
        else:
            return dict([
                (key, [self.related_resource.full_dehydrate(self.related_resource.build_bundle(obj=obj, request=bundle.request)).data
                       for obj in objlist])
                for key, objlist in hydrated.items()
            ])

        
class ToOneDocumentField(ApiField):
    '''
    A field that reference a single document in the couch database.
    It may or may not have a URI elsewhere in the API.
    '''

    def __init__(self, to, attribute, blank=False, readonly=False, unique=False, help_text=None):
        '''
        Note that most of these options are unused as of now...
        '''
        super(ToOneDocumentField, self).__init__(attribute=attribute,
                                                   blank=blank,
                                                   help_text=help_text,
                                                   unique=unique,
                                                   readonly=readonly)
        self.to = to
        self.attribute = AttributeOrCallable(attribute)

    @property
    def to_class(self):
        if not hasattr(self, '_to_class'):
            self._to_class = get_referenced_class(self.to)

        return self._to_class

    @property
    def related_resource(self):
        return self.to_class() # Tastypie internals are a bit more complex; it may or may not bite us that we do not share the complexity

    def dehydrate(self, bundle, for_list=True):
        hydrated = self.attribute(bundle.obj)

        if hydrated is None:
            return None
        else:
            return self.related_resource.full_dehydrate(self.related_resource.build_bundle(obj=hydrated, request=bundle.request)).data

