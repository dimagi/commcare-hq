/* globals d3, nv */
hqDefine("reports/js/aggregate_user_status", function() {
    function aggregateTooltip(key, x, y, e, graph) {
        return '<p><strong>' + key + '</strong></p>' +
           '<p>' + Math.round(e.value) + '% since ' + x + '</p>';
    }
    function setupCharts(data, div, customTooltip) {
        nv.addGraph(function() {
            var chart = nv.models.multiBarChart()
                .transitionDuration(100)
                .showControls(false)
                .reduceXTicks(true)
                .rotateLabels(0)
                .groupSpacing(0.1)
            ;

            chart.yAxis.tickFormat(d3.format(',f'));

            // disable legend click
            chart.legend.updateState(false);

            if (customTooltip) {
                chart.tooltipContent(customTooltip);
            }
            d3.select('#' + div + ' svg')
                .datum([data])
                .call(chart);

            nv.utils.windowResize(chart.update);
            return chart;
        });
    }
    $(document).ajaxSuccess(function(event, xhr, settings) {
        if (settings.url.match(/reports\/async\/aggregate_user_status/)) {
            setupCharts($("#submission-percentages").data("value"), 'submission_chart', aggregateTooltip);
            setupCharts($("#sync-percentages").data("value"), 'sync_chart', aggregateTooltip);
            $('.chart-toggle').click(function () {
                $(this).parent().children().not(this).removeClass('btn-primary');  // deselect other buttons
                $(this).addClass('btn-primary');  // select self
                // update data
                var tooltipFunction = $(this).data('is-aggregate') ? aggregateTooltip : undefined;
                setupCharts($("#" + $(this).data('chart-data')).data("value"), $(this).data('chart-div'), tooltipFunction);
            });
            var mainJs = hqImport("hqwebapp/js/main");
            $('.hq-help-template').each(function () {
                mainJs.transformHelpTemplate($(this), true);
            });
        }
    });
});
