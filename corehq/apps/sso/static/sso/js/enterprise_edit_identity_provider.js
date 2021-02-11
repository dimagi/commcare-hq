hqDefine('sso/js/enterprise_edit_identity_provider', [
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'sso/js/models',
    'jquery-mousewheel',
    'datetimepicker',
], function (
    $,
    ko,
    _,
    initialPageData,
    models
) {
    $(function () {
        var ssoExemptUserManager = models.linkedObjectListModel({
            asyncHandler: 'sso_exempt_users_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: function (newObject) {
                // very basic email checking
                return newObject.length > 4
                    && newObject.indexOf('.') !== -1
                    && newObject.indexOf('@') > 1
                    && !newObject.endsWith('.');
            }
        });
        $('#sso-exempt-user-manager').koApplyBindings(ssoExemptUserManager);
        ssoExemptUserManager.init();

        $("#id_date_idp_cert_expiration").datetimepicker();
    });
});
