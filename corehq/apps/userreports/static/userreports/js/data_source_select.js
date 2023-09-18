hqDefine("userreports/js/data_source_select", function () {
    $(function () {
        let dataModel = hqImport("userreports/js/data_source_select_model");
        $("#report-builder-form").koApplyBindings(dataModel);
        $('#js-next-data-source').click(function () {
            hqImport('userreports/js/report_analytix').track.event('Data Source Next', hqImport('hqwebapp/js/bootstrap3/main').capitalize(dataModel.sourceType()));
            hqImport('analytix/js/kissmetrix').track.event("RBv2 - Data Source");
        });
    });
});
