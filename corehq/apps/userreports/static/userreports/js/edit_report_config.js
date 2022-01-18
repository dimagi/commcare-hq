hqDefine('userreports/js/edit_report_config', [
    'jquery',
    'hqwebapp/js/multiselect_utils',
], function (
    $,
    multiselectUtils
) {
    $(function () {
        multiselectUtils.createFullMultiselectWidget('domain-selector', {
            selectableHeaderTitle: gettext("Linked projects"),
            selectedHeaderTitle: gettext("Projects to copy to"),
            searchItemTitle: gettext("Search projects"),
        });
    });
});
