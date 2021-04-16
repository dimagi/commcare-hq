hqDefine('userreports/js/edit_report_config', [
    'jquery',
    'hqwebapp/js/multiselect_utils',
], function (
    $,
    multiselectUtils
) {
    $(function () {
        multiselectUtils.createFullMultiselectWidget(
            'domain-selector',
            gettext("Linked projects"),
            gettext("Projects to copy to"),
            gettext("Search projects")
        );
    });
});
