hqDefine('settings/js/edit_my_account', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function (
    $,
    initialPageData
) {
    $(function () {
        $('#id_language').select2();

        $('form[name="user_information"]').on("change", null, null, function () {
            $(":submit").prop("disabled", false);
        }).on("input", null, null, function () {
            $(":submit").prop("disabled", false);
        });

        $('#generate-api-key').click(function () {
            var apiDiv = $(this).parent().parent().parent().parent();
            $.post(initialPageData.reverse('new_api_key'), '', function (data) {
                apiDiv.find('.form-control-static').text(data);
            });
        });
    });
});
