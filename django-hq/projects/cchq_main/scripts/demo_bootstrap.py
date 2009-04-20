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
    auth_user_1.last_login = datetime.datetime(2009, 4, 15, 11, 24)
    auth_user_1.date_joined = datetime.datetime(2009, 4, 15, 10, 30, 52)
    auth_user_1.save()

    from django.contrib.auth.models import Message


    from django.contrib.sessions.models import Session

    django_session_1 = Session()
    django_session_1.session_key = u'c6955d1bbf078f28a00b578700d89e66'
    django_session_1.session_data = u'gAJ9cQEoVRJfYXV0aF91c2VyX2JhY2tlbmRxAlUpZGphbmdvLmNvbnRyaWIuYXV0aC5iYWNrZW5k\ncy5Nb2RlbEJhY2tlbmRxA1UNX2F1dGhfdXNlcl9pZHEEigEFdS41NTc1NDQwZmE3NzgyMjA1NDJj\nMTNkYjc2ZTVmNzM5OA==\n'
    django_session_1.expire_date = datetime.datetime(2009, 4, 29, 11, 25, 4)
    django_session_1.save()

    from django.contrib.sites.models import Site

    django_site_1 = Site()
    django_site_1.domain = u'example.com'
    django_site_1.name = u'example.com'
    django_site_1.save()
    
    from dbanalyzer.models import RawGraph

    dbanalyzer_rawgraph_1 = RawGraph()
    dbanalyzer_rawgraph_1.shortname = u'User Daily Submissions'
    dbanalyzer_rawgraph_1.title = u'Submissions by User (daily count)'
    dbanalyzer_rawgraph_1.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_1.data_source = u''
    dbanalyzer_rawgraph_1.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), username, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), username\r\norder by timeend asc;"
    dbanalyzer_rawgraph_1.x_axis_label = u'Date'
    dbanalyzer_rawgraph_1.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_1.series_labels = u'Username'
    dbanalyzer_rawgraph_1.display_type = u'compare-trend'
    dbanalyzer_rawgraph_1.series_options = u''
    dbanalyzer_rawgraph_1.save()

    dbanalyzer_rawgraph_2 = RawGraph()
    dbanalyzer_rawgraph_2.shortname = u'Total User Submissions'
    dbanalyzer_rawgraph_2.title = u'All Submissions by User'
    dbanalyzer_rawgraph_2.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_2.data_source = u''
    dbanalyzer_rawgraph_2.db_query = u'select distinct(username), count(*) from x_http__www_commcare_org_brac_chp_homevisit_v0_0_1 group by username'
    dbanalyzer_rawgraph_2.x_axis_label = u'Username'
    dbanalyzer_rawgraph_2.x_type = u'string'
    dbanalyzer_rawgraph_2.series_labels = u'count'
    dbanalyzer_rawgraph_2.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_2.series_options = u''
    dbanalyzer_rawgraph_2.save()

    dbanalyzer_rawgraph_3 = RawGraph()
    dbanalyzer_rawgraph_3.shortname = u'Overall Submissions by User'
    dbanalyzer_rawgraph_3.title = u'Overall Submissions by all users (cumulative)'
    dbanalyzer_rawgraph_3.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_3.data_source = u''
    dbanalyzer_rawgraph_3.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), username, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), username\r\norder by timeend asc;"
    dbanalyzer_rawgraph_3.x_axis_label = u'Date'
    dbanalyzer_rawgraph_3.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_3.series_labels = u'0'
    dbanalyzer_rawgraph_3.display_type = u'compare-cumulative'
    dbanalyzer_rawgraph_3.series_options = u''
    dbanalyzer_rawgraph_3.save()

    dbanalyzer_rawgraph_4 = RawGraph()
    dbanalyzer_rawgraph_4.shortname = u'Histogram of all referrals'
    dbanalyzer_rawgraph_4.title = u'Overall Given Referrals'
    dbanalyzer_rawgraph_4.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_4.data_source = u'commcarehq'
    dbanalyzer_rawgraph_4.db_query = u'select distinct(referral_given), count(*) from x_http__www_commcare_org_brac_chp_homevisit_v0_0_1 group by referral_given'
    dbanalyzer_rawgraph_4.x_axis_label = u'val'
    dbanalyzer_rawgraph_4.x_type = u'string'
    dbanalyzer_rawgraph_4.series_labels = u'0'
    dbanalyzer_rawgraph_4.display_type = u'histogram-overall'
    dbanalyzer_rawgraph_4.series_options = u''
    dbanalyzer_rawgraph_4.save()

    dbanalyzer_rawgraph_5 = RawGraph()
    dbanalyzer_rawgraph_5.shortname = u'Global Referral Trends'
    dbanalyzer_rawgraph_5.title = u'Global Referral Trends (cumulative)'
    dbanalyzer_rawgraph_5.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_5.data_source = u''
    dbanalyzer_rawgraph_5.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given\r\norder by timeend asc;"
    dbanalyzer_rawgraph_5.x_axis_label = u''
    dbanalyzer_rawgraph_5.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_5.series_labels = u'asdf'
    dbanalyzer_rawgraph_5.display_type = u'compare-cumulative'
    dbanalyzer_rawgraph_5.series_options = u''
    dbanalyzer_rawgraph_5.save()

    dbanalyzer_rawgraph_6 = RawGraph()
    dbanalyzer_rawgraph_6.shortname = u'Global Daily Referral Count'
    dbanalyzer_rawgraph_6.title = u'Global Report of Inbound Referrals (daily count)'
    dbanalyzer_rawgraph_6.table_name = u'x_http__www_commcare_org_brac_chp_homevisit_v0_0_1'
    dbanalyzer_rawgraph_6.data_source = u''
    dbanalyzer_rawgraph_6.db_query = u"select\r\n  DATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given, count(*)\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1\r\ngroup by\r\nDATE_FORMAT(timeend,'%%m/%%d/%%Y'), referral_given\r\norder by timeend asc;"
    dbanalyzer_rawgraph_6.x_axis_label = u''
    dbanalyzer_rawgraph_6.x_type = u'MM/DD/YYYY'
    dbanalyzer_rawgraph_6.series_labels = u'referral'
    dbanalyzer_rawgraph_6.display_type = u'compare-trend'
    dbanalyzer_rawgraph_6.series_options = u''
    dbanalyzer_rawgraph_6.save()

    dbanalyzer_rawgraph_7 = RawGraph()
    dbanalyzer_rawgraph_7.shortname = u'cumulative line'
    dbanalyzer_rawgraph_7.title = u'cumulative line'
    dbanalyzer_rawgraph_7.table_name = u'fasdfwdrf'
    dbanalyzer_rawgraph_7.data_source = u''
    dbanalyzer_rawgraph_7.db_query = u'select      \r\n   timeend,     \r\n   number_of_children,     \r\n   num_of_baby   \r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1;'
    dbanalyzer_rawgraph_7.x_axis_label = u'time'
    dbanalyzer_rawgraph_7.x_type = u'date'
    dbanalyzer_rawgraph_7.series_labels = u'0|1'
    dbanalyzer_rawgraph_7.display_type = u'cumulative-line'
    dbanalyzer_rawgraph_7.series_options = u''
    dbanalyzer_rawgraph_7.save()

    dbanalyzer_rawgraph_8 = RawGraph()
    dbanalyzer_rawgraph_8.shortname = u'absolute line'
    dbanalyzer_rawgraph_8.title = u'absolute line'
    dbanalyzer_rawgraph_8.table_name = u'sadf'
    dbanalyzer_rawgraph_8.data_source = u'asdf'
    dbanalyzer_rawgraph_8.db_query = u'select \r\n    timeend,\r\n    number_of_children,\r\n    num_of_baby \r\n\r\nfrom x_http__www_commcare_org_brac_chp_homevisit_v0_0_1;'
    dbanalyzer_rawgraph_8.x_axis_label = u'Time'
    dbanalyzer_rawgraph_8.x_type = u'date'
    dbanalyzer_rawgraph_8.series_labels = u'1|2'
    dbanalyzer_rawgraph_8.display_type = u'absolute-line'
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
    modelrelationship_edgetype_5.name = u'Domain Chart'
    modelrelationship_edgetype_5.description = u'Domain Chart'
    modelrelationship_edgetype_5.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edgetype_5.parent_type = ContentType.objects.get(app_label="organization", model="domain")
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
    modelrelationship_edge_13.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edge_13.child_id = 5L
    modelrelationship_edge_13.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_13.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_13.parent_id = 2L
    modelrelationship_edge_13.save()

    modelrelationship_edge_14 = Edge()
    modelrelationship_edge_14.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edge_14.child_id = 4L
    modelrelationship_edge_14.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_14.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_14.parent_id = 2L
    modelrelationship_edge_14.save()

    modelrelationship_edge_15 = Edge()
    modelrelationship_edge_15.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edge_15.child_id = 1L
    modelrelationship_edge_15.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_15.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_15.parent_id = 2L
    modelrelationship_edge_15.save()

    modelrelationship_edge_16 = Edge()
    modelrelationship_edge_16.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edge_16.child_id = 2L
    modelrelationship_edge_16.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_16.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_16.parent_id = 2L
    modelrelationship_edge_16.save()

    modelrelationship_edge_17 = Edge()
    modelrelationship_edge_17.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edge_17.child_id = 3L
    modelrelationship_edge_17.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_17.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_17.parent_id = 2L
    modelrelationship_edge_17.save()

    modelrelationship_edge_18 = Edge()
    modelrelationship_edge_18.child_type = ContentType.objects.get(app_label="dbanalyzer", model="rawgraph")
    modelrelationship_edge_18.child_id = 6L
    modelrelationship_edge_18.relationship = modelrelationship_edgetype_5
    modelrelationship_edge_18.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    modelrelationship_edge_18.parent_id = 2L
    modelrelationship_edge_18.save()



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
    organization_domain_3.name = u'Grameen-Intel'
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
    organization_extuser_2.last_login = datetime.datetime(2009, 4, 15, 10, 34, 6)
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
    organization_extuser_3.last_login = datetime.datetime(2009, 4, 15, 10, 34, 38)
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
    organization_extuser_4.last_login = datetime.datetime(2009, 4, 15, 11, 25, 4)
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
    organization_extuser_8.password = u'test'
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
    organization_extuser_9.password = u'test'
    organization_extuser_9.is_staff = False
    organization_extuser_9.is_active = True
    organization_extuser_9.is_superuser = False
    organization_extuser_9.last_login = datetime.datetime(2009, 4, 15, 10, 58, 7)
    organization_extuser_9.date_joined = datetime.datetime(2009, 4, 15, 10, 58, 7)
    organization_extuser_9.primary_phone = u'+12134897213'
    organization_extuser_9.domain = organization_domain_2
    organization_extuser_9.identity = None
    organization_extuser_9.save()

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

        
    from receiver.models import Submission


    from receiver.models import Backup


    from receiver.models import Attachment


    from xformmanager.models import FormDefData


    from xformmanager.models import ElementDefData


