hqDefine('hqadmin/js/domain_faceted_report', function () {
    var visualizations = {
        forms: {name: "forms", xaxis_label: "# form submissions", viz: null},
        cases: {name: "cases", xaxis_label: "# case creations", viz: null},
        users: {name: "users", xaxis_label: "# mobile workers created", viz: null},
        domains: {name: "domains", xaxis_label: "# domains created", viz: null },
    };

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

    $(function() {
        for (var key in visualizations) {
            if (visualizations.hasOwnProperty(key)) {
                visualizations[key].viz = new hqImport("hqadmin/js/visualizations").HQVisualizations({
                    chart_name: key,
                    histogram_type: key,
                    xaxis_label: visualizations[key].xaxis_label,
                    ajax_url: hqImport("hqwebapp/js/initial_page_data").reverse("admin_stats_data"),
                    data: url_params,
                    interval: hqImport("hqwebapp/js/initial_page_data").get("interval"),
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
