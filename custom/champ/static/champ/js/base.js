hqDefine("champ/js/base", function() {
    $(function() {
        $('#reportFiltersAccordion').css('display', 'none');
    });

    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    $(document).on('ajaxSuccess', function(e, xhr, ajaxOptions) {
        var slug = initialPageData.get("slug"),
            jsOptions = initialPageData.get("js_options");
        if (jsOptions && ajaxOptions.url.indexOf(jsOptions.asyncUrl) === -1) {
            return;
        }

        $('#reportFiltersAccordion').css('display', 'none');
        if (slug === "prevision_vs_achievements_graph_report") {
            ko.applyBindings(new PrecisionVsAchievementsGraphModel(), $('#champApp').get(0));
        } else if (slug === "prevision_vs_achievements_table_report") {
            ko.applyBindings(new PrecisionVsAchievementsTableModel(), $('#champApp').get(0));
        } else if (slug === "service_uptake_report") {
            ko.applyBindings(new ServiceUptakeModel(), $('#champApp').get(0));
        }
    });
});
