hqDefine('sso/js/enterprise_edit_identity_provider', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/utils/email',
    "hqwebapp/js/initial_page_data",
    'sso/js/models',
], function (
    $,
    ko,
    _,
    emailUtils,
    initialPageData,
    models
) {
    $(function () {
        let ssoExemptUserManager = models.linkedObjectListModel({
            asyncHandler: 'sso_exempt_users_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: emailUtils.validateEmail,
        });
        $('#sso-exempt-user-manager').koApplyBindings(ssoExemptUserManager);
        ssoExemptUserManager.init();

        let ssoTestUserManager = models.linkedObjectListModel({
            asyncHandler: 'sso_test_users_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: emailUtils.validateEmail,
        });
        $('#sso-test-user-manager').koApplyBindings(ssoTestUserManager);
        ssoTestUserManager.init();

        let oidcClientSecretManager = function () {
            'use strict';
            let self = {};

            self.isClientSecretVisible = ko.observable(false);
            self.isClientSecretHidden = ko.computed(function () {
                return !self.isClientSecretVisible();
            });

            self.showClientSecret = function () {
                self.isClientSecretVisible(true);
            };

            self.hideClientSecret = function () {
                self.isClientSecretVisible(false);
            };

            return self;

        };

        if (initialPageData.get('toggle_client_secret')) {
            $('#idp').koApplyBindings(oidcClientSecretManager);
        }
    });
});
