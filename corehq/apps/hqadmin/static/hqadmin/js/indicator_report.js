hqDefine('hqadmin/js/indicator_report', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
        HQVisualizations = hqImport("hqadmin/js/visualizations").HQVisualizations;

    function parse_url_params() {
        var result = {}, queryString = location.search.slice(1),
            re = /([^&=]+)=([^&]*)/g, m;

        while (m = re.exec(queryString)) {
            var param = decodeURIComponent(m[1]), val = decodeURIComponent(m[2]);
            if (result.hasOwnProperty(param)) {
                result[param].push.apply(result[param], [val]);
            } else {
                result[param] = [val];
            }
        }

        return result;
    }
    var url_params = parse_url_params();

    $(function () {
        var indicatorData = initialPageData.get('indicator_data'),
            indicators = initialPageData.get('indicators'),
            visualizations = {};

        _.each(indicatorData, function(indicator, data) {
            if (indicators.indexOf(indicator) !== -1) {
                visualizations[indicator] = _.extend({}, data, {viz: null});
            }
        });


        for (var key in visualizations) {
            if (visualizations.hasOwnProperty(key)) {
                visualizations[key].viz = new HQVisualizations({
                    chart_name: visualizations[key].chart_name,
                    histogram_type: visualizations[key].histogram_type,
                    xaxis_label: visualizations[key].xaxis_label,
                    ajax_url: visualizations[key].ajax_url,
                    data: url_params,
                    interval: visualizations[key].interval,
                    is_cumulative: visualizations[key].is_cumulative,
                    get_request_params: visualizations[key].get_request_params
                });
                visualizations[key].viz.init();
            }
        }

        $("#all-charts-filter").on("submit", function() {
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
