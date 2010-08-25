NOTE FROM ROSS: 

Code is from: http://github.com/ryates/django-granular-permissions-redux.
Looks like a fork of the (seemingly unmaintained) version at code.google.com.
Note that this code monkeypatches User and Group in __init__.py

########################################################################################################

Django Granular Permissions allow you to setup per-row permissions.

This project is injecting new methods into Django's auth.User and auth.Group in a non-invasive way (doesn't require modifying Django's code).

Simple permission checks within views and templates with templatetags.

You just simply have to install django-granular-permissions somewhere on your PYTHONPATH and add 'django_granular_permissions' to your installed apps and invoke

python manage.py syncdb

Note: superusers will always have True returned on has_row_perm(), also not active users will always get False

Example:

# adding permission 'edit' to a user 'Bart' on an instance of a MyObject from myapp.models
>>> from django.contrib.auth.models import User, Group
>>> from myapp.models import MyObject
>>> user = User.objects.get(username='Bart')
>>> obj = MyObject()
>>> obj.save()
>>> user.add_row_perm(obj, 'edit')
>>> user.has_row_perm(obj, 'edit')
True
>>> user.has_row_perm(obj, 'delete')
False 

# similar for groups
>>> group = Group.objects.get(pk=1) # get first group in the db
>>> group.add_row_perm(obj, 'read')

# now we'll add the user to the group and he will inherit the 'read' permission
>>> user.groups.add(group)
>>> user.has_row_perm(obj, 'read')
True

# now to remove permission
>>> user.del_row_perm(obj, 'edit')
>>> user.has_row_perm(obj, 'edit')
False

# note that when you try to remove a permission from a user that is granted to him through group nothing changes
>>> user.del_row_perm(obj, 'read')
>>> user.has_row_perm(obj, 'read')
True

