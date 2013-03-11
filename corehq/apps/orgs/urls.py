from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.orgs.views',
    url(r'^(?P<org>[\w\.-]+)/$', 'orgs_landing', name='orgs_landing'),
    url(r'^(?P<org>[\w\.-]+)/update_info/$', 'orgs_update_info', name='orgs_update_info'),
    url(r'^(?P<org>[\w\.-]+)/get_data/$', 'get_data', name='get_data'),
    url(r'^(?P<org>[\w\.-]+)/add_project/$', 'orgs_add_project', name='orgs_add_project'),
    url(r'^(?P<org>[\w\.-]+)/new_project/$', 'orgs_new_project', name='orgs_new_project'),
    url(r'^(?P<org>[\w\.-]+)/update_project_info/$', 'orgs_update_project', name='orgs_update_project'),
    url(r'^(?P<org>[\w\.-]+)/remove_project/$', 'orgs_remove_project', name='orgs_remove_project'),
    url(r'^(?P<org>[\w\.-]+)/invite_member/$', 'invite_member', name='orgs_invite_member'),
    url(r'^(?P<org>[\w\.-]+)/remove_member/$', 'remove_member', name='orgs_remove_member'),
    url(r'^(?P<org>[\w\.-]+)/add_team/$', 'orgs_add_team', name='orgs_add_team'),
    url(r'^(?P<org>[\w\.-]+)/logo/$', 'orgs_logo', name='orgs_logo'),
    url(r'^(?P<org>[\w\.-]+)/members/$', 'orgs_members', name='orgs_members'),

    url(r'^(?P<org>[\w\.-]+)/teams/$', 'orgs_teams', name='orgs_teams'),
    url(r'^(?P<org>[\w\.-]+)/update_team_info/$', 'orgs_update_team', name='orgs_update_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/$', 'orgs_team_members', name='orgs_team_members'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/add_all$', 'add_all_to_team', name='add_all_to_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/remove_all$', 'remove_all_from_team', name='remove_all_from_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/add_domain$', 'add_domain_to_team', name='add_domain_to_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/set_permission$', 'set_team_permission_for_domain', name='set_team_permission_for_domain'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/remove_domain$', 'remove_domain_from_team', name='remove_domain_from_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/delete_team$', 'delete_team', name='delete_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<record_id>[ \w-]+)/undo_delete_team', 'undo_delete_team', name='undo_delete_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<record_id>[ \w-]+)/undo_remove_member', 'undo_remove_member', name='undo_remove_member'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/join_team$', 'join_team', name='join_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/leave_team$', 'leave_team', name='leave_team'),

    url(r'^(?P<org>[\w\.-]+)/join/(?P<invitation_id>[ \w-]+)/$', 'accept_invitation', name='orgs_accept_invitation'),
    url(r'^(?P<org>[\w\.-]+)/seen_request/$', 'seen_request', name='orgs_seen'),
    url(r'^(?P<org>[\w\.-]+)/verify_org/$', 'verify_org', name='verify_org'),
)

organizations_urls = patterns('corehq.apps.orgs.views',
    url(r'^$', 'orgs_base', name='orgs_base'),
    url(r'^(?P<org>[\w\.-]+)/$', 'public', name='orgs_public'),
)
