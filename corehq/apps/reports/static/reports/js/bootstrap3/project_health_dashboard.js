/* globals moment */
hqDefine("reports/js/bootstrap3/project_health_dashboard", function () {
    // "Performing / Active User Trends" Chart
    function setupCharts(data) {
        var highPerformingSeries = {
            'key': 'high performing',
            values: _.map(data, function (item) {
                return {
                    x: moment(item.month).format("MMM YYYY"),
                    y: item.performing,
                    z: item.delta_high_performers,
                };
            }),
        };
        var lowPerformingSeries = {
            'key': 'low performing',
            values: _.map(data, function (item) {
                return {
                    x: moment(item.month).format("MMM YYYY"),
                    y: item.active - item.performing,
                    z: item.delta_low_performers,
                };
            }),
        };
        function chevronIcon(value) {
            var chevronUp = '<span class="fa fa-chevron-up" style="color: #006400;"></span> ';
            var chevronDown = '<span class="fa fa-chevron-down" style="color: #8b0000;"></span> ';
            if (value > 0) {
                return chevronUp;
            } else if (value < 0) {
                return chevronDown;
            } else {
                return '';
            }
        }
        nv.addGraph(function () {
            var chart = nv.models.multiBarChart()
                .showControls(false)
                .stacked(true)
            ;

            chart.yAxis.tickFormat(d3.format(',.0f'));
            chart.color(["#004ebc", "#e73c27"]);
            chart.tooltipContent(function (key, x, y, e) {
                var d = e.series.values[e.pointIndex];
                var chevron = chevronIcon(d.z);
                return '<h3>' + key + '</h3>' + '<p>' +  y + ' in ' + x + '</p>' +
                       '<p>' + chevron + d.z + ' from last month' + '</p>';
            });
            d3.select('#perform_chart svg')
                .datum([highPerformingSeries, lowPerformingSeries])
                .call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        });
    }

    function setupLineChart(data) {
        var proportionActiveSeries = [{
            key: 'active users (%)',
            values: _.map(data, function (item) {
                return {
                    x: moment(item.month),
                    y: item.percent_active,
                    z: item.inactive,
                    u: item.total_users_by_month,
                    a: item.active,
                };
            }),
        }];
        nv.addGraph(function () {
            var chart = nv.models.lineChart()
                .margin({right: 50})
                .showYAxis(true)
                .showXAxis(true);

            chart.yAxis.tickFormat(d3.format(".0%"));
            chart.xScale(d3.time.scale());
            chart.xAxis.showMaxMin(false)
                .ticks(6)
                .tickFormat(function (d) {
                    return moment(d).format("MMM YYYY");
                });
            chart.tooltipContent(function (key, x, y, e) {
                var d = e.series.values[e.pointIndex];
                return '<h3>' + key + '</h3>' +
                       '<p>' +  y + ' in ' + x + '</p>' +
                       '<p>' + 'number of active users: ' + d.a +
                       '</p>' +
                       '<p>' + 'number of inactive users: ' + d.z +
                       '</p>' +
                       '<p>' + 'number of total users: ' + d.u +
                       '</p>';
            });
            d3.select('#active_linechart svg')
                .datum(proportionActiveSeries)
                .call(chart);

            nv.utils.windowResize(function () {
                chart.update();
            });

            return chart;

        });
    }

    // User Information PopOver, when clicked on username
    function setupPopovers() {
        // ajax popover: http://stackoverflow.com/a/14560039/8207
        $('a.user-popover').popover({
            "html": true,
            "content": function () {
                var divId =  "tmp-id-" + $.now();
                return detailsInPopup($(this).data('url'), divId);
            },
            "sanitize": false,
        });

        function detailsInPopup(link, divId) {
            $.ajax({
                url: link,
                success: function (response) {
                    $('#' + divId).html(response);
                },
                error: function () {
                    $('#' + divId).html(gettext("Sorry, we couldn't load that."));
                },
            });
            return $('<div />').attr('id', divId).text(gettext('Loading...'))[0].outerHTML;
        }
    }

    function setupDataTables() {
        $('.datatable').DataTable({
            "ordering": false,
            "searching": false,
            "lengthChange": false,
            "oLanguage": {
                'sEmptyTable': gettext('No data available in table'),
                'sInfo': gettext('Showing _START_ to _END_ of _TOTAL_ entries'),
                'sInfoEmpty': gettext('Showing _START_ to _END_ of _TOTAL_ entries'),
            },
        });
    }

    $(document).ajaxSuccess(function (event, xhr, settings) {
        if (settings.url.match(/reports\/async\/project_health/)) {
            var sixMonthsReports = $("#six-months-reports").data("value");
            setupCharts(sixMonthsReports);
            setupPopovers();
            setupLineChart(sixMonthsReports);
            setupDataTables();
        }
    });
});
