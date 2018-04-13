hqDefine('reports/js/charts/main', function() {
    var init = function () {
        var pieCharts = hqImport('reports/js/charts/pie_chart');
        $('.charts-pie-chart').each(function(i, el) {
            pieCharts.init(el);
        });

        var multibarCharts = hqImport('reports/js/charts/multibar_chart');
        $('.charts-multibar-chart').each(function (i, el) {
            multibarCharts.init(el);
        });

    };

    return { init: init };
});
