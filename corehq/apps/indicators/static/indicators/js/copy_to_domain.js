hqDefine("indicators/js/copy_to_domain", function() {
    $(function () {
        hqImport('hqwebapp/js/multiselect_utils').createFullMultiselectWidget(
            'id_indicator_ids',
            gettext("Available Indicators"),
            gettext("Indicators to Copy"),
            gettext("Search Indicators...")
        );
    });
});
