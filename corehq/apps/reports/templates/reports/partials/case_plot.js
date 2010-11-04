	$(function () {
	    var case_data = {{ daily_case_data|safe }};
	    var totals = {{ total_case_data|safe }};
	    $.plot($("#case-plot"), [{data: totals, label: "total cases received"},
	                               {data: case_data, label: "daily cases sent to phone", yaxis: 2, lines: {show: false}, bars: { show: true }} 
	                               ], 
	              { xaxis: {mode: "time",
	                        minTickSize: [1, "day"]}, 
	                yaxis: {min: 0, tickFormatter: function (v, axis) { return v + " cases" }, minTickSize: 1},
	                y2axis: {min: 0, tickFormatter: function (v, axis) { return v +" cases/day" }, minTickSize: 1},
	                legend: { position: "nw" }, 
	                grid: { hoverable: true }, 
	                series: { lines: { show: true },
	                          points: { show: true }}
	               });
	});
