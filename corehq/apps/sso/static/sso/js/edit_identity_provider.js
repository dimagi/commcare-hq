hqDefine('sso/js/edit_identity_provider', [
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
        var emailDomainManager = models.linkedObjectListModel({
            asyncHandler: 'identity_provider_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: function (newObject) {
                return newObject.length > 4
                    && newObject.indexOf('.') !== -1
                    && newObject.indexOf('@') === -1
                    && !newObject.endsWith('.');
            },
        });
        $('#email-domain-manager').koApplyBindings(emailDomainManager);
        emailDomainManager.init();

        var ssoExemptUserManager = models.linkedObjectListModel({
            asyncHandler: 'sso_exempt_users_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: emailUtils.validateEmail,
        });
        $('#sso-exempt-user-manager').koApplyBindings(ssoExemptUserManager);
        ssoExemptUserManager.init();

    });
});
