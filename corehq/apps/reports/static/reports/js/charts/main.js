hqDefine('reports/js/charts/main', function () {
    var init = function () {
        var pieCharts = hqImport('reports/js/charts/pie_chart');
        $('.charts-pie-chart').each(function (i, el) {
            var $el = $(el),
                data = $el.data();
            pieCharts.init(data);
        });

        var multibarCharts = hqImport('reports/js/charts/multibar_chart');
        $('.charts-multibar-chart').each(function (i, el) {
            var $el = $(el),
                data = $el.data();
            multibarCharts.init(data);
        });

    };

    return { init: init };
});
