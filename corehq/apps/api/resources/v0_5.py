from django.core.urlresolvers import reverse
from tastypie.bundle import Bundle
from corehq.apps.api.resources import v0_1, v0_4
from corehq.apps.groups.models import Group
from corehq.apps.sms.util import strip_plus
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser


class CommCareUserResource(v0_1.CommCareUserResource):

    class Meta(v0_1.CommCareUserResource.Meta):
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None
        else:
            obj = bundle_or_obj

        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=obj.domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def _update(self, bundle):
        should_save = False
        for key, value in bundle.data.items():
            if key == 'phone_numbers' and getattr(bundle.obj, key, None) != value:
                bundle.obj.phone_numbers = []
                for idx, phone_number in enumerate(bundle.data.get('phone_numbers', [])):

                    bundle.obj.add_phone_number(strip_plus(phone_number))
                    if idx == 0:
                        bundle.obj.set_default_phone_number(strip_plus(phone_number))
                    should_save = True
            if key == 'groups' and getattr(bundle.obj, key, None) != value:
                bundle.obj.set_groups(bundle.data.get("groups", []))
                should_save = True
            elif getattr(bundle.obj, key, None) != value:
                setattr(bundle.obj, key, value)
                should_save = True
        return should_save

    def obj_create(self, bundle, request=None, **kwargs):
        try:
            bundle.obj = CommCareUser.create(domain=kwargs['domain'], username=bundle.data['username'],
                                             password=bundle.data['password'], email=bundle.data.get('email', ''))
            del bundle.data['password']
            self._update(bundle)
            bundle.obj.save()
        except Exception:
            bundle.obj.delete()
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = CommCareUser.get(kwargs['pk'])
        assert bundle.obj.domain == kwargs['domain']
        if self._update(bundle):
            assert bundle.obj.domain == kwargs['domain']
            bundle.obj.save()
        return bundle


class WebUserResource(v0_1.WebUserResource):

    class Meta(v0_1.WebUserResource.Meta):
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if isinstance(bundle_or_obj, Bundle):
            domain = bundle_or_obj.request.domain
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None

        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def _update(self, bundle):
        should_save = False
        for key, value in bundle.data.items():
            if key == 'phone_numbers' and getattr(bundle.obj, key, None) != value:
                bundle.obj.phone_numbers = []
                for idx, phone_number in enumerate(bundle.data.get('phone_numbers', [])):
                    bundle.obj.add_phone_number(strip_plus(phone_number))
                    if idx == 0:
                        bundle.obj.set_default_phone_number(strip_plus(phone_number))
                    should_save = True
            elif getattr(bundle.obj, key, None) != value:
                setattr(bundle.obj, key, value)
                should_save = True
        return should_save

    def obj_create(self, bundle, request=None, **kwargs):
        try:
            self._meta.domain = kwargs['domain']
            bundle.obj = WebUser.create(domain=kwargs['domain'], username=bundle.data['username'],
                                             password=bundle.data['password'], email=bundle.data.get('email', ''))
            del bundle.data['password']
            self._update(bundle)
            bundle.obj.save()
        except Exception:
            bundle.obj.delete()
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = WebUser.get(kwargs['pk'])
        assert kwargs['domain'] in bundle.obj.domains
        if self._update(bundle):
            assert kwargs['domain'] in bundle.obj.domains
            bundle.obj.save()
        return bundle


class GroupResource(v0_4.GroupResource):

    class Meta(v0_4.GroupResource.Meta):
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']

    def _update(self, bundle):
        should_save = False
        for key, value in bundle.data.items():
            if key == 'name' and getattr(bundle.obj, key, None) != value:
                if not Group.by_name(bundle.obj.domain, value):
                    setattr(bundle.obj, key, value)
                    should_save = True
                else:
                    raise Exception("A group with this name already exists")
            if key == 'users' and getattr(bundle.obj, key, None) != value:
                users_to_add = set(value) - set(bundle.obj.users)
                users_to_remove = set(bundle.obj.users) - set(value)
                for user in users_to_add:
                    bundle.obj.add_user(user)
                    should_save = True
                for user in users_to_remove:
                    bundle.obj.remove_user(user)
                    should_save = True
            elif getattr(bundle.obj, key, None) != value:
                setattr(bundle.obj, key, value)
                should_save = True
        return should_save

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None
        else:
            obj = bundle_or_obj
        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=obj.domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def obj_create(self, bundle, request=None, **kwargs):
        if not Group.by_name(kwargs['domain'], bundle.data.get("name")):
            bundle.obj = Group(bundle.data)
            bundle.obj.domain = kwargs['domain']
            bundle.obj.save()
            for user in bundle.obj.users:
                CommCareUser.get(user).set_groups([bundle.obj._id])
        else:
            raise Exception("A group with this name already exists")
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = Group.get(kwargs['pk'])
        assert bundle.obj.domain == kwargs['domain']
        if self._update(bundle):
            assert bundle.obj.domain == kwargs['domain']
            bundle.obj.save()
        return bundle
