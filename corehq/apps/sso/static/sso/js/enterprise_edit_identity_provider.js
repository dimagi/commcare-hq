hqDefine('sso/js/enterprise_edit_identity_provider', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/utils/email',
    "hqwebapp/js/initial_page_data",
    'sso/js/models',
    'hqwebapp/js/bootstrap3/widgets',
], function (
    $,
    ko,
    _,
    emailUtils,
    initialPageData,
    models
) {
    'use strict';
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

        let remoteUserManagementAPISecretManager = function () {
            let self = {};
            self.isCancelUpdateVisible = ko.observable(false);
            self.apiExpirationDate = "";

            self.dateApiSecretExpiration = ko.observable($('#id_date_api_secret_expiration').val());
            self.isAPISecretVisible = ko.observable($('#masked-api-value').text() === '');
            self.apiSecret = ko.observable();

            self.startEditingAPISecret = function () {
                self.isAPISecretVisible(true);
                self.isCancelUpdateVisible(true);
                // Store the current expiration date before clearing them for editing.
                self.apiExpirationDate = self.dateApiSecretExpiration();
                self.dateApiSecretExpiration('');
            };

            self.cancelEditingAPISecret = function () {
                self.isAPISecretVisible(false);
                self.isCancelUpdateVisible(false);
                // Reset the api secret to blank if user cancel editing
                self.apiSecret('');
                // Restore the original values of expiration date after canceling editing.
                self.dateApiSecretExpiration(self.apiExpirationDate);

            };
            return self;

        };

        if (initialPageData.get('toggle_api_secret')) {
            $('#idp').koApplyBindings(remoteUserManagementAPISecretManager);
        }


        if (initialPageData.get('toggle_client_secret')) {
            $('#idp').koApplyBindings(oidcClientSecretManager);
        }
    });
});
