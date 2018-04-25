/* eslint-env mocha */
/* global $, sinon */

describe('requirejs', function() {
    it('should load modules', function(done) {
        requirejs.config({
            deps: ['knockout', 'ko.mapping'],
            callback: function (ko, mapping) {
                ko.mapping = mapping;
            },
        });
        requirejs([
            'hqwebapp/js/initial_page_data',
            'analytix/js/google',
            'analytix/js/kissmetrix',
        ], function(
            initialPageData,
            google,
            kissmetrics,
        ) {
            initialPageData.reverse = function(path) {
                return path;
            };
            google.track.event = sinon.spy();
            google.track.click = sinon.spy();
            kissmetrics.track.event = sinon.spy();

            // Prevent modules from throwing errors when loaded in this artificial context
            $.holdReady(true);

            requirejs([
                'accounting/js/base_subscriptions_main',
                'accounting/js/billing_account_form',
                'accounting/js/subscriptions_main',
                'hqwebapp/js/crud_paginated_list_init',
                'accounting/js/widgets',
                'accounting/js/widgets',
                'accounting/js/widgets',
                'accounting/js/software_plan_version_handler',
                'accounting/js/invoice_main',
                'dashboard/js/dashboard',
                'domain/js/pro-bono',
                'data_dictionary/js/data_dictionary',
                'domain/js/pro-bono',
                'hqwebapp/js/crud_paginated_list_init',
                'groups/js/all_groups',
                'fixtures/js/lookup-manage',
                'fixtures/js/view-table',
                'hqadmin/js/system_info',
                'hqwebapp/js/crud_paginated_list_init',
                'reminders/js/reminders.keywords.ko',
                'linked_domain/js/domain_links',
                'hqwebapp/js/crud_paginated_list_init',
                'sms/js/manage_registration_invitations',
                'hqwebapp/js/crud_paginated_list_init',
                'toggle_ui/js/flags',
                'toggle_ui/js/edit-flag',
                'hqwebapp/js/bulk_upload_file',
            ], function() {
                done();
            }, function(err) {
                assert.fail(err);
            });
        });
    });
});
