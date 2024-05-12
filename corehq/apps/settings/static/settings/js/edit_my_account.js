hqDefine('settings/js/edit_my_account', [
    'jquery',
    'select2/dist/js/select2.full.min',
], function (
    $
) {
    $(function () {
        $('#id_language').select2();

        $('form[name="user_information"]').on("change", null, null, function () {
            $(":submit").prop("disabled", false);
        }).on("input", null, null, function () {
            $(":submit").prop("disabled", false);
        });
    });
});
