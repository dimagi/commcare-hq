#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file has been automatically generated, changes may be lost if you
# go and generate it again. It was generated with the following command:
# ./manage.py dumpscript

import datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType

def run():
    from django.contrib.sites.models import Site

    django_site_1 = Site.objects.all()[0]
    django_site_1.domain = u'localhost:8000'
    django_site_1.name = u'localhost:8000'
    django_site_1.save()

    from corehq.apps.domain.models import Domain

    domain_domain_1 = Domain()
    domain_domain_1.name = u'test'
    domain_domain_1.is_active = True
    domain_domain_1.save()

    from django.contrib.auth.models import User

    auth_user_1 = User()
    auth_user_1.username = u'admin'
    auth_user_1.first_name = u''
    auth_user_1.last_name = u''
    auth_user_1.email = u'test@test.com'
    auth_user_1.password = u'sha1$f8d4b$b6d2f6431c423687c227ad261caa46faaf16917d'
    auth_user_1.is_staff = True
    auth_user_1.is_active = True
    auth_user_1.is_superuser = True
    auth_user_1.last_login = datetime.datetime(2010, 9, 10, 14, 40, 30, 501416)
    auth_user_1.date_joined = datetime.datetime(2010, 9, 10, 14, 37, 22, 677987)
    auth_user_1.save()

    auth_user_2 = User()
    auth_user_2.username = u'test'
    auth_user_2.first_name = u'test'
    auth_user_2.last_name = u'test'
    auth_user_2.email = u'test@test.com'
    auth_user_2.password = u'sha1$f09cf$551ac80804020ad3e1d9943a583ee1ea52284797'
    auth_user_2.is_staff = False
    auth_user_2.is_active = True
    auth_user_2.is_superuser = False
    auth_user_2.last_login = datetime.datetime(2010, 9, 10, 14, 40, 53, 818764)
    auth_user_2.date_joined = datetime.datetime(2010, 9, 10, 19, 40, 6, 159442)
    auth_user_2.save()

    couch_user = auth_user_2.get_profile().get_couch_user()
    couch_user.add_domain_membership(domain_domain_1.name)
    couch_user.save()

    from corehq.apps.domain.models import RegistrationRequest

    domain_registration_request_1 = RegistrationRequest()
    domain_registration_request_1.tos_confirmed = True
    domain_registration_request_1.request_time = datetime.datetime(2010, 9, 10, 19, 40, 6, 159442)
    domain_registration_request_1.request_ip = '127.0.0.1'
    domain_registration_request_1.activation_guid = u'368ce6b8bd1311df932c5cff350164a3'
    domain_registration_request_1.confirm_time = datetime.datetime(2010, 9, 10, 14, 40, 25, 219783)
    domain_registration_request_1.confirm_ip = '127.0.0.1'
    domain_registration_request_1.domain = domain_domain_1
    domain_registration_request_1.new_user = auth_user_2
    domain_registration_request_1.requesting_user = None
    domain_registration_request_1.save()

