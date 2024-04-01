hqDefine("reports/js/aggregate_user_status", function () {
    function aggregateTooltip(key, x, y, e) {
        return '<p><strong>' + key + '</strong></p>' +
           '<p>' + Math.round(e.value) + '% since ' + x + '</p>';
    }
    function addHorizontalScrollBar(div, width){
            $('#'+ div).css({
                    'overflow-x': 'scroll'
            });
            $('#'+ div + ' svg').css({
                'width': width + 'px'
            });
    }
    function setupCharts(data, div, customTooltip) {
        nv.addGraph(function () {
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

            // Add scrollbar for large datasets.
            // Multiplication factor for chart width is chosen so that chart is readable
            dataLength = data['values'].length
            if (dataLength > 120) {
                chartWidth = dataLength * 15;
                addHorizontalScrollBar(div, chartWidth);
                $('#'+ div).scrollLeft(0)
            }

            d3.select('#' + div + ' svg')
                .datum([data])
                .call(chart);

            nv.utils.windowResize(chart.update);
            return chart;
        });
    }
    $(document).ajaxSuccess(function (event, xhr, settings) {
        if (settings.url.match(/reports\/async\/aggregate_user_status/)) {
            setupCharts($("#submission-percentages").data("value"), 'submission_chart', aggregateTooltip);
            setupCharts($("#sync-percentages").data("value"), 'sync_chart', aggregateTooltip);
            $('.chart-toggle').click(function () {
                $(this).parent().children().not(this).removeClass('active');  // deselect other buttons
                $(this).addClass('active');  // select self
                // update data
                var tooltipFunction = $(this).data('is-aggregate') ? aggregateTooltip : undefined;
                setupCharts($("#" + $(this).data('chart-data')).data("value"), $(this).data('chart-div'), tooltipFunction);
            });
            var mainJs = hqImport("hqwebapp/js/bootstrap3/main");
            $('.hq-help-template').each(function () {
                mainJs.transformHelpTemplate($(this), true);
            });
        }
    });
});
