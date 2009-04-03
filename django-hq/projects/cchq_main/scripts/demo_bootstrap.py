#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file has been automatically generated, changes may be lost if you
# go and generate it again. It was generated with the following command:
# manage.py dumpscript organization modelrelationship

import datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType

def run():
    from organization.models import Domain

    organization_domain_1 = Domain()
    organization_domain_1.name = u'HelperOrganization'
    organization_domain_1.description = u''
    organization_domain_1.save()

    organization_domain_2 = Domain()
    organization_domain_2.name = u'Intel-Grameen'
    organization_domain_2.description = u''
    organization_domain_2.save()

    organization_domain_3 = Domain()
    organization_domain_3.name = u'Pathfinder'
    organization_domain_3.description = u''
    organization_domain_3.save()

    from organization.models import OrganizationType

    organization_organizationtype_1 = OrganizationType()
    organization_organizationtype_1.name = u'NGO'
    organization_organizationtype_1.domain = organization_domain_1
    organization_organizationtype_1.description = u''
    organization_organizationtype_1.save()

    from organization.models import ExtRole


    from organization.models import Organization

    organization_organization_1 = Organization()
    organization_organization_1.name = u'HelperOrganization'
    organization_organization_1.domain = organization_domain_1
    organization_organization_1.description = u''
    organization_organization_1.save()

    organization_organization_1.organization_type.add(organization_organizationtype_1)

    organization_organization_2 = Organization()
    organization_organization_2.name = u'HelpOrg - CHP'
    organization_organization_2.domain = organization_domain_1
    organization_organization_2.description = u''
    organization_organization_2.save()

    organization_organization_2.organization_type.add(organization_organizationtype_1)

    organization_organization_3 = Organization()
    organization_organization_3.name = u'HelpOrg - CHW'
    organization_organization_3.domain = organization_domain_1
    organization_organization_3.description = u''
    organization_organization_3.save()

    organization_organization_3.organization_type.add(organization_organizationtype_1)

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

    from modelrelationship.models import Edge

    modelrelationship_edge_1 = Edge()
    modelrelationship_edge_1.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_1.child_id = 2L
    modelrelationship_edge_1.relationship = modelrelationship_edgetype_1
    modelrelationship_edge_1.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_1.parent_id = 1L
    modelrelationship_edge_1.save()

    modelrelationship_edge_2 = Edge()
    modelrelationship_edge_2.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_2.child_id = 3L
    modelrelationship_edge_2.relationship = modelrelationship_edgetype_1
    modelrelationship_edge_2.parent_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_2.parent_id = 1L
    modelrelationship_edge_2.save()

    modelrelationship_edge_3 = Edge()
    modelrelationship_edge_3.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_3.child_id = 2L
    modelrelationship_edge_3.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_3.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_3.parent_id = 2L
    modelrelationship_edge_3.save()

    modelrelationship_edge_4 = Edge()
    modelrelationship_edge_4.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_4.child_id = 3L
    modelrelationship_edge_4.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_4.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_4.parent_id = 2L
    modelrelationship_edge_4.save()

    modelrelationship_edge_5 = Edge()
    modelrelationship_edge_5.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_5.child_id = 4L
    modelrelationship_edge_5.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_5.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_5.parent_id = 2L
    modelrelationship_edge_5.save()

    modelrelationship_edge_6 = Edge()
    modelrelationship_edge_6.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_6.child_id = 5L
    modelrelationship_edge_6.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_6.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_6.parent_id = 2L
    modelrelationship_edge_6.save()

    modelrelationship_edge_7 = Edge()
    modelrelationship_edge_7.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_7.child_id = 2L
    modelrelationship_edge_7.relationship = modelrelationship_edgetype_2
    modelrelationship_edge_7.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_7.parent_id = 3L
    modelrelationship_edge_7.save()

    modelrelationship_edge_8 = Edge()
    modelrelationship_edge_8.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edge_8.child_id = 6L
    modelrelationship_edge_8.relationship = modelrelationship_edgetype_3
    modelrelationship_edge_8.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_8.parent_id = 3L
    modelrelationship_edge_8.save()

    modelrelationship_edge_9 = Edge()
    modelrelationship_edge_9.child_type = ContentType.objects.get(app_label="organization", model="organization")
    modelrelationship_edge_9.child_id = 1L
    modelrelationship_edge_9.relationship = modelrelationship_edgetype_4
    modelrelationship_edge_9.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_9.parent_id = 1L
    modelrelationship_edge_9.save()

    from organization.models import ExtUser

    organization_extuser_1 = ExtUser()
    organization_extuser_1.username = u'brian'
    organization_extuser_1.first_name = u''
    organization_extuser_1.last_name = u''
    organization_extuser_1.email = u''
    organization_extuser_1.password = u'sha1$9bc9f$2d0448052960a387e4c38792a42c171069e4e402'
    organization_extuser_1.is_staff = True
    organization_extuser_1.is_active = True
    organization_extuser_1.is_superuser = True
    organization_extuser_1.last_login = datetime.datetime(2009, 4, 3, 13, 34, 27)
    organization_extuser_1.date_joined = datetime.datetime(2009, 3, 30, 16, 38, 50)
    organization_extuser_1.primary_phone = u''
    organization_extuser_1.domain = organization_domain_1
    organization_extuser_1.identity = None
    organization_extuser_1.save()

    organization_extuser_2 = ExtUser()
    organization_extuser_2.username = u'gayo'
    organization_extuser_2.first_name = u''
    organization_extuser_2.last_name = u''
    organization_extuser_2.email = u''
    organization_extuser_2.password = u'sha1$991d2$88984dd1d4516e35041785d1410eded1ae222814'
    organization_extuser_2.is_staff = False
    organization_extuser_2.is_active = True
    organization_extuser_2.is_superuser = False
    organization_extuser_2.last_login = datetime.datetime(2009, 3, 30, 16, 39, 6)
    organization_extuser_2.date_joined = datetime.datetime(2009, 3, 30, 16, 39, 6)
    organization_extuser_2.primary_phone = u'123456'
    organization_extuser_2.domain = organization_domain_1
    organization_extuser_2.identity = None
    organization_extuser_2.save()

    organization_extuser_3 = ExtUser()
    organization_extuser_3.username = u'mobile1'
    organization_extuser_3.first_name = u''
    organization_extuser_3.last_name = u''
    organization_extuser_3.email = u''
    organization_extuser_3.password = u'sha1$214fa$1798dfe80ded098ec17df752466bf9619f026be4'
    organization_extuser_3.is_staff = False
    organization_extuser_3.is_active = True
    organization_extuser_3.is_superuser = False
    organization_extuser_3.last_login = datetime.datetime(2009, 3, 30, 16, 39, 23)
    organization_extuser_3.date_joined = datetime.datetime(2009, 3, 30, 16, 39, 23)
    organization_extuser_3.primary_phone = u'123154123'
    organization_extuser_3.domain = organization_domain_1
    organization_extuser_3.identity = None
    organization_extuser_3.save()

    organization_extuser_4 = ExtUser()
    organization_extuser_4.username = u'mobile2'
    organization_extuser_4.first_name = u''
    organization_extuser_4.last_name = u''
    organization_extuser_4.email = u''
    organization_extuser_4.password = u'sha1$daa1b$d6b7bee6be830b104b56254ea9c1aabbe477e9cb'
    organization_extuser_4.is_staff = False
    organization_extuser_4.is_active = True
    organization_extuser_4.is_superuser = False
    organization_extuser_4.last_login = datetime.datetime(2009, 3, 30, 16, 39, 35)
    organization_extuser_4.date_joined = datetime.datetime(2009, 3, 30, 16, 39, 35)
    organization_extuser_4.primary_phone = u'462168798'
    organization_extuser_4.domain = organization_domain_1
    organization_extuser_4.identity = None
    organization_extuser_4.save()

    organization_extuser_5 = ExtUser()
    organization_extuser_5.username = u'mobile3'
    organization_extuser_5.first_name = u''
    organization_extuser_5.last_name = u''
    organization_extuser_5.email = u''
    organization_extuser_5.password = u'sha1$ab083$33ab7e7737e585d6428de17ac60e6a78b86c795c'
    organization_extuser_5.is_staff = False
    organization_extuser_5.is_active = True
    organization_extuser_5.is_superuser = False
    organization_extuser_5.last_login = datetime.datetime(2009, 3, 30, 16, 39, 51)
    organization_extuser_5.date_joined = datetime.datetime(2009, 3, 30, 16, 39, 51)
    organization_extuser_5.primary_phone = u'646137894152'
    organization_extuser_5.domain = organization_domain_1
    organization_extuser_5.identity = None
    organization_extuser_5.save()

    organization_extuser_6 = ExtUser()
    organization_extuser_6.username = u'testadmin'
    organization_extuser_6.first_name = u''
    organization_extuser_6.last_name = u''
    organization_extuser_6.email = u''
    organization_extuser_6.password = u'test'
    organization_extuser_6.is_staff = False
    organization_extuser_6.is_active = True
    organization_extuser_6.is_superuser = True
    organization_extuser_6.last_login = datetime.datetime(2009, 4, 3, 13, 36, 8)
    organization_extuser_6.date_joined = datetime.datetime(2009, 4, 3, 13, 36, 8)
    organization_extuser_6.primary_phone = u'111223333'
    organization_extuser_6.domain = organization_domain_1
    organization_extuser_6.identity = None
    organization_extuser_6.save()

    organization_extuser_1.user_ptr = User.objects.get(id=2)
    organization_extuser_1.save()

    organization_extuser_2.user_ptr = User.objects.get(id=3)
    organization_extuser_2.save()

    organization_extuser_3.user_ptr = User.objects.get(id=4)
    organization_extuser_3.save()

    organization_extuser_4.user_ptr = User.objects.get(id=5)
    organization_extuser_4.save()

    organization_extuser_5.user_ptr = User.objects.get(id=6)
    organization_extuser_5.save()

    organization_extuser_6.user_ptr = User.objects.get(id=7)
    organization_extuser_6.save()

