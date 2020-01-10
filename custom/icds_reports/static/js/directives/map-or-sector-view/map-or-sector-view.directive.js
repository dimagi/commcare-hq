/* global d3 */

function MapOrSectorController($location, storageService, locationsService, navigationService, isMobile) {

    var vm = this;
    var leftMargin = isMobile ? 70 : 150;
    var truncateAmount = isMobile ? 70 : 100;  // used in cropping the x-axis labels

    var location_id = $location.search().location_id;

    if (['null', 'undefined', ''].indexOf(location_id) === -1) {
        locationsService.getLocation(location_id).then(function (location) {
            vm.showChart = location.location_type === 'district';
        });
    }

    function wrapXAxisLabels() {
        //This wrap te text on the xAxis label if text length is longer than 100
        //Found on stackoverflow: https://stackoverflow.com/questions/16701522/how-to-linebreak-an-svg-text-within-javascript/28553412#28553412
        //Replace svg text element to:
        //<text><tspan></tspan><tspan></tspan>...<text>
        d3.selectAll(".nv-x.nv-axis .tick text").each(function () {
            var text = d3.select(this),
                words = text.text().split(/\s+/).reverse(),
                word, line = [],
                lineNumber = 0,
                lineHeight = 1.1, // ems
                y = 2.5 * parseInt(words.length),
                dy = parseFloat(text.attr("dy")),
                tspan = text.text(null).append("tspan").attr("x", -5).attr("y", -y).attr("dy", dy + "em");

            word = words.pop();
            while (word) {
                line.push(word);
                tspan.text(line.join(" "));
                if (tspan.node().getComputedTextLength() > truncateAmount) {
                    line.pop();
                    tspan.text(line.join(" "));
                    line = [word];
                    tspan = text.append("tspan").attr("x", -5).attr("y", -y).attr("dy", ++lineNumber * lineHeight + dy + "em").text(word);
                }
                word = words.pop();
            }
        });
    }

    // reduce caption width to fit screen up to 900px on mobile view
    var captionWidth = (isMobile && window.innerWidth < 960) ? window.innerWidth - 60 : 900;

    function getChartTooltip(d) {
        if (!vm.data.mapData.tooltips_data || !vm.data.mapData.tooltips_data[d.value]) {
            return 'NA';
        }
        return vm.templatePopup({
            loc: {
                properties: {
                    name: d.value,
                },
            },
            row: vm.data.mapData.tooltips_data[d.value],
        });
    }
    vm.chartOptions = {

        chart: {
            type: 'multiBarHorizontalChart',
            margin: {
                bottom: 40,
                left: leftMargin,
            },
            x: function (d) {
                return d[0];
            },
            y: function (d) {
                return d[1];
            },
            showControls: false,
            showLegend: false,
            showValues: true,
            valueFormat: function (d) {
                if (vm.data.mapData.format === "number") {
                    return d;
                }
                return d3.format(".2%")(d);
            },
            xAxis: {
                showMaxMin: false,
            },
            yAxis: {
                tickFormat: function (d) {
                    if (vm.data.mapData.format === "number") {
                        return d3.format("d")(d);
                    }
                    var max = d3.max(vm.data.mapData.chart_data[0].values, function (value) {
                        return value[1];
                    });
                    return max < 0.1 ? d3.format(".2%")(d) : d3.format("%")(d);
                },
                axisLabelDistance: 20,
            },
            tooltip: {
                contentGenerator: getChartTooltip,
            },
            callback: function (chart) {
                var height = 1500;
                var calcHeight = vm.data.mapData ? vm.data.mapData.chart_data[0].values.length * 60 : 0;
                vm.chartOptions.chart.height = calcHeight !== 0 ? calcHeight : height;

                chart.multibar.dispatch.on('elementClick', function (e) {
                    locationsService.getLocationByNameAndParent(e.data[0], location_id).then(function (locations) {
                        var location = locations[0];
                        $location.search('location_name', location.name);
                        $location.search('location_id', location.location_id);
                        storageService.setKey('search', $location.search());
                        if (location.location_type_name === 'awc') {
                            $location.path(navigationService.getAWCTabFromPagePath($location.path()));
                        }
                    });
                });

                nv.utils.windowResize(function () {
                    wrapXAxisLabels();
                });
                wrapXAxisLabels();

                return chart;
            },
        },
        caption: {
            enable: true,
            html: function () {
                return '<i class="fa fa-info-circle"></i> ' + (vm.data.mapData !== void (0) ? vm.data.mapData.info : "");
            },
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': captionWidth + 'px',
            },
        },
        title: {
            enable: true,
            text: vm.label,
            css: {
                'text-align': 'right',
                'color': 'black',
            },
        },
    };
}

MapOrSectorController.$inject = [
    '$location', 'storageService', 'locationsService', 'navigationService', 'isMobile',
];

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').directive('mapOrSectorView',  ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        scope: {
            mode: '@',
            data: '=',
            templatePopup: '&',
            location: '=',
            label: '=',
        },
        templateUrl: function () {
            return templateProviderService.getTemplate('map-or-sector-view.directive');
        },
        bindToController: true,
        controller: MapOrSectorController,
        controllerAs: '$ctrl',
    };
}]);
