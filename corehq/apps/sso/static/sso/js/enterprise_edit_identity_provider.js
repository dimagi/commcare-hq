hqDefine('sso/js/enterprise_edit_identity_provider', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/utils/email',
    "hqwebapp/js/initial_page_data",
    'sso/js/models',
    'eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min',
], function (
    $,
    ko,
    _,
    emailUtils,
    initialPageData,
    models
) {
    $(function () {
        var ssoExemptUserManager = models.linkedObjectListModel({
            asyncHandler: 'sso_exempt_users_admin',
            requestContext: {
                idpSlug: initialPageData.get('idp_slug'),
            },
            validateNewObjectFn: emailUtils.validateEmail,
        });
        $('#sso-exempt-user-manager').koApplyBindings(ssoExemptUserManager);
        ssoExemptUserManager.init();

        var $expDate = $("#id_date_idp_cert_expiration"),
            initialDate = $expDate.val();
        $expDate.datetimepicker({
            date: initialDate,
        });
    });
});
