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
        var slugToModule = {
            "prevision_vs_achievements_graph_report": "champ/js/knockout/prevision_vs_achievement_graph",
            "prevision_vs_achievements_table_report": "champ/js/knockout/prevision_vs_achievement_table",
            "service_uptake_report": "champ/js/knockout/service_uptake",
        };
        if (slugToModule[slug]) {
            $('#champApp').koApplyBindings(hqImport(slugToModule[slug]).model());
        }
    });
});
