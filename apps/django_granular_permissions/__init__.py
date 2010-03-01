from django.contrib.auth.models import User, Group
from models import Permission
import new
import inspect

class MetaClass(type):
    def __new__(self, classname, classbases, classdict):
        try:
            frame = inspect.currentframe()
            frame = frame.f_back
            if frame.f_locals.has_key(classname):
                old_class = frame.f_locals.get(classname)
                for name,func in classdict.items():
                    if inspect.isfunction(func):
                        setattr(old_class, name, func)
                return old_class
            return type.__new__(self, classname, classbases, classdict)
        finally:
            del frame

class MetaObject(object):
    __metaclass__ = MetaClass
            
class User(MetaObject):
    def add_row_perm(self, instance, perm):
        
# 20100118 RL
# Bug in this app's code - one can fail to have perms both because you don't have them, and
# because your account isn't active. If the latter, we definitely shouldn't be putting duplicate rows in.
# Short of copying/pasting code, the easiest thing to do is to skip the active test - implemented by
# modifying has_row_perm to take another param.        
    
        if self.has_row_perm(instance, perm, True, False):
            return False
        
        permission = Permission()
        permission.content_object = instance
        permission.user = self
        permission.name = perm
        permission.save()
        return True
        
    def del_row_perm(self, instance, perm):
        if not self.has_row_perm(instance, perm, True):
            return False
        
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(user=self, content_type__pk=content_type.id, object_id=instance.id, name=perm)
        objects.delete()
        return True
        
    def has_row_perm(self, instance, perm, only_me=False, do_active_test=True):
        if self.is_superuser:
            return True
        
        if do_active_test:
            if not self.is_active:
                return False

        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(user=self, content_type__pk=content_type.id, object_id=instance.id, name=perm)
        if objects.count()>0:
            return True
            
        # check groups
        if not only_me:
            for group in self.groups.all():
                if group.has_row_perm(instance, perm):
                    return True
        return False
        
    def get_rows_with_permission(self, instance, perm):
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Q
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(Q(user=self) | Q(group__in=self.groups.all()), content_type__pk=content_type.id, name=perm)
        return objects
        
            
class Group(MetaObject):
    def add_row_perm(self, instance, perm):
        if self.has_row_perm(instance, perm):
            return False
        permission = Permission()
        permission.content_object = instance
        permission.group = self
        permission.name = perm
        permission.save()
        return True
        
    def del_row_perm(self, instance, perm):
        if not self.has_row_perm(instance, perm):
            return False
        
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(instance)
# Change to this row prompted by bug report at:
# http://github.com/ryates/django-granular-permissions-redux/issues#issue/4
        objects = Permission.objects.filter(group=self, content_type__pk=content_type.id, object_id=instance.id, name=perm)
        objects.delete()
        return True
        
    def has_row_perm(self, instance, perm):
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(group=self, content_type__pk=content_type.id, object_id=instance.id, name=perm)
        if objects.count()>0:
            return True
        else:
            return False
            
    def get_rows_with_permission(self, instance, perm):
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(group=self, content_type__pk=contet_type.id, name=perm)
        return objects
        
