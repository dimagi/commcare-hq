    $(function () {
        var datasets = {{ plot_data|safe }};
        
        // hard-code color indices to prevent them from shifting as
        // countries are turned on/off
        var i = 0;
        $.each(datasets, function(key, val) {
            val.totals.color = i;
            val.averages.color = i;
            ++i;
        });
        // insert checkboxes 
	    var choiceContainer = $("#choices");
	    $.each(datasets, function(key, val) {
	        choiceContainer.append('<br/><input type="checkbox" name="' + key +
	                               '" checked="checked" id="id' + key + '">' +
	                               '<label for="id' + key + '">'
	                                + key + '</label>');
	    });
	    choiceContainer.find("input").click(plotAccordingToChoices);
	 
        function plotAccordingToChoices() {
	        var data = [];
	 
	        choiceContainer.find("input:checked").each(function () {
	            var key = $(this).attr("name");
	            if (key && datasets[key])
	                data.push(datasets[key].totals);
	                data.push(datasets[key].averages);
	        });
	        
	        if (data.length > 0)
	            $.plot($("#formentry-plot"), data, 
                      { xaxis: {mode: "time",
                                minTickSize: [1, "day"]}, 
                    yaxis: {min: 0, tickFormatter: function (v, axis) { return v + " sec" }},
                    y2axis: {min: 0, tickFormatter: function (v, axis) { return v +" forms" }},
                    legend: { show: true, container: "#trendlegend"}, 
                    grid: { hoverable: true }, 
                   });

        }
        function tooltipContents(item) {
            return item.series.label;
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
                                tooltipContents(item));
                }
            }
            else {
                $("#tooltip").remove();
                previousPoint = null;            
            }
        });
        plotAccordingToChoices();
    });