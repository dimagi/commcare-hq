from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.orgs.views',
    url(r'^(?P<org>[\w\.-]+)/$', 'orgs_landing', name='orgs_landing'),
    url(r'^(?P<org>[\w\.-]+)/update_info/$', 'orgs_update_info', name='orgs_update_info'),
    url(r'^(?P<org>[\w\.-]+)/get_data/$', 'get_data', name='get_data'),
    url(r'^(?P<org>[\w\.-]+)/add_project/$', 'orgs_add_project', name='orgs_add_project'),
    url(r'^(?P<org>[\w\.-]+)/new_project/$', 'orgs_new_project', name='orgs_new_project'),
    url(r'^(?P<org>[\w\.-]+)/invite_member/$', 'invite_member', name='orgs_invite_member'),
    url(r'^(?P<org>[\w\.-]+)/add_team/$', 'orgs_add_team', name='orgs_add_team'),
    url(r'^(?P<org>[\w\.-]+)/logo/$', 'orgs_logo', name='orgs_logo'),

    url(r'^(?P<org>[\w\.-]+)/teams/$', 'orgs_teams', name='orgs_teams'),
    url(r'^(?P<org>[\w\.-]+)/teams/add_team$', 'add_team', name='add_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/$', 'orgs_team_members', name='orgs_team_members'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/add_all$', 'add_all_to_team', name='add_all_to_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/remove_all$', 'remove_all_from_team', name='remove_all_from_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/(?P<domain>[\w-]+)/add_domain$', 'add_domain_to_team', name='add_domain_to_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/set_permission$', 'set_team_permission_for_domain', name='set_team_permission_for_domain'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/(?P<domain>[\w-]+)/remove_domain$', 'remove_domain_from_team', name='remove_domain_from_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/delete_team$', 'delete_team', name='delete_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<record_id>[ \w-]+)/undo_delete_team', 'undo_delete_team', name='undo_delete_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/(?P<couch_user_id>[\w-]+)/join_team$', 'join_team', name='join_team'),
    url(r'^(?P<org>[\w\.-]+)/teams/(?P<team_id>[ \w-]+)/(?P<couch_user_id>[\w-]+)/leave_team$', 'leave_team', name='leave_team'),

    url(r'^(?P<org>[\w\.-]+)/join/(?P<invitation_id>[ \w-]+)/$', 'accept_invitation', name='orgs_accept_invitation'),
    url(r'^(?P<org>[\w\.-]+)/seen_request/$', 'seen_request', name='orgs_seen'),
)
