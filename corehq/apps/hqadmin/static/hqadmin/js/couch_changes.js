hqDefine('hqadmin/js/couch_changes', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'd3/d3.min',
    'nvd3/nv.d3.min',
], function (
    $,
    initialPageData,
    d3,
    nv
) {
    $(function () {
        var domain_data = initialPageData.get('domain_data'),
            doc_type_data = initialPageData.get('doc_type_data');
        var addGraph = function (data, divId) {
            nv.addGraph(function () {
                var chart = nv.models.discreteBarChart()
                    .x(function (d) { return d.label; })
                    .y(function (d) { return d.value; })
                    .staggerLabels(true)    //Too many bars and not enough room? Try staggering labels.
                    .tooltips(false)        //Don't show tooltips
                    .showValues(true)       //...instead, show the bar value right on top of each bar.
                ;
                d3.select('#' + divId + ' svg')
                    .datum(data)
                    .call(chart);
                nv.utils.windowResize(chart.update);
                return chart;
            });
        };
        addGraph([domain_data], 'domain-info');
        addGraph([doc_type_data], 'doc-type-info');
    });
});
