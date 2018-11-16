hqDefine("indicators/js/copy_to_domain", [
    'jquery',
    'hqwebapp/js/multiselect_utils',
], function (
    $,
    multiselectUtils
) {
    $(function () {
        multiselectUtils.createFullMultiselectWidget(
            'id_indicator_ids',
            gettext("Available Indicators"),
            gettext("Indicators to Copy"),
            gettext("Search Indicators...")
        );
    });
});
