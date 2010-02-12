#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file has been automatically generated, changes may be lost if you
# go and generate it again. It was generated with the following command:
# manage.py dumpscript

import datetime
from decimal import Decimal

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
    auth_user_1.last_login = datetime.datetime(2009, 8, 6, 10, 37, 54)
    auth_user_1.date_joined = datetime.datetime(2009, 4, 15, 10, 30, 52)
    auth_user_1.save()

    from django.contrib.auth.models import Message


    from domain.models import Domain

    hq_domain_1 = Domain()
    hq_domain_1.name = u'Pathfinder'
    hq_domain_1.description = u''
    hq_domain_1.timezone = None
    hq_domain_1.save()

    hq_domain_2 = Domain()
    hq_domain_2.name = u'BRAC'
    hq_domain_2.description = u''
    hq_domain_2.timezone = None
    hq_domain_2.save()

    hq_domain_3 = Domain()
    hq_domain_3.name = u'Grameen'
    hq_domain_3.description = u''
    hq_domain_3.timezone = None
    hq_domain_3.save()

    hq_domain_4 = Domain()
    hq_domain_4.name = u'MVP'
    hq_domain_4.description = u''
    hq_domain_4.timezone = None
    hq_domain_4.save()

    from hq.models import OrganizationType

    hq_organizationtype_1 = OrganizationType()
    hq_organizationtype_1.name = u'NGO'
    hq_organizationtype_1.domain = hq_domain_1
    hq_organizationtype_1.description = u''
    hq_organizationtype_1.save()

    hq_organizationtype_2 = OrganizationType()
    hq_organizationtype_2.name = u'BRAC-Org'
    hq_organizationtype_2.domain = hq_domain_2
    hq_organizationtype_2.description = u''
    hq_organizationtype_2.save()

    hq_organizationtype_3 = OrganizationType()
    hq_organizationtype_3.name = u'Grameen-Intel'
    hq_organizationtype_3.domain = hq_domain_3
    hq_organizationtype_3.description = u''
    hq_organizationtype_3.save()

    hq_organizationtype_4 = OrganizationType()
    hq_organizationtype_4.name = u'MVP-Org'
    hq_organizationtype_4.domain = hq_domain_4
    hq_organizationtype_4.description = u''
    hq_organizationtype_4.save()

    from httptester.models import Permissions


    from locations.models import LocationType


    from locations.models import Location


    from reports.models import Case


    from patterns.models import Pattern




    from receiver.models import Submission


    from receiver.models import Attachment


    from receiver.models import SubmissionHandlingType


    from receiver.models import SubmissionHandlingOccurrence


    from reporters.models import Role


    from reporters.models import ReporterGroup

    reporters_reportergroup_1 = ReporterGroup()
    reporters_reportergroup_1.title = u'brac-chw-supervisors'
    reporters_reportergroup_1.parent = None
    reporters_reportergroup_1.description = u'BRAC CHW supervisors'
    reporters_reportergroup_1.save()

    reporters_reportergroup_2 = ReporterGroup()
    reporters_reportergroup_2.title = u'brac-chw-members'
    reporters_reportergroup_2.parent = None
    reporters_reportergroup_2.description = u'BRAC CHW members'
    reporters_reportergroup_2.save()

    from reporters.models import Reporter

    reporters_reporter_1 = Reporter()
    reporters_reporter_1.alias = u'bderenzi'
    reporters_reporter_1.first_name = u''
    reporters_reporter_1.last_name = u''
    reporters_reporter_1.location = None
    reporters_reporter_1.role = None
    reporters_reporter_1.language = u'en'
    reporters_reporter_1.registered_self = False
    reporters_reporter_1.save()

    reporters_reporter_1.groups.add(reporters_reportergroup_1)

    reporters_reporter_2 = Reporter()
    reporters_reporter_2.alias = u'njowine'
    reporters_reporter_2.first_name = u''
    reporters_reporter_2.last_name = u''
    reporters_reporter_2.location = None
    reporters_reporter_2.role = None
    reporters_reporter_2.language = u''
    reporters_reporter_2.registered_self = False
    reporters_reporter_2.save()

    reporters_reporter_3 = Reporter()
    reporters_reporter_3.alias = u'husseini'
    reporters_reporter_3.first_name = u''
    reporters_reporter_3.last_name = u''
    reporters_reporter_3.location = None
    reporters_reporter_3.role = None
    reporters_reporter_3.language = u''
    reporters_reporter_3.registered_self = False
    reporters_reporter_3.save()

    reporters_reporter_4 = Reporter()
    reporters_reporter_4.alias = u'joachim'
    reporters_reporter_4.first_name = u''
    reporters_reporter_4.last_name = u''
    reporters_reporter_4.location = None
    reporters_reporter_4.role = None
    reporters_reporter_4.language = u''
    reporters_reporter_4.registered_self = False
    reporters_reporter_4.save()

    reporters_reporter_5 = Reporter()
    reporters_reporter_5.alias = u'demo_user'
    reporters_reporter_5.first_name = u''
    reporters_reporter_5.last_name = u''
    reporters_reporter_5.location = None
    reporters_reporter_5.role = None
    reporters_reporter_5.language = u''
    reporters_reporter_5.registered_self = False
    reporters_reporter_5.save()

    from reporters.models import PersistantBackend

    reporters_persistantbackend_1 = PersistantBackend()
    reporters_persistantbackend_1.slug = u'http'
    reporters_persistantbackend_1.title = u'http'
    reporters_persistantbackend_1.save()

    from reporters.models import PersistantConnection

    reporters_persistantconnection_1 = PersistantConnection()
    reporters_persistantconnection_1.backend = reporters_persistantbackend_1
    reporters_persistantconnection_1.identity = u'13'
    reporters_persistantconnection_1.reporter = reporters_reporter_1
    reporters_persistantconnection_1.last_seen = None
    reporters_persistantconnection_1.save()

    from hq.models import Organization

    hq_organization_1 = Organization()
    hq_organization_1.name = u'Pathfinder'
    hq_organization_1.domain = hq_domain_1
    hq_organization_1.description = u'TZ'
    hq_organization_1.parent = None
    hq_organization_1.members = None
    hq_organization_1.supervisors = None
    hq_organization_1.save()

    hq_organization_1.organization_type.add(hq_organizationtype_1)

    hq_organization_2 = Organization()
    hq_organization_2.name = u'BRAC'
    hq_organization_2.domain = hq_domain_2
    hq_organization_2.description = u''
    hq_organization_2.parent = None
    hq_organization_2.members = None
    hq_organization_2.supervisors = None
    hq_organization_2.save()

    hq_organization_2.organization_type.add(hq_organizationtype_2)

    hq_organization_3 = Organization()
    hq_organization_3.name = u'BRAC-CHP'
    hq_organization_3.domain = hq_domain_2
    hq_organization_3.description = u''
    hq_organization_3.parent = hq_organization_2
    hq_organization_3.members = reporters_reportergroup_2
    hq_organization_3.supervisors = reporters_reportergroup_1
    hq_organization_3.save()

    hq_organization_3.organization_type.add(hq_organizationtype_2)

    hq_organization_4 = Organization()
    hq_organization_4.name = u'BRAC-CHW'
    hq_organization_4.domain = hq_domain_2
    hq_organization_4.description = u''
    hq_organization_4.parent = hq_organization_2
    hq_organization_4.members = None
    hq_organization_4.supervisors = None
    hq_organization_4.save()

    hq_organization_4.organization_type.add(hq_organizationtype_2)

    hq_organization_5 = Organization()
    hq_organization_5.name = u'Grameen-Intel'
    hq_organization_5.domain = hq_domain_3
    hq_organization_5.description = u''
    hq_organization_5.parent = None
    hq_organization_5.members = None
    hq_organization_5.supervisors = None
    hq_organization_5.save()

    hq_organization_5.organization_type.add(hq_organizationtype_3)

    hq_organization_6 = Organization()
    hq_organization_6.name = u'MVP'
    hq_organization_6.domain = hq_domain_4
    hq_organization_6.description = u'MVP root organization'
    hq_organization_6.parent = None
    hq_organization_6.members = None
    hq_organization_6.supervisors = None
    hq_organization_6.save()

    hq_organization_6.organization_type.add(hq_organizationtype_4)

    from hq.models import ReportSchedule

    hq_reportschedule_1 = ReportSchedule()
    hq_reportschedule_1.name = u'Direct to bracadmin'
    hq_reportschedule_1.description = u'Direct email to bracadmin'
    hq_reportschedule_1.report_class = u'siteadmin'
    hq_reportschedule_1.report_frequency = u'daily'
    hq_reportschedule_1.report_delivery = u'email'
    hq_reportschedule_1.organization = hq_organization_2
    hq_reportschedule_1.report_function = u''
    hq_reportschedule_1.active = True
    hq_reportschedule_1.save()

    hq_reportschedule_2 = ReportSchedule()
    hq_reportschedule_2.name = u'Brian Weekly Email'
    hq_reportschedule_2.description = u"Brian's Weekly Email"
    hq_reportschedule_2.report_class = u'supervisor'
    hq_reportschedule_2.report_frequency = u'weekly'
    hq_reportschedule_2.report_delivery = u'email'
    hq_reportschedule_2.recipient_user = None
    hq_reportschedule_2.organization = hq_organization_3
    hq_reportschedule_2.report_function = u''
    hq_reportschedule_2.active = True
    hq_reportschedule_2.save()

    hq_reportschedule_3 = ReportSchedule()
    hq_reportschedule_3.name = u'Brian Daily SMS'
    hq_reportschedule_3.description = u"Brian's Daily SMS as CHP Supervisor"
    hq_reportschedule_3.report_class = u'supervisor'
    hq_reportschedule_3.report_frequency = u'daily'
    hq_reportschedule_3.report_delivery = u'sms'
    hq_reportschedule_3.recipient_user = None
    hq_reportschedule_3.organization = hq_organization_3
    hq_reportschedule_3.report_function = u''
    hq_reportschedule_3.active = True
    hq_reportschedule_3.save()

    hq_reportschedule_4 = ReportSchedule()
    hq_reportschedule_4.name = u'Daily report to BRAC-CHW'
    hq_reportschedule_4.description = u'Daily SMS as CHW Member'
    hq_reportschedule_4.report_class = u'member'
    hq_reportschedule_4.report_frequency = u'daily'
    hq_reportschedule_4.report_delivery = u'sms'
    hq_reportschedule_4.recipient_user = None
    hq_reportschedule_4.organization = hq_organization_4
    hq_reportschedule_4.report_function = u''
    hq_reportschedule_4.active = True
    hq_reportschedule_4.save()

    hq_reportschedule_5 = ReportSchedule()
    hq_reportschedule_5.name = u'Supervisor weekly SMS CHP'
    hq_reportschedule_5.description = u'Supervisor weekly SMS CHP'
    hq_reportschedule_5.report_class = u'supervisor'
    hq_reportschedule_5.report_frequency = u'weekly'
    hq_reportschedule_5.report_delivery = u'sms'
    hq_reportschedule_5.recipient_user = None
    hq_reportschedule_5.organization = hq_organization_3
    hq_reportschedule_5.report_function = u''
    hq_reportschedule_5.active = True
    hq_reportschedule_5.save()

    from reports.models import FormIdentifier


    from reports.models import CaseFormIdentifier


    from xformmanager.models import ElementDefModel


    from xformmanager.models import FormDefModel


    from xformmanager.models import Metadata


    from hq.models import ReporterProfile

    hq_reporterprofile_1 = ReporterProfile()
    hq_reporterprofile_1.reporter = reporters_reporter_4
    hq_reporterprofile_1.chw_id = u'-1'
    hq_reporterprofile_1.chw_username = u'joachim'
    hq_reporterprofile_1.domain = hq_domain_1
    hq_reporterprofile_1.organization = hq_organization_1
    hq_reporterprofile_1.guid = u'-1'
    hq_reporterprofile_1.approved = True
    hq_reporterprofile_1.active = True
    hq_reporterprofile_1.save()

    hq_reporterprofile_2 = ReporterProfile()
    hq_reporterprofile_2.reporter = reporters_reporter_3
    hq_reporterprofile_2.chw_id = u'11'
    hq_reporterprofile_2.chw_username = u'husseini'
    hq_reporterprofile_2.domain = hq_domain_1
    hq_reporterprofile_2.organization = hq_organization_1
    hq_reporterprofile_2.guid = u'11'
    hq_reporterprofile_2.approved = True
    hq_reporterprofile_2.active = True
    hq_reporterprofile_2.save()

    hq_reporterprofile_3 = ReporterProfile()
    hq_reporterprofile_3.reporter = reporters_reporter_5
    hq_reporterprofile_3.chw_id = u'0'
    hq_reporterprofile_3.chw_username = u'demo_user'
    hq_reporterprofile_3.domain = hq_domain_1
    hq_reporterprofile_3.organization = hq_organization_1
    hq_reporterprofile_3.guid = u'0'
    hq_reporterprofile_3.approved = True
    hq_reporterprofile_3.active = True
    hq_reporterprofile_3.save()

    hq_reporterprofile_4 = ReporterProfile()
    hq_reporterprofile_4.reporter = reporters_reporter_2
    hq_reporterprofile_4.chw_id = u'13'
    hq_reporterprofile_4.chw_username = u'njowine'
    hq_reporterprofile_4.domain = hq_domain_1
    hq_reporterprofile_4.organization = hq_organization_1
    hq_reporterprofile_4.guid = u'13'
    hq_reporterprofile_4.approved = True
    hq_reporterprofile_4.active = True
    hq_reporterprofile_4.save()

    from django.contrib.auth.models import User

    hq_extuser_1 = User()
    hq_extuser_1.username = u'bracadmin'
    hq_extuser_1.first_name = u''
    hq_extuser_1.last_name = u''
    hq_extuser_1.email = u'dmyung+bracadmin@dimagi.com'
    hq_extuser_1.password = u'sha1$25e8d$45cfe119a9429d066168a20255f737dbffef6488'
    hq_extuser_1.is_staff = False
    hq_extuser_1.is_active = True
    hq_extuser_1.is_superuser = True
    hq_extuser_1.last_login = datetime.datetime(2009, 4, 15, 10, 33, 29)
    hq_extuser_1.date_joined = datetime.datetime(2009, 4, 15, 10, 33, 29)
    hq_extuser_1.chw_id = None
    hq_extuser_1.chw_username = None
    hq_extuser_1.primary_phone = u'+16176453236'
    hq_extuser_1.domain = hq_domain_2
    hq_extuser_1.organization = None
    hq_extuser_1.reporter = None
    hq_extuser_1.save()

    hq_extuser_2 = User()
    hq_extuser_2.username = u'pfadmin'
    hq_extuser_2.first_name = u''
    hq_extuser_2.last_name = u''
    hq_extuser_2.email = u''
    hq_extuser_2.password = u'sha1$223b5$7e92dfc51c7ae3ad5b0fd4df4b52396630e72406'
    hq_extuser_2.is_staff = False
    hq_extuser_2.is_active = True
    hq_extuser_2.is_superuser = True
    hq_extuser_2.last_login = datetime.datetime(2009, 4, 24, 16, 53, 39)
    hq_extuser_2.date_joined = datetime.datetime(2009, 4, 15, 10, 34, 6)
    hq_extuser_2.chw_id = None
    hq_extuser_2.chw_username = None
    hq_extuser_2.primary_phone = u''
    hq_extuser_2.domain = hq_domain_1
    hq_extuser_2.organization = None
    hq_extuser_2.reporter = None
    hq_extuser_2.save()

    hq_extuser_3 = User()
    hq_extuser_3.username = u'gradmin'
    hq_extuser_3.first_name = u''
    hq_extuser_3.last_name = u''
    hq_extuser_3.email = u''
    hq_extuser_3.password = u'sha1$f8df4$5339016289f029e23e14466e735a3e8cf016b57f'
    hq_extuser_3.is_staff = False
    hq_extuser_3.is_active = True
    hq_extuser_3.is_superuser = True
    hq_extuser_3.last_login = datetime.datetime(2009, 4, 24, 16, 55, 24)
    hq_extuser_3.date_joined = datetime.datetime(2009, 4, 15, 10, 34, 38)
    hq_extuser_3.chw_id = None
    hq_extuser_3.chw_username = None
    hq_extuser_3.primary_phone = u''
    hq_extuser_3.domain = hq_domain_3
    hq_extuser_3.organization = None
    hq_extuser_3.reporter = None
    hq_extuser_3.save()

    hq_extuser_4 = User()
    hq_extuser_4.username = u'brian'
    hq_extuser_4.first_name = u''
    hq_extuser_4.last_name = u''
    hq_extuser_4.email = u'dmyung+brian@dimagi.com'
    hq_extuser_4.password = u'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
    hq_extuser_4.is_staff = False
    hq_extuser_4.is_active = True
    hq_extuser_4.is_superuser = True
    hq_extuser_4.last_login = datetime.datetime(2009, 4, 24, 17, 1, 40)
    hq_extuser_4.date_joined = datetime.datetime(2009, 4, 15, 10, 35, 1)
    hq_extuser_4.chw_id = None
    hq_extuser_4.chw_username = None
    hq_extuser_4.primary_phone = u'+16174016544'
    hq_extuser_4.domain = hq_domain_2
    hq_extuser_4.organization = None
    hq_extuser_4.reporter = None
    hq_extuser_4.save()

    hq_extuser_5 = User()
    hq_extuser_5.username = u'gayo'
    hq_extuser_5.first_name = u''
    hq_extuser_5.last_name = u''
    hq_extuser_5.email = u'dmyung+gayo@dimagi.com'
    hq_extuser_5.password = u'sha1$2aa9b$f8ce3e507b719c97d8442e518f8632c4454e686f'
    hq_extuser_5.is_staff = False
    hq_extuser_5.is_active = True
    hq_extuser_5.is_superuser = False
    hq_extuser_5.last_login = datetime.datetime(2009, 4, 15, 10, 35, 25)
    hq_extuser_5.date_joined = datetime.datetime(2009, 4, 15, 10, 35, 25)
    hq_extuser_5.chw_id = None
    hq_extuser_5.chw_username = None
    hq_extuser_5.primary_phone = u'+16174016544'
    hq_extuser_5.domain = hq_domain_2
    hq_extuser_5.organization = None
    hq_extuser_5.reporter = None
    hq_extuser_5.save()

    hq_extuser_6 = User()
    hq_extuser_6.username = u'pf1'
    hq_extuser_6.first_name = u''
    hq_extuser_6.last_name = u''
    hq_extuser_6.email = u''
    hq_extuser_6.password = u'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
    hq_extuser_6.is_staff = False
    hq_extuser_6.is_active = True
    hq_extuser_6.is_superuser = False
    hq_extuser_6.last_login = datetime.datetime(2009, 4, 15, 10, 57, 13)
    hq_extuser_6.date_joined = datetime.datetime(2009, 4, 15, 10, 57, 13)
    hq_extuser_6.chw_id = None
    hq_extuser_6.chw_username = None
    hq_extuser_6.primary_phone = u''
    hq_extuser_6.domain = hq_domain_1
    hq_extuser_6.organization = None
    hq_extuser_6.reporter = None
    hq_extuser_6.save()

    hq_extuser_7 = User()
    hq_extuser_7.username = u'pf2'
    hq_extuser_7.first_name = u''
    hq_extuser_7.last_name = u''
    hq_extuser_7.email = u''
    hq_extuser_7.password = u'sha1$245de$137d06d752eee1885a6bbd1e40cbe9150043dd5e'
    hq_extuser_7.is_staff = False
    hq_extuser_7.is_active = True
    hq_extuser_7.is_superuser = False
    hq_extuser_7.last_login = datetime.datetime(2009, 4, 15, 10, 57, 31)
    hq_extuser_7.date_joined = datetime.datetime(2009, 4, 15, 10, 57, 31)
    hq_extuser_7.chw_id = None
    hq_extuser_7.chw_username = None
    hq_extuser_7.primary_phone = u''
    hq_extuser_7.domain = hq_domain_1
    hq_extuser_7.organization = None
    hq_extuser_7.reporter = None
    hq_extuser_7.save()

    hq_extuser_8 = User()
    hq_extuser_8.username = u'br1'
    hq_extuser_8.first_name = u''
    hq_extuser_8.last_name = u''
    hq_extuser_8.email = u''
    hq_extuser_8.password = u'sha1$f0e70$8d5487476afde09a4a35de8d6ef3b39fba0b4405'
    hq_extuser_8.is_staff = False
    hq_extuser_8.is_active = True
    hq_extuser_8.is_superuser = False
    hq_extuser_8.last_login = datetime.datetime(2009, 4, 15, 10, 57, 52)
    hq_extuser_8.date_joined = datetime.datetime(2009, 4, 15, 10, 57, 52)
    hq_extuser_8.chw_id = None
    hq_extuser_8.chw_username = None
    hq_extuser_8.primary_phone = u'+16176453236'
    hq_extuser_8.domain = hq_domain_2
    hq_extuser_8.organization = None
    hq_extuser_8.reporter = None
    hq_extuser_8.save()

    hq_extuser_9 = User()
    hq_extuser_9.username = u'br2'
    hq_extuser_9.first_name = u''
    hq_extuser_9.last_name = u''
    hq_extuser_9.email = u''
    hq_extuser_9.password = u'sha1$a4c05$da3d0998c0d01ded87ffcd26cefdd5db619c6927'
    hq_extuser_9.is_staff = False
    hq_extuser_9.is_active = True
    hq_extuser_9.is_superuser = False
    hq_extuser_9.last_login = datetime.datetime(2009, 4, 15, 10, 58, 7)
    hq_extuser_9.date_joined = datetime.datetime(2009, 4, 15, 10, 58, 7)
    hq_extuser_9.chw_id = None
    hq_extuser_9.chw_username = None
    hq_extuser_9.primary_phone = u'+16174016544'
    hq_extuser_9.domain = hq_domain_2
    hq_extuser_9.organization = None
    hq_extuser_9.reporter = None
    hq_extuser_9.save()

    hq_extuser_10 = User()
    hq_extuser_10.username = u'grdoc'
    hq_extuser_10.first_name = u''
    hq_extuser_10.last_name = u''
    hq_extuser_10.email = u''
    hq_extuser_10.password = u'sha1$9df33$4bb013b189b71d3cfefa6f8b867c7a500ea46f68'
    hq_extuser_10.is_staff = False
    hq_extuser_10.is_active = True
    hq_extuser_10.is_superuser = False
    hq_extuser_10.last_login = datetime.datetime(2009, 4, 22, 14, 45, 11)
    hq_extuser_10.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 11)
    hq_extuser_10.chw_id = None
    hq_extuser_10.chw_username = None
    hq_extuser_10.primary_phone = u''
    hq_extuser_10.domain = hq_domain_3
    hq_extuser_10.organization = None
    hq_extuser_10.reporter = None
    hq_extuser_10.save()

    hq_extuser_11 = User()
    hq_extuser_11.username = u'grsupervisor'
    hq_extuser_11.first_name = u''
    hq_extuser_11.last_name = u''
    hq_extuser_11.email = u'dmyung+grsupervisor@dimagi.com'
    hq_extuser_11.password = u'sha1$4c2a2$cec32be6824786e76488aea338f350c6bbceb8eb'
    hq_extuser_11.is_staff = False
    hq_extuser_11.is_active = True
    hq_extuser_11.is_superuser = False
    hq_extuser_11.last_login = datetime.datetime(2009, 4, 22, 14, 45, 36)
    hq_extuser_11.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 36)
    hq_extuser_11.chw_id = None
    hq_extuser_11.chw_username = None
    hq_extuser_11.primary_phone = u'+16174016544'
    hq_extuser_11.domain = hq_domain_3
    hq_extuser_11.organization = None
    hq_extuser_11.reporter = None
    hq_extuser_11.save()

    hq_extuser_12 = User()
    hq_extuser_12.username = u'grmobile1'
    hq_extuser_12.first_name = u''
    hq_extuser_12.last_name = u''
    hq_extuser_12.email = u''
    hq_extuser_12.password = u'sha1$ecda0$0728c9c311d4308333bb62058c1f2e979d2899ea'
    hq_extuser_12.is_staff = False
    hq_extuser_12.is_active = True
    hq_extuser_12.is_superuser = False
    hq_extuser_12.last_login = datetime.datetime(2009, 4, 22, 14, 45, 55)
    hq_extuser_12.date_joined = datetime.datetime(2009, 4, 22, 14, 45, 55)
    hq_extuser_12.chw_id = None
    hq_extuser_12.chw_username = None
    hq_extuser_12.primary_phone = u''
    hq_extuser_12.domain = hq_domain_3
    hq_extuser_12.organization = None
    hq_extuser_12.reporter = None
    hq_extuser_12.save()

    hq_extuser_13 = User()
    hq_extuser_13.username = u'grmobile2'
    hq_extuser_13.first_name = u''
    hq_extuser_13.last_name = u''
    hq_extuser_13.email = u''
    hq_extuser_13.password = u'sha1$6b5c2$12023bfbeb8ac8614d9d7800444f4b2053c67f3e'
    hq_extuser_13.is_staff = False
    hq_extuser_13.is_active = True
    hq_extuser_13.is_superuser = False
    hq_extuser_13.last_login = datetime.datetime(2009, 4, 22, 14, 46, 11)
    hq_extuser_13.date_joined = datetime.datetime(2009, 4, 22, 14, 46, 11)
    hq_extuser_13.chw_id = None
    hq_extuser_13.chw_username = None
    hq_extuser_13.primary_phone = u''
    hq_extuser_13.domain = hq_domain_3
    hq_extuser_13.organization = None
    hq_extuser_13.reporter = None
    hq_extuser_13.save()

    hq_extuser_14 = User()
    hq_extuser_14.username = u'mvpadmin'
    hq_extuser_14.first_name = u''
    hq_extuser_14.last_name = u''
    hq_extuser_14.email = u''
    hq_extuser_14.password = u'sha1$65d24$447a3770156eb7d91381819b14fb9c7a07ce15eb'
    hq_extuser_14.is_staff = False
    hq_extuser_14.is_active = True
    hq_extuser_14.is_superuser = True
    hq_extuser_14.last_login = datetime.datetime(2009, 4, 30, 13, 49, 20)
    hq_extuser_14.date_joined = datetime.datetime(2009, 4, 30, 13, 20, 36)
    hq_extuser_14.chw_id = u'000'
    hq_extuser_14.chw_username = None
    hq_extuser_14.primary_phone = u''
    hq_extuser_14.domain = hq_domain_4
    hq_extuser_14.organization = None
    hq_extuser_14.reporter = None
    hq_extuser_14.save()

    hq_extuser_15 = User()
    hq_extuser_15.username = u'mvpuser1'
    hq_extuser_15.first_name = u''
    hq_extuser_15.last_name = u''
    hq_extuser_15.email = u''
    hq_extuser_15.password = u'resetme'
    hq_extuser_15.is_staff = False
    hq_extuser_15.is_active = True
    hq_extuser_15.is_superuser = False
    hq_extuser_15.last_login = datetime.datetime(2009, 4, 30, 13, 21, 57)
    hq_extuser_15.date_joined = datetime.datetime(2009, 4, 30, 13, 21, 57)
    hq_extuser_15.chw_id = u'001'
    hq_extuser_15.chw_username = None
    hq_extuser_15.primary_phone = u''
    hq_extuser_15.domain = hq_domain_4
    hq_extuser_15.organization = None
    hq_extuser_15.reporter = None
    hq_extuser_15.save()







    hq_reportschedule_1.recipient_user = hq_extuser_1
    hq_reportschedule_1.save()
















    from graphing.models import GraphPref, GraphGroup

    graphing_graphpref_1 = GraphPref()
    graphing_graphpref_1.user = hq_extuser_4
    graphing_graphpref_1.save()
    graphing_graphpref_1.root_graphs = [GraphGroup.objects.get(id=5)]
    graphing_graphpref_1.save()
    
    graphing_graphpref_2 = GraphPref()
    graphing_graphpref_2.user = hq_extuser_3
    graphing_graphpref_2.save()
    graphing_graphpref_2.root_graphs = [GraphGroup.objects.get(id=1)]
    graphing_graphpref_2.save()
    
