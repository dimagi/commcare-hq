None
#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file has been automatically generated, changes may be lost if you
# go and generate it again. It was generated with the following command:
# manage.py dumpscript

import datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType

def run():
    from django.contrib.auth.models import Group


    from django.contrib.auth.models import User

    auth_user_1 = User()
    auth_user_1.username = u'testadmin'
    auth_user_1.first_name = u''
    auth_user_1.last_name = u''
    auth_user_1.email = u'admin@dimagi.com'
    auth_user_1.password = u'sha1$f8636$9ce2327b480195f1c764ac05aad10dc1a106a58e'
    auth_user_1.is_staff = True
    auth_user_1.is_active = True
    auth_user_1.is_superuser = True
    auth_user_1.last_login = datetime.datetime(2009, 4, 22, 18, 9, 57)
    auth_user_1.date_joined = datetime.datetime(2009, 4, 15, 10, 30, 52)
    auth_user_1.save()

    from django.contrib.auth.models import Message


    from modelrelationship.models import EdgeType

    modelrelationship_edgetype_1 = EdgeType()
    modelrelationship_edgetype_1.directional = True
    modelrelationship_edgetype_1.name = u'is parent organization'
    modelrelationship_edgetype_1.description = u'Parent Organization'
    modelrelationship_edgetype_1.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edgetype_1.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edgetype_1.save()

    modelrelationship_edgetype_2 = EdgeType()
    modelrelationship_edgetype_2.directional = True
    modelrelationship_edgetype_2.name = u'has supervisors'
    modelrelationship_edgetype_2.description = u'Organization Supervisor'
    modelrelationship_edgetype_2.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edgetype_2.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edgetype_2.save()

    modelrelationship_edgetype_3 = EdgeType()
    modelrelationship_edgetype_3.directional = True
    modelrelationship_edgetype_3.name = u'has members'
    modelrelationship_edgetype_3.description = u'Organization Group Members'
    modelrelationship_edgetype_3.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edgetype_3.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edgetype_3.save()

    modelrelationship_edgetype_4 = EdgeType()
    modelrelationship_edgetype_4.directional = True
    modelrelationship_edgetype_4.name = u'is domain root'
    modelrelationship_edgetype_4.description = u'Domain Root'
    modelrelationship_edgetype_4.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edgetype_4.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edgetype_4.save()

    modelrelationship_edgetype_5 = EdgeType()
    modelrelationship_edgetype_5.directional = True
    modelrelationship_edgetype_5.name = u'User Chart Group'
    modelrelationship_edgetype_5.description = u'A User can have a root chart group linked to their login'
    modelrelationship_edgetype_5.child_type = ContentType.objects.get(app_label="dbanalyzer", model="graphgroup")
    modelrelationship_edgetype_5.parent_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edgetype_5.save()

    from modelrelationship.models import Edge

    modelrelationship_edge_1 = Edge()
    modelrelationship_edge_1.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_1.child_id = 3L
    modelrelationship_edge_1.relationship = modelrelationship_edgetype_1
    modelrelationship_edge_1.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_1.parent_id = 2L
    modelrelationship_edge_1.save()

    modelrelationship_edge_2 = Edge()
    modelrelationship_edge_2.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_2.child_id = 4L
    modelrelationship_edge_2.relationship = modelrelationship_edgetype_1
    modelrelationship_edge_2.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_2.parent_id = 2L
    modelrelationship_edge_2.save()

    modelrelationship_edge_3 = Edge()
    modelrelationship_edge_3.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_3.child_id = 9L
    modelrelationship_edge_3.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_3.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_3.parent_id = 3L
    modelrelationship_edge_3.save()

    modelrelationship_edge_4 = Edge()
    modelrelationship_edge_4.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_4.child_id = 7L
    modelrelationship_edge_4.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_4.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_4.parent_id = 1L
    modelrelationship_edge_4.save()

    modelrelationship_edge_5 = Edge()
    modelrelationship_edge_5.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_5.child_id = 8L
    modelrelationship_edge_5.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_5.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_5.parent_id = 1L
    modelrelationship_edge_5.save()

    modelrelationship_edge_6 = Edge()
    modelrelationship_edge_6.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_6.child_id = 3L
    modelrelationship_edge_6.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_6.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_6.parent_id = 1L
    modelrelationship_edge_6.save()

    modelrelationship_edge_7 = Edge()
    modelrelationship_edge_7.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_7.child_id = 10L
    modelrelationship_edge_7.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_7.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_7.parent_id = 3L
    modelrelationship_edge_7.save()

    modelrelationship_edge_8 = Edge()
    modelrelationship_edge_8.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_8.child_id = 5L
    modelrelationship_edge_8.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_8.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_8.parent_id = 4L
    modelrelationship_edge_8.save()

    modelrelationship_edge_9 = Edge()
    modelrelationship_edge_9.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_9.child_id = 6L
    modelrelationship_edge_9.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_9.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_9.parent_id = 4L
    modelrelationship_edge_9.save()

    modelrelationship_edge_10 = Edge()
    modelrelationship_edge_10.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_10.child_id = 1L
    modelrelationship_edge_10.relationship = modelrelationship_edgetype_4
    modelrelationship_edge_10.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_10.parent_id = 1L
    modelrelationship_edge_10.save()

    modelrelationship_edge_11 = Edge()
    modelrelationship_edge_11.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_11.child_id = 2L
    modelrelationship_edge_11.relationship = modelrelationship_edgetype_4
    modelrelationship_edge_11.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_11.parent_id = 2L
    modelrelationship_edge_11.save()

    modelrelationship_edge_12 = Edge()
    modelrelationship_edge_12.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_12.child_id = 5L
    modelrelationship_edge_12.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_12.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_12.parent_id = 3L
    modelrelationship_edge_12.save()

    modelrelationship_edge_13 = Edge()
    modelrelationship_edge_13.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_13.child_id = 5L
    modelrelationship_edge_13.relationship = modelrelationship_edgetype_4
    modelrelationship_edge_13.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_13.parent_id = 3L
    modelrelationship_edge_13.save()

    modelrelationship_edge_14 = Edge()
    modelrelationship_edge_14.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_14.child_id = 12L
    modelrelationship_edge_14.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_14.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_14.parent_id = 5L
    modelrelationship_edge_14.save()

    modelrelationship_edge_15 = Edge()
    modelrelationship_edge_15.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_15.child_id = 11L
    modelrelationship_edge_15.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_15.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_15.parent_id = 5L
    modelrelationship_edge_15.save()

    modelrelationship_edge_16 = Edge()
    modelrelationship_edge_16.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_16.child_id = 13L
    modelrelationship_edge_16.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_16.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_16.parent_id = 5L
    modelrelationship_edge_16.save()

    modelrelationship_edge_17 = Edge()
    modelrelationship_edge_17.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_17.child_id = 14L
    modelrelationship_edge_17.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_17.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_17.parent_id = 5L
    modelrelationship_edge_17.save()

    modelrelationship_edge_18 = Edge()
    modelrelationship_edge_18.child_type = ContentType.objects.get(app_label="dbanalyzer", model="graphgroup")
    modelrelationship_edge_18.child_id = 5L
    modelrelationship_edge_18.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_18.parent_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_18.parent_id = 5L
    modelrelationship_edge_18.save()

    modelrelationship_edge_19 = Edge()
    modelrelationship_edge_19.child_type = ContentType.objects.get(app_label="dbanalyzer", model="graphgroup")
    modelrelationship_edge_19.child_id = 1L
    modelrelationship_edge_19.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_19.parent_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_19.parent_id = 4L
    modelrelationship_edge_19.save()

    from monitorregistry.models import MonitorIdentity


    from monitorregistry.models import Hardware


    from monitorregistry.models import MonitorDevice


    from monitorregistry.models import MonitorGroup


    from organization.models import Domain

    organization_domain_1 = Domain()
    organization_domain_1.name = u'Pathfinder'
    organization_domain_1.description = u''
    organization_domain_1.save()

    organization_domain_2 = Domain()
    organization_domain_2.name = u'BRAC'
    organization_domain_2.description = u''
    organization_domain_2.save()

    organization_domain_3 = Domain()
    organization_domain_3.name = u'Grameen'
    organization_domain_3.description = u''
    organization_domain_3.save()

    from organization.models import OrganizationType

    organization_organizationtype_1 = OrganizationType()
    organization_organizationtype_1.name = u'NGO'
    organization_organizationtype_1.domain = organization_domain_1
    organization_organizationtype_1.description = u''
    organization_organizationtype_1.save()

    organization_organizationtype_2 = OrganizationType()
    organization_organizationtype_2.name = u'BRAC-Org'
    organization_organizationtype_2.domain = organization_domain_2
    organization_organizationtype_2.description = u''
    organization_organizationtype_2.save()

    organization_organizationtype_3 = OrganizationType()
    organization_organizationtype_3.name = u'Grameen-Intel'
    organization_organizationtype_3.domain = organization_domain_3
    organization_organizationtype_3.description = u''
    organization_organizationtype_3.save()

    from organization.models import ExtRole


    from organization.models import ExtUser

    organization_extuser_1 = ExtUser()
    organization_extuser_1.username = u'bracadmin'
    organization_extuser_1.first_name = u''
    organization_extuser_1.last_name = u''
    organization_extuser_1.email = u''
    organization_extuser_1.password = u'sha1$25e8d$45cfe119a9429d066168a20255f737dbffef6488'
    organization_extuser_1.is_staff = False
    organization_extuser_1.is_active = True
    organization_extuser_1.is_superuser = True
    organization_extuser_1.last_login = datetime.datetime(2009, 4, 15, 10, 33, 29)
    organization_extuser_1.date_joined = datetime.datetime(2009, 4, 15, 10, 33, 29)
    organization_extuser_1.primary_phone = u'+1112223333'
    organization_extuser_1.domain = organization_domain_2
    organization_extuser_1.identity = None
    organization_extuser_1.save()

    organization_extuser_2 = ExtUser()
    organization_extuser_2.username = u'pfadmin'
    organization_extuser_2.first_name = u''
    organization_extuser_2.last_name = u''
    organization_extuser_2.email = u''
    organization_extuser_2.password = u'sha1$223b5$7e92dfc51c7ae3ad5b0fd4df4b52396630e72406'
    organization_extuser_2.is_staff = False
    organization_extuser_2.is_active = True
    organization_extuser_2.is_superuser = True
    organization_extuser_2.last_login = datetime.datetime(2009, 4, 22, 18, 32, 45)
    organization_extuser_2.date_joined = datetime.datetime(2009, 4, 15, 10, 34, 6)
    organization_extuser_2.primary_phone = u'+2223334444'
    organization_extuser_2.domain = organization_domain_1
    organization_extuser_2.identity = None
    organization_extuser_2.save()

    organization_extuser_3 = ExtUser()
    organization_extuser_3.username = u'gradmin'
    organization_extuser_3.first_name = u''
    organization_extuser_3.last_name = u''
    organization_extuser_3.email = u''
    organization_extuser_3.password = u'sha1$f8df4$5339016289f029e23e14466e735a3e8cf016b57f'
    organization_extuser_3.is_staff = False
    organization_extuser_3.is_active = True
    organization_extuser_3.is_superuser = True
    organization_extuser_3.last_login = datetime.datetime(2009, 4, 22, 15, 37, 40)
    organization_extuser_3.date_joined = datetime.datetime(2009, 4, 15, 10, 34, 38)
    organization_extuser_3.primary_phone = u'+4445556666'
    organization_extuser_3.domain = organization_domain_3
    organization_extuser_3.identity = None
    organization_extuser_3.save()

    organization_extuser_4 = ExtUser()
    organization_extuser_4.username = u'brian'
    organization_extuser_4.first_name = u''
    organization_extuser_4.last_name = u''
    organization_extuser_4.email = u''
    organization_extuser_4.password = u'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
    organization_extuser_4.is_staff = False
    organization_extuser_4.is_active = True
    organization_extuser_4.is_superuser = True
    organization_extuser_4.last_login = datetime.datetime(2009, 4, 22, 18, 32, 10)
    organization_extuser_4.date_joined = datetime.datetime(2009, 4, 15, 10, 35, 1)
    organization_extuser_4.primary_phone = u'+1234567898'
    organization_extuser_4.domain = organization_domain_2
    organization_extuser_4.identity = None
    organization_extuser_4.save()

    organization_extuser_5 = ExtUser()
    organization_extuser_5.username = u'gayo'
    organization_extuser_5.first_name = u''
    organization_extuser_5.last_name = u''
    organization_extuser_5.email = u''
    organization_extuser_5.password = u'sha1$2aa9b$f8ce3e507b719c97d8442e518f8632c4454e686f'
    organization_extuser_5.is_staff = False
    organization_extuser_5.is_active = True
    organization_extuser_5.is_superuser = False
    organization_extuser_5.last_login = datetime.datetime(2009, 4, 15, 10, 35, 25)
    organization_extuser_5.date_joined = datetime.datetime(2009, 4, 15, 10, 35, 25)
    organization_extuser_5.primary_phone = u'+5554443333'
    organization_extuser_5.domain = organization_domain_2
    organization_extuser_5.identity = None
    organization_extuser_5.save()

    organization_extuser_6 = ExtUser()
    organization_extuser_6.username = u'pf1'
    organization_extuser_6.first_name = u''
    organization_extuser_6.last_name = u''
    organization_extuser_6.email = u''
    organization_extuser_6.password = u'test'
    organization_extuser_6.is_staff = False
    organization_extuser_6.is_active = True
    organization_extuser_6.is_superuser = False
    organization_extuser_6.last_login = datetime.datetime(2009, 4, 15, 10, 57, 13)
    organization_extuser_6.date_joined = datetime.datetime(2009, 4, 15, 10, 57, 13)
    organization_extuser_6.primary_phone = u'+1155312452'
    organization_extuser_6.domain = organization_domain_1
    organization_extuser_6.identity = None
    organization_extuser_6.save()

    organization_extuser_7 = ExtUser()
    organization_extuser_7.username = u'pf2'
    organization_extuser_7.first_name = u''
    organization_extuser_7.last_name = u''
    organization_extuser_7.email = u''
    organization_extuser_7.password = u'test'
    organization_extuser_7.is_staff = False
    organization_extuser_7.is_active = True
    organization_extuser_7.is_superuser = False
    organization_extuser_7.last_login = datetime.datetime(2009, 4, 15, 10, 57, 31)
    organization_extuser_7.date_joined = datetime.datetime(2009, 4, 15, 10, 57, 31)
    organization_extuser_7.primary_phone = u'+1412135452'
    organization_extuser_7.domain = organization_domain_1
    organization_extuser_7.identity = None
    organization_extuser_7.save()

    organization_extuser_8 = ExtUser()
    organization_extuser_8.username = u'br1'
    organization_extuser_8.first_name = u''
    organization_extuser_8.last_name = u''
    organization_extuser_8.email = u''
    organization_extuser_8.password = u'sha1$f0e70$8d5487476afde09a4a35de8d6ef3b39fba0b4405'
    organization_extuser_8.is_staff = False
    organization_extuser_8.is_active = True
    organization_extuser_8.is_superuser = False
    organization_extuser_8.last_login = datetime.datetime(2009, 4, 15, 10, 57, 52)
    organization_extuser_8.date_joined = datetime.datetime(2009, 4, 15, 10, 57, 52)
    organization_extuser_8.primary_phone = u'+1231214532'
    organization_extuser_8.domain = organization_domain_2
    organization_extuser_8.identity = None
    organization_extuser_8.save()

    organization_extuser_9 = ExtUser()
    organization_extuser_9.username = u'br2'
    organization_extuser_9.first_name = u''
    organization_extuser_9.last_name = u''
    organization_extuser_9.email = u''
    organization_extuser_9.password = u'sha1$a4c05$da3d0998c0d01ded87ffcd26cefdd5db619c6927'
    organization_extuser_9.is_staff = False
    organization_extuser_9.is_active = True
    organization_extuser_9.is_superuser = False
    organization_extuser_9.last_login = datetime.datetime(2009, 4, 15, 10, 58, 7)
    organization_extuser_9.date_joined = datetime.datetime(2009, 4, 15, 10, 58, 7)
    organization_extuser_9.primary_phone = u'+12134897213'
    organization_extuser_9.domain = organization_domain_2
    organization_extuser_9.identity = None
    organization_extuser_9.save()

    organization_extuser_10 = ExtUser()
    organization_extuser_10.username = u'grdoc'
    organization_extuser_10.first_name = u''
    organization_extuser_10.last_name = u''
    organization_extuser_10.email = u''
    organization_extuser_10.password = u'sha1$9df33$4bb013b189b71d3cfefa6f8b867c7a500ea46f68'
    organization_extuser_10.is_staff = False
    organization_extuser_10.is_active = True
    organization_extuser_10.is_superuser = False
    organization_extuser_10.last_login = datetime.datetime(2009, 4, 22, 14, 45, 11)
    organization_extuser_10.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 11)
    organization_extuser_10.primary_phone = u'+1234567897'
    organization_extuser_10.domain = organization_domain_3
    organization_extuser_10.identity = None
    organization_extuser_10.save()

    organization_extuser_11 = ExtUser()
    organization_extuser_11.username = u'grsupervisor'
    organization_extuser_11.first_name = u''
    organization_extuser_11.last_name = u''
    organization_extuser_11.email = u''
    organization_extuser_11.password = u'sha1$4c2a2$cec32be6824786e76488aea338f350c6bbceb8eb'
    organization_extuser_11.is_staff = False
    organization_extuser_11.is_active = True
    organization_extuser_11.is_superuser = False
    organization_extuser_11.last_login = datetime.datetime(2009, 4, 22, 14, 45, 36)
    organization_extuser_11.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 36)
    organization_extuser_11.primary_phone = u'+7778884444'
    organization_extuser_11.domain = organization_domain_3
    organization_extuser_11.identity = None
    organization_extuser_11.save()

    organization_extuser_12 = ExtUser()
    organization_extuser_12.username = u'grmobile1'
    organization_extuser_12.first_name = u''
    organization_extuser_12.last_name = u''
    organization_extuser_12.email = u''
    organization_extuser_12.password = u'sha1$ecda0$0728c9c311d4308333bb62058c1f2e979d2899ea'
    organization_extuser_12.is_staff = False
    organization_extuser_12.is_active = True
    organization_extuser_12.is_superuser = False
    organization_extuser_12.last_login = datetime.datetime(2009, 4, 22, 14, 45, 55)
    organization_extuser_12.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 55)
    organization_extuser_12.primary_phone = u'+45647891216'
    organization_extuser_12.domain = organization_domain_3
    organization_extuser_12.identity = None
    organization_extuser_12.save()

    organization_extuser_13 = ExtUser()
    organization_extuser_13.username = u'grmobile2'
    organization_extuser_13.first_name = u''
    organization_extuser_13.last_name = u''
    organization_extuser_13.email = u''
    organization_extuser_13.password = u'sha1$6b5c2$12023bfbeb8ac8614d9d7800444f4b2053c67f3e'
    organization_extuser_13.is_staff = False
    organization_extuser_13.is_active = True
    organization_extuser_13.is_superuser = False
    organization_extuser_13.last_login = datetime.datetime(2009, 4, 22, 14, 46, 11)
    organization_extuser_13.date_joined = datetime.datetime(2009, 4, 22, 14, 46, 11)
    organization_extuser_13.primary_phone = u'+141512342134'
    organization_extuser_13.domain = organization_domain_3
    organization_extuser_13.identity = None
    organization_extuser_13.save()

    from organization.models import Organization

    organization_organization_1 = Organization()
    organization_organization_1.name = u'Pathfinder'
    organization_organization_1.domain = organization_domain_1
    organization_organization_1.description = u'TZ'
    organization_organization_1.save()

    organization_organization_1.organization_type.add(organization_organizationtype_1)

    organization_organization_2 = Organization()
    organization_organization_2.name = u'BRAC'
    organization_organization_2.domain = organization_domain_2
    organization_organization_2.description = u''
    organization_organization_2.save()

    organization_organization_2.organization_type.add(organization_organizationtype_2)

    organization_organization_3 = Organization()
    organization_organization_3.name = u'BRAC-CHP'
    organization_organization_3.domain = organization_domain_2
    organization_organization_3.description = u''
    organization_organization_3.save()

    organization_organization_3.organization_type.add(organization_organizationtype_2)

    organization_organization_4 = Organization()
    organization_organization_4.name = u'BRAC-CHW'
    organization_organization_4.domain = organization_domain_2
    organization_organization_4.description = u''
    organization_organization_4.save()

    organization_organization_4.organization_type.add(organization_organizationtype_2)

    organization_organization_5 = Organization()
    organization_organization_5.name = u'Grameen-Intel'
    organization_organization_5.domain = organization_domain_3
    organization_organization_5.description = u''
    organization_organization_5.save()

    organization_organization_5.organization_type.add(organization_organizationtype_3)

    from organization.models import ReportSchedule


    from dbanalyzer.models import BaseGraph


    from dbanalyzer.models import RawGraph

    dbanalyzer_rawgraph_1 = RawGraph()
    dbanalyzer_rawgraph_1.shortname = u'Avg time with patient'
    dbanalyzer_rawgraph_1.title = u'Average Time Spent with Patient at Registration'
    dbanalyzer_rawgraph_1.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_1.data_source = u''
    dbanalyzer_rawgraph_1.db_query = u'select \r\ndistinct(username), \r\navg(UNIX_TIMESTAMP(timeend) - UNIX_TIMESTAMP(timestart)) as avg \r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\ngroup by username\r\n\r\n\r\n'
    dbanalyzer_rawgraph_1.x_axis_label = u''
    dbanalyzer_rawgraph_1.x_type = u'string'
    dbanalyzer_rawgraph_1.series_labels = u'Time'
    dbanalyzer_rawgraph_1.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_1.series_options = u''
    dbanalyzer_rawgraph_1.save()

    dbanalyzer_rawgraph_2 = RawGraph()
    dbanalyzer_rawgraph_2.shortname = u'Prior Birth distributions'
    dbanalyzer_rawgraph_2.title = u'Distribution of Prior Births at Registration'
    dbanalyzer_rawgraph_2.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_2.data_source = u''
    dbanalyzer_rawgraph_2.db_query = u"select\r\n distinct(numb_birth), \r\n count(*) \r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\nwhere given_birth='yes'\r\ngroup by numb_birth"
    dbanalyzer_rawgraph_2.x_axis_label = u''
    dbanalyzer_rawgraph_2.x_type = u'numeric'
    dbanalyzer_rawgraph_2.series_labels = u'Counts'
    dbanalyzer_rawgraph_2.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_2.series_options = u''
    dbanalyzer_rawgraph_2.save()

    dbanalyzer_rawgraph_3 = RawGraph()
    dbanalyzer_rawgraph_3.shortname = u'Average number of Prior births'
    dbanalyzer_rawgraph_3.title = u'Average number of Prior Births'
    dbanalyzer_rawgraph_3.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1 '
    dbanalyzer_rawgraph_3.data_source = u''
    dbanalyzer_rawgraph_3.db_query = u"select \r\n DATE_FORMAT(timeend,'%%m/%%d/%%Y'),\r\n avg(numb_birth) as avgbirth\r\n\r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1 \r\nwhere given_birth='yes'\r\n\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y')\r\n;"
    dbanalyzer_rawgraph_3.x_axis_label = u''
    dbanalyzer_rawgraph_3.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_3.series_labels = u'Count'
    dbanalyzer_rawgraph_3.display_type = u'absolute-line'
    dbanalyzer_rawgraph_3.series_options = u''
    dbanalyzer_rawgraph_3.save()

    dbanalyzer_rawgraph_4 = RawGraph()
    dbanalyzer_rawgraph_4.shortname = u'User Registrations to Date'
    dbanalyzer_rawgraph_4.title = u'Total Registrations by User'
    dbanalyzer_rawgraph_4.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_4.data_source = u''
    dbanalyzer_rawgraph_4.db_query = u'select\r\n distinct(username), \r\ncount(*) \r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\ngroup by username'
    dbanalyzer_rawgraph_4.x_axis_label = u'Username'
    dbanalyzer_rawgraph_4.x_type = u'string'
    dbanalyzer_rawgraph_4.series_labels = u'Count'
    dbanalyzer_rawgraph_4.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_4.series_options = u''
    dbanalyzer_rawgraph_4.save()

    dbanalyzer_rawgraph_5 = RawGraph()
    dbanalyzer_rawgraph_5.shortname = u'Registration Trends by User'
    dbanalyzer_rawgraph_5.title = u'Pregnancy Registration Trends by User'
    dbanalyzer_rawgraph_5.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_5.data_source = u''
    dbanalyzer_rawgraph_5.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), username, count(*)\r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), username\r\norder by timeend asc;"
    dbanalyzer_rawgraph_5.x_axis_label = u''
    dbanalyzer_rawgraph_5.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_5.series_labels = u'Count'
    dbanalyzer_rawgraph_5.display_type = u'compare-cumulative'
    dbanalyzer_rawgraph_5.series_options = u''
    dbanalyzer_rawgraph_5.save()

    dbanalyzer_rawgraph_6 = RawGraph()
    dbanalyzer_rawgraph_6.shortname = u'Grameen User Daily Registrations'
    dbanalyzer_rawgraph_6.title = u'Daily Pregnancy Registrations by user'
    dbanalyzer_rawgraph_6.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_6.data_source = u''
    dbanalyzer_rawgraph_6.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), username, count(*)\r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), username\r\norder by timeend asc;"
    dbanalyzer_rawgraph_6.x_axis_label = u'Date'
    dbanalyzer_rawgraph_6.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_6.series_labels = u'username'
    dbanalyzer_rawgraph_6.display_type = u'compare-trend'
    dbanalyzer_rawgraph_6.series_options = u''
    dbanalyzer_rawgraph_6.save()

    dbanalyzer_rawgraph_7 = RawGraph()
    dbanalyzer_rawgraph_7.shortname = u'Registrations per day'
    dbanalyzer_rawgraph_7.title = u'Pregnancy Registration Activity'
    dbanalyzer_rawgraph_7.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_7.data_source = u''
    dbanalyzer_rawgraph_7.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'),\r\n  count(*)\r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y')\r\norder by timeend asc;"
    dbanalyzer_rawgraph_7.x_axis_label = u''
    dbanalyzer_rawgraph_7.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_7.series_labels = u'Count'
    dbanalyzer_rawgraph_7.display_type = u'absolute-line'
    dbanalyzer_rawgraph_7.series_options = u''
    dbanalyzer_rawgraph_7.save()

    dbanalyzer_rawgraph_8 = RawGraph()
    dbanalyzer_rawgraph_8.shortname = u'All Registrations'
    dbanalyzer_rawgraph_8.title = u'All Pregnancy Registrations'
    dbanalyzer_rawgraph_8.table_name = u'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1'
    dbanalyzer_rawgraph_8.data_source = u''
    dbanalyzer_rawgraph_8.db_query = u"select\r\n  timeend, count(*)\r\nfrom x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y')\r\norder by timeend asc;"
    dbanalyzer_rawgraph_8.x_axis_label = u''
    dbanalyzer_rawgraph_8.x_type = u'date'
    dbanalyzer_rawgraph_8.series_labels = u'Count'
    dbanalyzer_rawgraph_8.display_type = u'cumulative-line'
    dbanalyzer_rawgraph_8.series_options = u''
    dbanalyzer_rawgraph_8.save()

    dbanalyzer_rawgraph_9 = RawGraph()
    dbanalyzer_rawgraph_9.shortname = u'absolute bar'
    dbanalyzer_rawgraph_9.title = u'absolute bar'
    dbanalyzer_rawgraph_9.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_9.data_source = u'commcarehq'
    dbanalyzer_rawgraph_9.db_query = u'select \r\n    timeend,\r\n    number_of_children,\r\n    num_of_baby \r\n\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1;'
    dbanalyzer_rawgraph_9.x_axis_label = u'Time'
    dbanalyzer_rawgraph_9.x_type = u'date'
    dbanalyzer_rawgraph_9.series_labels = u'Children|Babies'
    dbanalyzer_rawgraph_9.display_type = u'absolute-bar'
    dbanalyzer_rawgraph_9.series_options = u''
    dbanalyzer_rawgraph_9.save()

    dbanalyzer_rawgraph_10 = RawGraph()
    dbanalyzer_rawgraph_10.shortname = u'absolute line'
    dbanalyzer_rawgraph_10.title = u'absolute line'
    dbanalyzer_rawgraph_10.table_name = u'sadf'
    dbanalyzer_rawgraph_10.data_source = u'asdf'
    dbanalyzer_rawgraph_10.db_query = u'select \r\n    timeend,\r\n    number_of_children,\r\n    num_of_baby \r\n\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1;'
    dbanalyzer_rawgraph_10.x_axis_label = u'Time'
    dbanalyzer_rawgraph_10.x_type = u'date'
    dbanalyzer_rawgraph_10.series_labels = u'1|2'
    dbanalyzer_rawgraph_10.display_type = u'absolute-line'
    dbanalyzer_rawgraph_10.series_options = u''
    dbanalyzer_rawgraph_10.save()

    dbanalyzer_rawgraph_11 = RawGraph()
    dbanalyzer_rawgraph_11.shortname = u'cumulative line'
    dbanalyzer_rawgraph_11.title = u'cumulative line'
    dbanalyzer_rawgraph_11.table_name = u'fasdfwdrf'
    dbanalyzer_rawgraph_11.data_source = u''
    dbanalyzer_rawgraph_11.db_query = u'select      \r\n   timeend,     \r\n   number_of_children,     \r\n   num_of_baby   \r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1;'
    dbanalyzer_rawgraph_11.x_axis_label = u'time'
    dbanalyzer_rawgraph_11.x_type = u'date'
    dbanalyzer_rawgraph_11.series_labels = u'0|1'
    dbanalyzer_rawgraph_11.display_type = u'cumulative-line'
    dbanalyzer_rawgraph_11.series_options = u''
    dbanalyzer_rawgraph_11.save()

    dbanalyzer_rawgraph_12 = RawGraph()
    dbanalyzer_rawgraph_12.shortname = u'Global Daily Referral Count'
    dbanalyzer_rawgraph_12.title = u'Global Report of Inbound Referrals (daily count)'
    dbanalyzer_rawgraph_12.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_12.data_source = u''
    dbanalyzer_rawgraph_12.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given\r\norder by timeend asc;"
    dbanalyzer_rawgraph_12.x_axis_label = u''
    dbanalyzer_rawgraph_12.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_12.series_labels = u'referral'
    dbanalyzer_rawgraph_12.display_type = u'compare-trend'
    dbanalyzer_rawgraph_12.series_options = u''
    dbanalyzer_rawgraph_12.save()

    dbanalyzer_rawgraph_13 = RawGraph()
    dbanalyzer_rawgraph_13.shortname = u'Global Referral Trends'
    dbanalyzer_rawgraph_13.title = u'Global Referral Trends (cumulative)'
    dbanalyzer_rawgraph_13.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_13.data_source = u''
    dbanalyzer_rawgraph_13.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given\r\norder by timeend asc;"
    dbanalyzer_rawgraph_13.x_axis_label = u''
    dbanalyzer_rawgraph_13.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_13.series_labels = u'asdf'
    dbanalyzer_rawgraph_13.display_type = u'compare-cumulative'
    dbanalyzer_rawgraph_13.series_options = u''
    dbanalyzer_rawgraph_13.save()

    dbanalyzer_rawgraph_14 = RawGraph()
    dbanalyzer_rawgraph_14.shortname = u'Histogram of all referrals'
    dbanalyzer_rawgraph_14.title = u'Overall Given Referrals'
    dbanalyzer_rawgraph_14.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_14.data_source = u'commcarehq'
    dbanalyzer_rawgraph_14.db_query = u'select distinct(referral_given), count(*) from x_http__www_commcare_org_brac_chp_homevisit_v0_0_1 group by referral_given'
    dbanalyzer_rawgraph_14.x_axis_label = u'val'
    dbanalyzer_rawgraph_14.x_type = u'string'
    dbanalyzer_rawgraph_14.series_labels = u'0'
    dbanalyzer_rawgraph_14.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_14.series_options = u''
    dbanalyzer_rawgraph_14.save()

    dbanalyzer_rawgraph_15 = RawGraph()
    dbanalyzer_rawgraph_15.shortname = u'Overall Submissions by User'
    dbanalyzer_rawgraph_15.title = u'Overall Submissions by all users (cumulative)'
    dbanalyzer_rawgraph_15.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_15.data_source = u''
    dbanalyzer_rawgraph_15.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), username, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), username\r\norder by timeend asc;"
    dbanalyzer_rawgraph_15.x_axis_label = u'Date'
    dbanalyzer_rawgraph_15.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_15.series_labels = u'0'
    dbanalyzer_rawgraph_15.display_type = u'compare-cumulative'
    dbanalyzer_rawgraph_15.series_options = u''
    dbanalyzer_rawgraph_15.save()

    dbanalyzer_rawgraph_16 = RawGraph()
    dbanalyzer_rawgraph_16.shortname = u'Total User Submissions'
    dbanalyzer_rawgraph_16.title = u'All Submissions by User'
    dbanalyzer_rawgraph_16.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_16.data_source = u''
    dbanalyzer_rawgraph_16.db_query = u'select distinct(username), count(*) from x_http__www_commcare_org_brac_chp_homevisit_v0_0_1 group by username'
    dbanalyzer_rawgraph_16.x_axis_label = u'Username'
    dbanalyzer_rawgraph_16.x_type = u'string'
    dbanalyzer_rawgraph_16.series_labels = u'count'
    dbanalyzer_rawgraph_16.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_16.series_options = u''
    dbanalyzer_rawgraph_16.save()

    dbanalyzer_rawgraph_17 = RawGraph()
    dbanalyzer_rawgraph_17.shortname = u'User Daily Submissions'
    dbanalyzer_rawgraph_17.title = u'Submissions by User (daily count)'
    dbanalyzer_rawgraph_17.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_17.data_source = u''
    dbanalyzer_rawgraph_17.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), username, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), username\r\norder by timeend asc;"
    dbanalyzer_rawgraph_17.x_axis_label = u'Date'
    dbanalyzer_rawgraph_17.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_17.series_labels = u'Username'
    dbanalyzer_rawgraph_17.display_type = u'compare-trend'
    dbanalyzer_rawgraph_17.series_options = u''
    dbanalyzer_rawgraph_17.save()

    from dbanalyzer.models import GraphGroup

    dbanalyzer_graphgroup_1 = GraphGroup()
    dbanalyzer_graphgroup_1.name = u'Grameen Root Chart Group'
    dbanalyzer_graphgroup_1.description = u'Grameen Root Chart Group'
    dbanalyzer_graphgroup_1.parent_group = None
    dbanalyzer_graphgroup_1.save()

    dbanalyzer_graphgroup_2 = GraphGroup()
    dbanalyzer_graphgroup_2.name = u'Registration'
    dbanalyzer_graphgroup_2.description = u'Registration Graphs'
    dbanalyzer_graphgroup_2.parent_group = dbanalyzer_graphgroup_1
    dbanalyzer_graphgroup_2.save()

    dbanalyzer_graphgroup_2.graphs.add(None)
    dbanalyzer_graphgroup_2.graphs.add(None)

    dbanalyzer_graphgroup_3 = GraphGroup()
    dbanalyzer_graphgroup_3.name = u'Registration User Charts'
    dbanalyzer_graphgroup_3.description = u'Registration stats by user'
    dbanalyzer_graphgroup_3.parent_group = dbanalyzer_graphgroup_2
    dbanalyzer_graphgroup_3.save()

    dbanalyzer_graphgroup_3.graphs.add(None)
    dbanalyzer_graphgroup_3.graphs.add(None)
    dbanalyzer_graphgroup_3.graphs.add(None)
    dbanalyzer_graphgroup_3.graphs.add(None)

    dbanalyzer_graphgroup_4 = GraphGroup()
    dbanalyzer_graphgroup_4.name = u'Registration Pregnancy Stats'
    dbanalyzer_graphgroup_4.description = u'Stats on Pregnancy related data'
    dbanalyzer_graphgroup_4.parent_group = dbanalyzer_graphgroup_2
    dbanalyzer_graphgroup_4.save()

    dbanalyzer_graphgroup_4.graphs.add(None)
    dbanalyzer_graphgroup_4.graphs.add(None)

    dbanalyzer_graphgroup_5 = GraphGroup()
    dbanalyzer_graphgroup_5.name = u'BRAC root graphs'
    dbanalyzer_graphgroup_5.description = u'BRAC Graph Root'
    dbanalyzer_graphgroup_5.parent_group = None
    dbanalyzer_graphgroup_5.save()

    dbanalyzer_graphgroup_6 = GraphGroup()
    dbanalyzer_graphgroup_6.name = u'Brac User Charts'
    dbanalyzer_graphgroup_6.description = u'Brac user charts'
    dbanalyzer_graphgroup_6.parent_group = dbanalyzer_graphgroup_5
    dbanalyzer_graphgroup_6.save()

    dbanalyzer_graphgroup_6.graphs.add(None)
    dbanalyzer_graphgroup_6.graphs.add(None)
    dbanalyzer_graphgroup_6.graphs.add(None)

    dbanalyzer_graphgroup_7 = GraphGroup()
    dbanalyzer_graphgroup_7.name = u'Brac Data Charts'
    dbanalyzer_graphgroup_7.description = u'Data data'
    dbanalyzer_graphgroup_7.parent_group = dbanalyzer_graphgroup_5
    dbanalyzer_graphgroup_7.save()

    dbanalyzer_graphgroup_7.graphs.add(None)
    dbanalyzer_graphgroup_7.graphs.add(None)
    dbanalyzer_graphgroup_7.graphs.add(None)

    from dbanalyzer.models import GraphPref


    from receiver.models import Submission


    from receiver.models import Backup


    from receiver.models import Attachment


