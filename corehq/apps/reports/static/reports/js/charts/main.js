hqDefine('reports/js/charts/main', [
    'jquery',
    'reports/js/charts/multibar_chart',
    'reports/js/charts/pie_chart',
], function (
    $,
    multibarCharts,
    pieCharts,
) {
    var init = function () {
        $('.charts-pie-chart').each(function (i, el) {
            var $el = $(el),
                data = $el.data();
            pieCharts.init(data);
        });

        $('.charts-multibar-chart').each(function (i, el) {
            var $el = $(el),
                data = $el.data();
            multibarCharts.init(data);
        });
    };

    return { init: init };
});
