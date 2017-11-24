
hqDefine("userreports/js/data_source_select", function() {
    $(function () {
        var dataSourceSelector = {
            application: ko.observable(""),
            sourceType: ko.observable(""),
            sourcesMap: hqImport("hqwebapp/js/initial_page_data").get("sources_map"),
            labelMap: {'case': gettext('Case'), 'form': gettext('Form')},
        };
        $("#report-builder-form").koApplyBindings(dataSourceSelector);
        $('#js-next-data-source').click(function () {
            hqImport('userreports/js/report_analytics').track.event('Data Source Next', hqImport('hqwebapp/js/main').capitalize(dataSourceSelector.sourceType()));
            hqImport('analytix/js/kissmetrics').track.event("RBv2 - Data Source");
        });
    });
});
