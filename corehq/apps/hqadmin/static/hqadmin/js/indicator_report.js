hqDefine('hqadmin/js/indicator_report', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
        hqVisualizations = hqImport("hqadmin/js/visualizations").hqVisualizations;

    function parse_url_params() {
        var result = {}, queryString = location.search.slice(1),
            re = /([^&=]+)=([^&]*)/g,
            m = re.exec(queryString);


        while (m) {
            var param = decodeURIComponent(m[1]), val = decodeURIComponent(m[2]);
            if (result.hasOwnProperty(param)) {
                result[param].push.apply(result[param], [val]);
            } else {
                result[param] = [val];
            }
            m = re.exec(queryString);
        }

        return result;
    }
    var url_params = parse_url_params();

    $(function () {
        var indicatorData = initialPageData.get('indicator_data'),
            indicators = initialPageData.get('indicators'),
            visualizations = {};

        _.each(indicatorData, function (data, indicator) {
            if (indicators.indexOf(indicator) === -1) { return; }

            visualizations[indicator] = _.extend(
                {}, data, {
                    viz: hqVisualizations({
                        chart_name: data.chart_name,
                        histogram_type: data.histogram_type,
                        xaxis_label: data.xaxis_label,
                        ajax_url: data.ajax_url,
                        data: url_params,
                        interval: data.interval,
                        is_cumulative: data.is_cumulative,
                        get_request_params: data.get_request_params,
                    }).init(),
                }
            );
        });

        $("#all-charts-filter").on("submit", function () {
            var $this = $(this);
            var startdate = $this.find('[name="startdate"]').val();
            var enddate = $this.find('[name="enddate"]').val();
            var interval = $this.find('[name="interval"]').val();

            $('.startdate-input').val(startdate);
            $('.enddate-input').val(enddate);
            $('.interval-input').val(interval);

            $('.reload-graph-form').submit();

            return false;
        });
    });
});
