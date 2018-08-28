/* global d3, insertLinebreaks, loadCharts */
// depends on hqadmin/js/nvd3_charts_helper.js for loadCharts and insertLinebreaks
hqDefine("hqadmin/js/visualizations", function() {
    // adapted from http://stackoverflow.com/questions/901115/
    var getUrlParams = function(a) {
        // takes a string of the form "foo=bar&bat=&fizz=bang"
        // and returns {"foo": "bar", "bat": "", "fizz": "bang"}
        if (!a) {
            return {};
        }
        a = a.split('&');
        var b = {};
        for (var i = 0; i < a.length; ++i)
        {
            var p=a[i].split('=');
            if (p.length !== 2) continue;
            b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
        }
        return b;
    };

    var hqVisualizations = function (options) {
        var self = {};
        self.chartName = options.chart_name;
        self.xaxisLabel = options.xaxis_label;
        self.histogramType = options.histogram_type;
        self.ajaxUrl = options.ajax_url;
        self.data = options.data || {};
        self.shouldUpdateUrl = options.should_update_url === undefined ? false : options.should_update_url;
        self.interval = options.interval || "day";
        self.datefield = options.datefield;
        self.isCumulative = options.is_cumulative || null;
        self.getRequestParams = options.get_request_params || {};

        self.charts = { "bar-chart": null, "cumulative-chart": null, "stacked-cumulative-chart": null };
        self.chartsId = '#' + self.chartName + '-charts';
        self.chartTabsId = '#' + self.chartName + '-chart-tabs';

        function updateActiveChart() {
            // for some reason nvd3 doesn't fully animate the charts, force this update after the chart is loaded
            var activeChartName = $(self.chartTabsId + ' li.active a').attr('href').substr(1); // remove '#'
            _updateChartIfExists(self.charts[activeChartName]);
        }

        function _updateChartIfExists(chart) {
            if (chart) {
                chart.update();
            }
        }

        self.init = function() {
            $(function() {
                // load new chart when daterange is clicked
                $(self.chartTabsId).on('submit', '.reload-graph-form', function() {
                    var $this = $(this);
                    var startdate = $this.find('[name="startdate"]').val();
                    var enddate = $this.find('[name="enddate"]').val();
                    var interval = $this.find('[name="interval"]').val();
                    var datefield = $this.find('[name="datefield"]').val();

                    if (interval) {
                        self.interval = interval;
                    }

                    if (datefield) {
                        self.datefield = datefield;
                    }

                    self.loadChartData(updateActiveChart, startdate, enddate);

                    if (self.shouldUpdateUrl) {
                        var params = getUrlParams($(location).attr('search').substr(1));
                        params['datefield'] = datefield || "";
                        params['interval'] = interval;
                        params['startdate'] = startdate;
                        params['enddate'] = enddate;

                        var newUrl = '?' + $.param(params) + window.location.hash;
                        history.pushState(null, "Reloaded Chart", newUrl);

                        // keep the urls for the other data visualizations consistent with this datespan
                        $(".viz-url").each(function() {
                            var newHref = $(this).attr('href').split("?")[0] + newUrl;
                            $(this).attr('href', newHref);
                        });
                    }

                    return false;
                });
                $(self.chartTabsId + ' .reload-graph-form').submit();

                // load chart if not already visible on the screen
                $(self.chartTabsId).on('click', 'a[data-toggle="hash-tab"]', function(){
                    $('.nvd3-chart').hide();
                    var $chart = $($(this).attr('href')).children('.nvd3-chart');
                    $chart.show().removeClass('hidden');
                    $(window).trigger('resize');
                    var chart = self.charts[$chart.parents('.tab-pane').attr('id')];
                    _updateChartIfExists(chart); // for some reason nvd3 doesn't fully animate the charts, force this update
                });
            });
            return self;
        };

        self.loadChartData = function(callbackFn, startdate, enddate) {
            var $loading = $(self.chartsId + ' .loading');
            var $error = $(self.chartsId + ' .error');
            var $charts = $(self.chartsId + ' .nvd3-chart');
            var data = {};

            $(self.chartsId + " .no-data").hide();
            $error.hide();
            $loading.show().removeClass('hidden');
            $(window).trigger('resize');  // redraw graph

            var svgWidth = $(self.chartsId + " .tab-pane.active").width();
            $charts.each(function(){
                // hack: need to explicitly set the width to a pixel value because nvd3 has issues when it's set to 100%
                var $svgEle = $("<svg style='height:320px;'> </svg>").width(svgWidth);
                $(this).hide().html('').append($svgEle); // create a new svg element to stop update issues
            });

            data["histogram_type"] = self.histogramType;
            data["interval"] = self.interval;

            if (self.datefield) {
                data["datefield"] = self.datefield;
            }

            if (enddate) {
                data["enddate"] = enddate;
            }
            if (startdate) {
                data["startdate"] = startdate;
            }

            if (!$.isEmptyObject(self.getRequestParams)) {
                data['get_request_params'] = self.getRequestParams;
            }

            if (self.isCumulative !== null) {
                data['is_cumulative'] = self.isCumulative;
            }

            _.extend(self.data, data);

            $.getJSON(self.ajaxUrl, self.data,
                function(d) {
                    var startdate = new Date(Date.UTC(d.startdate[0], d.startdate[1]-1, d.startdate[2]));
                    var enddate = new Date(Date.UTC(d.enddate[0], d.enddate[1]-1, d.enddate[2]));
                    self.charts = loadCharts(self.chartName, self.xaxisLabel, d.histo_data, d.initial_values,
                        startdate.getTime(), enddate.getTime(), self.interval);
                    $loading.hide();
                    $charts.show().removeClass('hidden');
                    $(window).trigger('resize');  // redraw graph

                    _.each(self.charts, function(chart, name) {
                        if (chart === null) {
                            $("#" + self.chartName + "-" + name + " svg").hide();
                            $("#" + self.chartName + "-" + name + " .no-data").show().removeClass('hidden');
                            $(window).trigger('resize');  // redraw graph
                        }
                    });

                    // set the date fields if they're not already set
                    var $startdateField = $("#" + self.chartName + "-startdate");
                    var $enddateField = $("#" + self.chartName + "-enddate");
                    var $intervalField = $("#" + self.chartName + "-interval");
                    if (!$startdateField.val()) {
                        $startdateField.val(startdate.toISOString().substr(0, 10)); // substr bc date strs are 10 chars
                    }
                    if (!$enddateField.val()) {
                        $enddateField.val(enddate.toISOString().substr(0, 10));
                    }
                    if (!$intervalField.val()) {
                        $intervalField.val(self.interval);
                    }

                    d3.selectAll(self.chartsId + ' g.nv-x.nv-axis g text').each(insertLinebreaks);

                    if (callbackFn) {
                        callbackFn();
                    }
                }
            ).fail(function() {
                $loading.hide();
                $error.show().removeClass('hidden');
            });
        };

        return self;
    };

    return {
        hqVisualizations: hqVisualizations,
    };
});
