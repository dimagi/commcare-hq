hqDefine("domain/js/info_basic", [
    'jquery',
    'underscore',
    'hqwebapp/js/select_2_ajax_widget', // for call center case owner
    'select2/dist/js/select2.full.min',
], function (
    $,
    _
) {
    $(function () {
        $('#id_default_timezone').select2({
            placeholder: gettext('Select a Timezone...'),
        });

        $('#id_call_center_enabled').change(function () {
            var type = $('#id_call_center_type').closest('.control-group');
            var case_owner = $('#id_call_center_case_owner').closest('.control-group');
            var case_type = $('#id_call_center_case_type').closest('.control-group');
            if ($(this).is(':checked')) {
                type.removeClass('hide');
                case_owner.removeClass('hide');
                case_type.removeClass('hide');
            } else {
                type.addClass('hide');
                case_owner.addClass('hide');
                case_type.addClass('hide');
            }
        });
        $('#id_call_center_enabled').trigger('change');
    });
});
