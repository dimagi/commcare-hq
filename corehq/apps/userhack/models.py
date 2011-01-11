#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.db.models.signals import class_prepared

# hackity hack:
# http://stackoverflow.com/questions/2610088/can-djangos-auth-user-username-be-varchar75-how-could-that-be-done

def longer_username(sender, *args, **kwargs):
    # You can't just do `if sender == django.contrib.auth.models.User`
    # because you would have to import the model
    # You have to test using __name__ and __module__
    if sender.__name__ == "User" and sender.__module__ == "django.contrib.auth.models":
        sender._meta.get_field("username").max_length = 128

class_prepared.connect(longer_username)