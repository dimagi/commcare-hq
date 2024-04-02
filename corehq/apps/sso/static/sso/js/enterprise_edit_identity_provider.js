'use strict';

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

        let editEnterpriseIdPFormManager = function (showAPIFields) {
            let self = {};

            if (initialPageData.get('is_oidc')) {
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
            }

            if (initialPageData.get('show_remote_user_management')) {
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
            }

            if (showAPIFields) {
                const initialEnforce = document.forms['configuration']['enforce_user_api_key_expiration'].checked;
                self.initialExpirationLength =
                    document.forms['configuration']['max_days_until_user_api_key_expiration'].value;
                if (self.initialExpirationLength) {
                    self.initialExpirationLength = parseInt(self.initialExpirationLength, 10);
                }
                self.enforceExpiration = ko.observable(initialEnforce);
                self.expirationLengthValue = ko.observable(self.initialExpirationLength);
                self.expirationLength = ko.observable(null);
                self.expirationLengthValue.subscribe(function (newValue) {
                    if (newValue) {
                        const selValue = $('#id_max_days_until_user_api_key_expiration option:selected').text();
                        self.expirationLength(selValue);
                    }
                });
                self.showExpirationWarning = ko.pureComputed(function () {
                    return (
                        (self.initialExpirationLength === '' && self.expirationLengthValue() !== '') ||
                        (self.expirationLengthValue() < self.initialExpirationLength)
                    );
                });
            }

            return self;

        };
        const showAPIFields = initialPageData.get('show_api_fields');
        let formManager = new editEnterpriseIdPFormManager(showAPIFields);
        $('#idp').koApplyBindings(formManager);
    });
});
