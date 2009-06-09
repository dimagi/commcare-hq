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

    
    modelrelationship_edgetype_5 = EdgeType()
    modelrelationship_edgetype_5.directional = True
    modelrelationship_edgetype_5.name = u'User Chart Group'
    modelrelationship_edgetype_5.description = u'A User can have a root chart group linked to their login'
    modelrelationship_edgetype_5.child_type = ContentType.objects.get(app_label="dbanalyzer", model="graphgroup")
    modelrelationship_edgetype_5.parent_type = ContentType.objects.get(app_label="organization", model="extuser")
    modelrelationship_edgetype_5.save()

    from modelrelationship.models import Edge

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
    
    organization_domain_4 = Domain()
    organization_domain_4.name = u'MVP'
    organization_domain_4.description = u''
    organization_domain_4.save()

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
    
    organization_organizationtype_4 = OrganizationType()
    organization_organizationtype_4.name = u'MVP-Org'
    organization_organizationtype_4.domain = organization_domain_4
    organization_organizationtype_4.description = u''
    organization_organizationtype_4.save()


    from organization.models import ExtRole


    from organization.models import ExtUser

    organization_extuser_1 = ExtUser()
    organization_extuser_1.username = u'bracadmin'
    organization_extuser_1.first_name = u''
    organization_extuser_1.last_name = u''
    organization_extuser_1.email = u'dmyung+bracadmin@dimagi.com'
    organization_extuser_1.password = u'sha1$25e8d$45cfe119a9429d066168a20255f737dbffef6488'
    organization_extuser_1.is_staff = False
    organization_extuser_1.is_active = True
    organization_extuser_1.is_superuser = True
    organization_extuser_1.last_login = datetime.datetime(2009, 4, 15, 10, 33, 29)
    organization_extuser_1.date_joined = datetime.datetime(2009, 4, 15, 10, 33, 29)
    organization_extuser_1.primary_phone = u'+16176453236'
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
    organization_extuser_2.last_login = datetime.datetime(2009, 4, 24, 16, 53, 39)
    organization_extuser_2.date_joined = datetime.datetime(2009, 4, 15, 10, 34, 6)
    organization_extuser_2.primary_phone = u''
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
    organization_extuser_3.last_login = datetime.datetime(2009, 4, 24, 16, 55, 24)
    organization_extuser_3.date_joined = datetime.datetime(2009, 4, 15, 10, 34, 38)
    organization_extuser_3.primary_phone = u''
    organization_extuser_3.domain = organization_domain_3
    organization_extuser_3.identity = None
    organization_extuser_3.save()

    organization_extuser_4 = ExtUser()
    organization_extuser_4.username = u'brian'
    organization_extuser_4.first_name = u''
    organization_extuser_4.last_name = u''
    organization_extuser_4.email = u'dmyung+brian@dimagi.com'
    organization_extuser_4.password = u'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
    organization_extuser_4.is_staff = False
    organization_extuser_4.is_active = True
    organization_extuser_4.is_superuser = True
    organization_extuser_4.last_login = datetime.datetime(2009, 4, 24, 17, 1, 40)
    organization_extuser_4.date_joined = datetime.datetime(2009, 4, 15, 10, 35, 1)
    organization_extuser_4.primary_phone = u'+16174016544'
    organization_extuser_4.domain = organization_domain_2
    organization_extuser_4.identity = None
    organization_extuser_4.save()

    organization_extuser_5 = ExtUser()
    organization_extuser_5.username = u'gayo'
    organization_extuser_5.first_name = u''
    organization_extuser_5.last_name = u''
    organization_extuser_5.email = u'dmyung+gayo@dimagi.com'
    organization_extuser_5.password = u'sha1$2aa9b$f8ce3e507b719c97d8442e518f8632c4454e686f'
    organization_extuser_5.is_staff = False
    organization_extuser_5.is_active = True
    organization_extuser_5.is_superuser = False
    organization_extuser_5.last_login = datetime.datetime(2009, 4, 15, 10, 35, 25)
    organization_extuser_5.date_joined = datetime.datetime(2009, 4, 15, 10, 35, 25)
    organization_extuser_5.primary_phone = u'+16174016544'
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
    organization_extuser_6.primary_phone = u''
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
    organization_extuser_7.primary_phone = u''
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
    organization_extuser_8.primary_phone = u'+16176453236'
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
    organization_extuser_9.primary_phone = u'+16174016544'
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
    organization_extuser_10.primary_phone = u''
    organization_extuser_10.domain = organization_domain_3
    organization_extuser_10.identity = None
    organization_extuser_10.save()

    organization_extuser_11 = ExtUser()
    organization_extuser_11.username = u'grsupervisor'
    organization_extuser_11.first_name = u''
    organization_extuser_11.last_name = u''
    organization_extuser_11.email = u'dmyung+grsupervisor@dimagi.com'
    organization_extuser_11.password = u'sha1$4c2a2$cec32be6824786e76488aea338f350c6bbceb8eb'
    organization_extuser_11.is_staff = False
    organization_extuser_11.is_active = True
    organization_extuser_11.is_superuser = False
    organization_extuser_11.last_login = datetime.datetime(2009, 4, 22, 14, 45, 36)
    organization_extuser_11.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 36)
    organization_extuser_11.primary_phone = u'+16174016544'
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
    organization_extuser_12.primary_phone = u''
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
    organization_extuser_13.primary_phone = u''
    organization_extuser_13.domain = organization_domain_3
    organization_extuser_13.identity = None
    organization_extuser_13.save()

    organization_extuser_14 = ExtUser()
    organization_extuser_14.username = u'mvpadmin'
    organization_extuser_14.first_name = u''
    organization_extuser_14.last_name = u''
    organization_extuser_14.email = u''
    organization_extuser_14.password = u'sha1$65d24$447a3770156eb7d91381819b14fb9c7a07ce15eb'
    organization_extuser_14.is_staff = False
    organization_extuser_14.is_active = True
    organization_extuser_14.is_superuser = True
    organization_extuser_14.last_login = datetime.datetime(2009, 4, 30, 13, 49, 20)
    organization_extuser_14.date_joined = datetime.datetime(2009, 4, 30, 13, 20, 36)
    organization_extuser_14.chw_id = u'000'
    organization_extuser_14.primary_phone = u''
    organization_extuser_14.domain = organization_domain_4
    organization_extuser_14.identity = None
    organization_extuser_14.save()

    organization_extuser_15 = ExtUser()
    organization_extuser_15.username = u'mvpuser1'
    organization_extuser_15.first_name = u''
    organization_extuser_15.last_name = u''
    organization_extuser_15.email = u''
    organization_extuser_15.password = u'resetme'
    organization_extuser_15.is_staff = False
    organization_extuser_15.is_active = True
    organization_extuser_15.is_superuser = False
    organization_extuser_15.last_login = datetime.datetime(2009, 4, 30, 13, 21, 57)
    organization_extuser_15.date_joined = datetime.datetime(2009, 4, 30, 13, 21, 57)
    organization_extuser_15.chw_id = u'001'
    organization_extuser_15.primary_phone = u''
    organization_extuser_15.domain = organization_domain_4
    organization_extuser_15.identity = None
    organization_extuser_15.save()

    from organization.models import Organization

    organization_organization_1 = Organization()
    organization_organization_1.name = u'Pathfinder'
    organization_organization_1.domain = organization_domain_1
    organization_organization_1.description = u'TZ'
    organization_organization_1.save()
    organization_organization_1.supervisors = [organization_extuser_2]
    organization_organization_1.members = [organization_extuser_6, organization_extuser_7]
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
    organization_organization_3.parent = organization_organization_2 
    organization_organization_3.save()
    organization_organization_3.supervisors = [organization_extuser_4]
    organization_organization_3.members = [organization_extuser_8, organization_extuser_9]
    organization_organization_3.save()
    
    

    organization_organization_3.organization_type.add(organization_organizationtype_2)

    organization_organization_4 = Organization()
    organization_organization_4.name = u'BRAC-CHW'
    organization_organization_4.domain = organization_domain_2
    organization_organization_4.description = u''
    organization_organization_4.parent = organization_organization_2 
    organization_organization_4.save()
    organization_organization_4.members = [organization_extuser_4, organization_extuser_5]
    organization_organization_4.save()
    
    organization_organization_4.organization_type.add(organization_organizationtype_2)

    organization_organization_5 = Organization()
    organization_organization_5.name = u'Grameen-Intel'
    organization_organization_5.domain = organization_domain_3
    organization_organization_5.description = u''
    organization_organization_5.save()
    organization_organization_5.supervisors = [organization_extuser_10, organization_extuser_11]
    organization_organization_5.members = [organization_extuser_12, organization_extuser_13]
    organization_organization_5.save()
    

    organization_organization_5.organization_type.add(organization_organizationtype_3)
    
    organization_organization_6 = Organization()
    organization_organization_6.name = u'MVP'
    organization_organization_6.domain = organization_domain_4
    organization_organization_6.description = u'MVP root organization'
    organization_organization_6.save()

    organization_organization_6.organization_type.add(organization_organizationtype_4)


    from organization.models import ReportSchedule

    organization_reportschedule_1 = ReportSchedule()
    organization_reportschedule_1.name = u'Direct to bracadmin'
    organization_reportschedule_1.description = u'Direct email to bracadmin'
    organization_reportschedule_1.report_class = u'siteadmin'
    organization_reportschedule_1.report_frequency = u'daily'
    organization_reportschedule_1.report_delivery = u'email'
    organization_reportschedule_1.recipient_user = organization_extuser_1
    organization_reportschedule_1.organization = organization_organization_2
    organization_reportschedule_1.report_function = u''
    organization_reportschedule_1.save()

    organization_reportschedule_2 = ReportSchedule()
    organization_reportschedule_2.name = u'Brian Weekly Email'
    organization_reportschedule_2.description = u"Brian's Weekly Email"
    organization_reportschedule_2.report_class = u'supervisor'
    organization_reportschedule_2.report_frequency = u'weekly'
    organization_reportschedule_2.report_delivery = u'email'
    organization_reportschedule_2.recipient_user = None
    organization_reportschedule_2.organization = organization_organization_3
    organization_reportschedule_2.report_function = u''
    organization_reportschedule_2.save()

    organization_reportschedule_3 = ReportSchedule()
    organization_reportschedule_3.name = u'Brian Daily SMS'
    organization_reportschedule_3.description = u"Brian's Daily SMS as CHP Supervisor"
    organization_reportschedule_3.report_class = u'supervisor'
    organization_reportschedule_3.report_frequency = u'daily'
    organization_reportschedule_3.report_delivery = u'sms'
    organization_reportschedule_3.recipient_user = None
    organization_reportschedule_3.organization = organization_organization_3
    organization_reportschedule_3.report_function = u''
    organization_reportschedule_3.save()

    organization_reportschedule_4 = ReportSchedule()
    organization_reportschedule_4.name = u'Daily report to BRAC-CHW'
    organization_reportschedule_4.description = u'Daily SMS as CHW Member'
    organization_reportschedule_4.report_class = u'member'
    organization_reportschedule_4.report_frequency = u'daily'
    organization_reportschedule_4.report_delivery = u'sms'
    organization_reportschedule_4.recipient_user = None
    organization_reportschedule_4.organization = organization_organization_4
    organization_reportschedule_4.report_function = u''
    organization_reportschedule_4.save()

    organization_reportschedule_5 = ReportSchedule()
    organization_reportschedule_5.name = u'Supervisor weekly SMS CHP'
    organization_reportschedule_5.description = u'Supervisor weekly SMS CHP'
    organization_reportschedule_5.report_class = u'supervisor'
    organization_reportschedule_5.report_frequency = u'weekly'
    organization_reportschedule_5.report_delivery = u'sms'
    organization_reportschedule_5.recipient_user = None
    organization_reportschedule_5.organization = organization_organization_3
    organization_reportschedule_5.report_function = u''
    organization_reportschedule_5.save()


    from dbanalyzer.models import GraphPref


    from receiver.models import Submission


    from receiver.models import Backup


    from receiver.models import Attachment


