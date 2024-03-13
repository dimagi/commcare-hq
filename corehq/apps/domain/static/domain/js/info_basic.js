hqDefine("domain/js/info_basic", [
    'jquery',
    'hqwebapp/js/select_2_ajax_widget', // for call center case owner
    'select2/dist/js/select2.full.min',
    'hqwebapp/js/bootstrap3/widgets',
], function (
    $
) {
    $(function () {
        $('#id_default_timezone').select2({
            placeholder: gettext('Select a Timezone...'),
        });

        $('#id_call_center_enabled').change(function () {
            var type = $('#id_call_center_type').closest('.control-group');
            var caseOwner = $('#id_call_center_case_owner').closest(
                '.control-group'
            );
            var caseType = $('#id_call_center_case_type').closest(
                '.control-group'
            );
            if ($(this).is(':checked')) {
                type.removeClass('hide');
                caseOwner.removeClass('hide');
                caseType.removeClass('hide');
            } else {
                type.addClass('hide');
                caseOwner.addClass('hide');
                caseType.addClass('hide');
            }
        });
        $('#id_call_center_enabled').trigger('change');
    });
});
