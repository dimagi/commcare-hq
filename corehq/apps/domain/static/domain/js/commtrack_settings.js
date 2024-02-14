hqDefine("domain/js/commtrack_settings", ['jquery'], function ($) {
    $(function () {
        $("#id_use_auto_consumption").change(function () {
            $("#id_consumption_min_transactions, " +
              "#id_consumption_min_window, " +
              "#id_consumption_optimal_window"
            ).prop('disabled', !$(this).prop('checked'));
        }).change();
    });
});
