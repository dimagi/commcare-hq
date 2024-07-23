"use strict";
hqDefine('accounting/js/subscriptions_main', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'accounting/js/widgets',
    'accounting/js/base_subscriptions_main',
], function (
    $,
    initialPageData,
    widgets
) {
    $(function () {
        var asyncSelect2Handler = widgets.asyncSelect2Handler;
        var newPlanVersion = asyncSelect2Handler('new_plan_version');
        newPlanVersion.init();
        newPlanVersion.getAdditionalData = function () {
            return {
                'edition': $('#id_new_plan_edition').val(),
                'visibility': $('#id_new_plan_visibility').val(),
                'most_recent_version': $('#id_new_plan_most_recent_version').val(),
                'current_version': initialPageData.get('current_version'),
            };
        };

        var deselectPlanVersion = function () {
            var $planVer = $('#id_new_plan_version');
            $planVer.val('');
            $planVer.select2('val', '');
        };
        $('#id_new_plan_edition').change(deselectPlanVersion);
        $('#id_new_plan_visibility').change(deselectPlanVersion);
        $('#id_new_plan_most_recent_version').change(deselectPlanVersion);
    });
});
