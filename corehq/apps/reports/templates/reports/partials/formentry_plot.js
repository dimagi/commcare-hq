    $(function () {
        var avgs = {{ avgs_data|safe }};
        var tots = {{ totals_data|safe }};
        var extras = {{ chart_extras|safe }};
        $.plot($("#formentry-plot"), [{data: avgs, label: "average time per form"}, 
                                   {data: tots, label: "total forms filled", yaxis: 2}], 
                  { xaxis: {mode: "time",
                            minTickSize: [1, "day"]}, 
                    yaxis: {min: 0, tickFormatter: function (v, axis) { return v + " sec" }},
                    y2axis: {min: 0, tickFormatter: function (v, axis) { return v +" forms" }},
                    legend: { position: "nw"}, 
                    grid: { hoverable: true }, 
                    series: { lines: { show: true },
                              points: { show: true }}
                   });

        function tooltipContents(x, y) {
            dict = extras[x];
            var m_names = new Array("Jan", "Feb", "Mar", 
                                    "Apr", "May", "Jun", "Jul", "Aug", "Sep", 
                                    "Oct", "Nov", "Dec");
            d = new Date();
            d.setTime(x);
            return d.getDate() + " " + m_names[d.getMonth()] + " " + d.getFullYear() + " - total forms: " + dict["count"] + ", average time: " + y + " seconds";
            
        }
        function showTooltip(x, y, contents) {
          
            $('<div id="tooltip">' + contents + '</div>').css( {
                position: 'absolute',
                display: 'none',
                top: y + 5,
                left: x + 5,
                border: '1px solid #fdd',
                padding: '2px',
                'background-color': '#fee',
                opacity: 0.80
            }).appendTo("body").fadeIn(200);
        }
        
        var previousPoint = null;
        $("#formentry-plot").bind("plothover", function (event, pos, item) {
            $("#x").text(pos.x.toFixed(2));
            $("#y").text(pos.y.toFixed(2));
            if (item) {
                if (previousPoint != item.datapoint) {
                    previousPoint = item.datapoint;
                    
                    $("#tooltip").remove();
                    var x = item.datapoint[0].toFixed(2),
                        y = item.datapoint[1].toFixed(2);
                    showTooltip(item.pageX, item.pageY,
                                // tooltipContents(x, y));
                                tooltipContents(item.datapoint[0], y));
                }
            }
            else {
                $("#tooltip").remove();
                previousPoint = null;            
            }
        });
    });