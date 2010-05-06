from django import VERSION
from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User, Group
from django.contrib import admin
from django_granular_permissions import MetaClass, MetaObject

if VERSION[0]=='newforms-admin' or VERSION[0]>0:
    class Permission(models.Model):
        name = models.CharField(max_length=16)
        content_type = models.ForeignKey(ContentType, related_name="row_permissions")
        object_id = models.PositiveIntegerField()
        content_object = generic.GenericForeignKey('content_type', 'object_id')
        user = models.ForeignKey(User, null=True)
        group = models.ForeignKey(Group, null=True)
        
        class Meta:
            verbose_name = 'permission'
            verbose_name_plural = 'permissions'
            
            
    class PermissionAdmin(admin.ModelAdmin):
        model = Permission
        list_display = ('content_type', 'user', 'group', 'name')
        list_filter = ('name',)
        search_fields = ['object_id', 'content_type', 'user', 'group']
        raw_id_fields = ['user', 'group']
        
        def __unicode__(self):
            return u"%s | %s | %d | %s" % (self.content_type.app_label, self.content_type, self.object_id, self.name)
    
    admin.site.register(Permission, PermissionAdmin)
else:
    class Permission(models.Model):
        name = models.CharField(max_length=16)
        content_type = models.ForeignKey(ContentType, related_name="row_permissions")
        object_id = models.PositiveIntegerField()
        content_object = generic.GenericForeignKey('content_type', 'object_id')
        user = models.ForeignKey(User, null=True, blank=True, raw_id_admin=True)
        group = models.ForeignKey(Group, null=True, blank=True, raw_id_admin=True)

        class Admin:
            list_display = ('content_type', 'user', 'group', 'name')
            list_filter = ('name',)
            search_fields = ['object_id', 'content_type', 'user', 'group']
        
        class Meta:
            verbose_name = 'permission'
            verbose_name_plural = 'permissions'
        
        def __unicode__(self):
            return u"%s | %s | %d | %s" % (self.content_type.app_label, self.content_type, self.object_id, self.name)
        


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
        
        content_type = ContentType.objects.get_for_model(instance)
# Change to this row prompted by bug report at:
# http://github.com/ryates/django-granular-permissions-redux/issues#issue/4
        objects = Permission.objects.filter(group=self, content_type__pk=content_type.id, object_id=instance.id, name=perm)
        objects.delete()
        return True
        
    def has_row_perm(self, instance, perm):
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(group=self, content_type__pk=content_type.id, object_id=instance.id, name=perm)
        if objects.count()>0:
            return True
        else:
            return False
            
    def get_rows_with_permission(self, instance, perm):
        content_type = ContentType.objects.get_for_model(instance)
        objects = Permission.objects.filter(group=self, content_type__pk=content_type.id, name=perm)
        return objects
        
