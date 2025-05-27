import $ from "jquery";
import multibarCharts from "reports/js/charts/multibar_chart";
import pieCharts from "reports/js/charts/pie_chart";

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

export default { init: init };
