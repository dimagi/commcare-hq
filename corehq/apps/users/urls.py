from django.conf.urls import include, re_path as url

from corehq.apps.domain.utils import grandfathered_domain_re
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher

from .views import (
    DefaultProjectUserSettingsView,
    EditWebUserView,
    EnterpriseUsersView,
    InviteWebUserView,
    UploadWebUsers,
    WebUserUploadStatusView,
    ListRolesView,
    ListWebUsersView,
    add_domain_membership,
    change_password,
    delete_phone_number,
    delete_request,
    check_sso_trust,
    delete_user_role,
    domain_accounts,
    make_phone_number_default,
    paginate_enterprise_users,
    paginate_web_users,
    post_user_role,
    register_fcm_device_token,
    remove_web_user,
    test_httpdigest,
    undo_remove_web_user,
    verify_phone_number,
    download_web_users,
    DownloadWebUsersStatusView,
    WebUserUploadJobPollView,
)
from .views.web import (
    accept_invitation,
    delete_invitation,
    DomainRequestView,
    reinvite_web_user,
)
from .views.mobile.custom_data_fields import UserFieldsView
from .views.mobile.groups import (
    BulkSMSVerificationView,
    EditGroupMembersView,
    GroupsListView,
)
from .views.mobile.users import (
    CommCareUserConfirmAccountBySMSView,
    CommCareUsersLookup,
    ConfirmBillingAccountForExtraUsersView,
    ConfirmTurnOffDemoModeView,
    CreateCommCareUserModal,
    DemoRestoreStatusView,
    DeleteCommCareUsers,
    DownloadUsersStatusView,
    EditCommCareUserView,
    FilteredCommCareUserDownload,
    FilteredWebUserDownload,
    MobileWorkerListView,
    UploadCommCareUsers,
    UserUploadStatusView,
    activate_commcare_user,
    count_commcare_users,
    count_web_users,
    deactivate_commcare_user,
    delete_commcare_user,
    demo_restore_job_poll,
    download_commcare_users,
    force_user_412,
    paginate_mobile_workers,
    reset_demo_user_restore,
    restore_commcare_user,
    toggle_demo_mode,
    update_user_groups,
    user_download_job_poll,
    CommCareUserConfirmAccountView,
    send_confirmation_email,
    send_confirmation_sms,
    CommcareUserUploadJobPollView,
    ClearCommCareUsers,
    link_connectid_user,
)
from ..hqwebapp.decorators import waf_allow


user_management_urls = [
    UserManagementReportDispatcher.url_pattern(),
]


urlpatterns = [
    url(r'^$', DefaultProjectUserSettingsView.as_view(), name=DefaultProjectUserSettingsView.urlname),
    url(r'^change_password/(?P<login_id>[ \w-]+)/$', change_password, name="change_password"),
    url(r'^domain_accounts/(?P<couch_user_id>[ \w-]+)/$', domain_accounts, name='domain_accounts'),
    url(r'^delete_phone_number/(?P<couch_user_id>[ \w-]+)/$', delete_phone_number, name='delete_phone_number'),
    url(
        r'^make_phone_number_default/(?P<couch_user_id>[ \w-]+)/$',
        make_phone_number_default,
        name='make_phone_number_default'
    ),
    url(r'^verify_phone_number/(?P<couch_user_id>[ \w-]+)/$', verify_phone_number, name='verify_phone_number'),
    url(
        r'^add_domain_membership/(?P<couch_user_id>[ \w-]+)/(?P<domain_name>%s)/$' % grandfathered_domain_re,
        add_domain_membership,
        name='add_domain_membership'
    ),
    url(r'^web/account/(?P<couch_user_id>[ \w-]+)/$', EditWebUserView.as_view(), name=EditWebUserView.urlname),
    url(r'^web/remove/(?P<couch_user_id>[ \w-]+)/$', remove_web_user, name='remove_web_user'),
    url(r'^web/undo_remove/(?P<record_id>[ \w-]+)/$', undo_remove_web_user, name='undo_remove_web_user'),
    url(r'^web/invite/$', InviteWebUserView.as_view(), name=InviteWebUserView.urlname),
    url(r'^web/reinvite/$', reinvite_web_user, name='reinvite_web_user'),
    url(r'^web/request/$', DomainRequestView.as_view(), name=DomainRequestView.urlname),
    url(r'^web/delete_invitation/$', delete_invitation, name='delete_invitation'),
    url(r'^web/delete_request/$', delete_request, name='delete_request'),
    url(r'^web/check_sso_trust/$', check_sso_trust, name='check_sso_trust'),
    url(r'^web/$', ListWebUsersView.as_view(), name=ListWebUsersView.urlname),
    url(r'^web/json/$', paginate_web_users, name='paginate_web_users'),
    url(r'^web/download/$', download_web_users, name='download_web_users'),
    url(
        r'^web/download/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        DownloadWebUsersStatusView.as_view(),
        name='download_web_users_status'
    ),
    url(r'^web/filter_and_download/$', FilteredWebUserDownload.as_view(), name=FilteredWebUserDownload.urlname),
    url(r'^web/count_users/$', count_web_users, name='count_web_users'),
    url(r'^web/upload/$', waf_allow('XSS_BODY')(UploadWebUsers.as_view()), name=UploadWebUsers.urlname),
    url(
        r'^web/upload/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        WebUserUploadStatusView.as_view(),
        name=WebUserUploadStatusView.urlname
    ),
    url(
        r'^web/upload/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        WebUserUploadJobPollView.as_view(),
        name=WebUserUploadJobPollView.urlname
    ),
    url(r'^enterprise/$', EnterpriseUsersView.as_view(), name=EnterpriseUsersView.urlname),
    url(r'^enterprise/json/$', paginate_enterprise_users, name='paginate_enterprise_users'),
    url(r'^join/(?P<uuid>[ \w-]+)/$', accept_invitation, name='domain_accept_invitation'),
    url(r'^roles/$', ListRolesView.as_view(), name=ListRolesView.urlname),
    url(r'^roles/save/$', post_user_role, name='post_user_role'),
    url(r'^roles/delete/$', delete_user_role, name='delete_user_role'),
    url(
        r'^register_fcm_device_token/(?P<couch_user_id>[ \w-]+)/(?P<device_token>[ \w-]+)/$',
        register_fcm_device_token,
        name='register_fcm_device_token'
    ),
    url(r'^httpdigest/?$', test_httpdigest, name='test_httpdigest'),
] + [
    url(r'^commcare/$', MobileWorkerListView.as_view(), name=MobileWorkerListView.urlname),
    url(r'^commcare/json/$', paginate_mobile_workers, name='paginate_mobile_workers'),
    url(r'^user_data/$', waf_allow('XSS_BODY')(UserFieldsView.as_view()), name=UserFieldsView.urlname),
    url(
        r'^commcare/account/(?P<couch_user_id>[ \w-]+)/$',
        EditCommCareUserView.as_view(),
        name=EditCommCareUserView.urlname
    ),
    url(r'^commcare/account/(?P<couch_user_id>[ \w-]+)/groups/$', update_user_groups, name='update_user_groups'),
    url(r'^commcare/activate/(?P<user_id>[ \w-]+)/$', activate_commcare_user, name='activate_commcare_user'),
    url(r'^commcare/deactivate/(?P<user_id>[ \w-]+)/$', deactivate_commcare_user, name='deactivate_commcare_user'),
    url(
        r'^commcare/send_confirmation_email/(?P<user_id>[ \w-]+)/$',
        send_confirmation_email,
        name='send_confirmation_email'
    ),
    url(r'^commcare/delete/(?P<user_id>[ \w-]+)/$', delete_commcare_user, name='delete_commcare_user'),
    url(r'^commcare/force_412/(?P<user_id>[ \w-]+)/$', force_user_412, name='force_user_412'),
    url(r'^commcare/restore/(?P<user_id>[ \w-]+)/$', restore_commcare_user, name='restore_commcare_user'),
    url(r'^commcare/toggle_demo_mode/(?P<user_id>[ \w-]+)/$', toggle_demo_mode, name='toggle_demo_mode'),
    url(
        r'^commcare/confirm_turn_off_demo_mode/(?P<couch_user_id>[ \w-]+)/$',
        ConfirmTurnOffDemoModeView.as_view(),
        name=ConfirmTurnOffDemoModeView.urlname
    ),
    url(r'^commcare/delete/$', DeleteCommCareUsers.as_view(), name=DeleteCommCareUsers.urlname),
    url(r'^commcare/clear/$', ClearCommCareUsers.as_view(), name=ClearCommCareUsers.urlname),
    url(r'^commcare/lookup/$', CommCareUsersLookup.as_view(), name=CommCareUsersLookup.urlname),
    url(
        r'^commcare/reset_demo_user_restore/(?P<user_id>[ \w-]+)/$',
        reset_demo_user_restore,
        name='reset_demo_user_restore'
    ),
    url(
        r'^commcare/demo_restore/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/(?P<user_id>[ \w-]+)/$',
        DemoRestoreStatusView.as_view(),
        name=DemoRestoreStatusView.urlname
    ),
    url(
        r'^commcare/demo_restore/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        demo_restore_job_poll,
        name='demo_restore_job_poll'
    ),
    url(
        r'^commcare/upload/$',
        waf_allow('XSS_BODY')(UploadCommCareUsers.as_view()),
        name=UploadCommCareUsers.urlname
    ),
    url(
        r'^commcare/upload/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        UserUploadStatusView.as_view(),
        name=UserUploadStatusView.urlname
    ),
    url(
        r'^commcare/upload/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        CommcareUserUploadJobPollView.as_view(),
        name=CommcareUserUploadJobPollView.urlname
    ),
    url(r'^commcare/download/$', download_commcare_users, name='download_commcare_users'),
    url(
        r'^commcare/filter_and_download/$',
        FilteredCommCareUserDownload.as_view(),
        name=FilteredCommCareUserDownload.urlname
    ),
    url(r'^commcare/count_users/$', count_commcare_users, name='count_commcare_users'),
    url(
        r'^commcare/download/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        DownloadUsersStatusView.as_view(),
        name=DownloadUsersStatusView.urlname
    ),
    url(
        r'^commcare/download/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        user_download_job_poll,
        name='user_download_job_poll'
    ),
    url(
        r'^commcare/new_mobile_worker_modal/$',
        CreateCommCareUserModal.as_view(),
        name=CreateCommCareUserModal.urlname
    ),
    url(
        r'^commcare/confirm_charges/$',
        ConfirmBillingAccountForExtraUsersView.as_view(),
        name=ConfirmBillingAccountForExtraUsersView.urlname
    ),
    url(
        r'^commcare/confirm_account/(?P<user_id>[\w-]+)/$',
        CommCareUserConfirmAccountView.as_view(),
        name=CommCareUserConfirmAccountView.urlname
    ),
    url(
        r'^commcare/send_confirmation_sms/(?P<user_id>[ \w-]+)/$',
        send_confirmation_sms,
        name='send_confirmation_sms'
    ),
    url(
        r'^commcare/confirm_account_sms/(?P<user_invite_hash>[\S-]+)/$',
        CommCareUserConfirmAccountBySMSView.as_view(),
        name=CommCareUserConfirmAccountBySMSView.urlname
    ),
    url(
        r'^commcare/link_connectid_user/$',
        link_connectid_user,
        name='link_connectid_user'
    ),
] + [
    url(r'^groups/$', GroupsListView.as_view(), name=GroupsListView.urlname),
    url(r'^groups/(?P<group_id>[ \w-]+)/$', EditGroupMembersView.as_view(), name=EditGroupMembersView.urlname),
    url(
        r'^groups/sms_verification/(?P<group_id>[ \w-]+)$',
        BulkSMSVerificationView.as_view(),
        name=BulkSMSVerificationView.urlname
    ),
] + [
    url(r'^reports/', include(user_management_urls)),
]
