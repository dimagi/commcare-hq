hqDefine('accounting/js/subscriptions', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'accounting/js/widgets',
    'accounting/js/subscription_info_handler',
], function (
    $,
    initialPageData,
    widgets
) {
    $(function () {
        var AsyncSelect2Handler = widgets.AsyncSelect2Handler;
        var new_plan_version = new AsyncSelect2Handler('new_plan_version');
        new_plan_version.init();
        new_plan_version.getAdditionalData = function () {
            return {
                'edition': $('#id_new_plan_edition').val(),
                'current_version': initialPageData.get('current_version'),
            }
        };

        var deselectPlanVersion = function () {
            var $planVer = $('#id_new_plan_version');
            $planVer.val('');
            $planVer.select2('val', '');
        };
        $('#id_new_plan_edition').change(deselectPlanVersion);
    });
});
