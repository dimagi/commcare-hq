hqDefine('sso/js/edit_identity_provider', [
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'sso/js/models',
], function (
    $,
    ko,
    _,
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
            }
        });
        $('#email-domain-manager').koApplyBindings(emailDomainManager);
        emailDomainManager.init();

        var ssoExemptUserManager = models.linkedObjectListModel({
            asyncHandler: 'sso_exempt_users_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: function (newObject) {
                // from http://stackoverflow.com/questions/46155/validate-email-address-in-javascript
                var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/; // eslint-disable-line no-useless-escape
                return re.test(newObject);
            }
        });
        $('#sso-exempt-user-manager').koApplyBindings(ssoExemptUserManager);
        ssoExemptUserManager.init();

    });
});
