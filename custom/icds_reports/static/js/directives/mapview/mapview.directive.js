function MapviewController($scope) {
    $scope.openFilters = function () {
        $scope.$broadcast('openFilterMenu');
    };
    
    var vm = this;
    
    vm.renderMap = function() {
       
        var map = L.map('map').setView([25, 80], 6);

                    L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw', {
                        maxZoom: 18,
                        attribution: 'Sample Map ',
                        id: 'mapbox.light'
                    }).addTo(map);

                    // control that shows state info on hover
                    var info = L.control();
                    info.onAdd = function(map) {
                        this._div = L.DomUtil.create('div', 'info');
                        this.update();
                        return this._div;
                    };
                    info.update = function(props) {
                        this._div.innerHTML = '<h4>Map Details</h4>' + (props ?
                            '<b>' + props.name + '</b><br />' + props.density + ' people / mi<sup>2</sup>' :
                            'Click on a Region');
                    };

                    info.addTo(map);

                    // get color depending on population density value
                    function getColor(d) {
                        return d > 1000 ? '#800026' :
                            d > 500 ? '#BD0026' :
                            d > 200 ? '#E31A1C' :
                            d > 100 ? '#FC4E2A' :
                            d > 50 ? '#FD8D3C' :
                            d > 20 ? '#FEB24C' :
                            d > 10 ? '#FED976' :
                            '#FFEDA0';
                    }

                    function style(feature) {
                        return {
                            weight: 2,
                            opacity: 1,
                            color: 'white',
                            dashArray: '3',
                            fillOpacity: 0.7,
                            fillColor: getColor(feature.properties.density)
                        };
                    }
                    var cnt = 0;
                    var flagArray = Array();
                    var flag = 0;
                    var geojson;

                    function highlightFeature(e) {
                        var layer = e.target;
                        cnt++;
                        layer.setStyle({
                            weight: 5,
                            color: '#666',
                            dashArray: '',
                            fillOpacity: 0.7
                        });

                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                            layer.bringToFront();
                        }

                        info.update(layer.feature.properties);


                        if (flag == 1) {
                            map.fitBounds(e.target.getBounds());
                            flag = 0;
                        }


                        if (in_array(layer.feature.properties.uid, flagArray, 0)) {
                            switch (layer.feature.properties.uid) {
                                case 'u01':
                                    location.href = "./#/demographics?page=1";
                                    break;
                                case 'u02':
                                    location.href = "./#/demographics?page=2";
                                    break;
                            }
                        } else {
                            flagArray.push(layer.feature.properties.uid);
                        }

                        /*
                        if (cnt % 2 == 0) {
                            switch (layer.feature.properties.uid) {
                                case 'u01':
                                    location.href = "./#!/page1";
                                    break;
                                case 'u02':
                                    location.href = "./#!/page2";
                                    break;
                            }

                            geojson.resetStyle(e.target);
                            info.update();
                        }
                        */
                    }

                    function in_array(needle, haystack, argStrict) {
                        //  discuss at: https://locutus.io/php/in_array/
                        // original by: Kevin van Zonneveld (https://kvz.io)
                        // improved by: vlado houba
                        // improved by: Jonas Sciangula Street (Joni2Back)
                        //    input by: Billy
                        // bugfixed by: Brett Zamir (https://brett-zamir.me)
                        //   example 1: in_array('van', ['Kevin', 'van', 'Zonneveld'])
                        //   returns 1: true
                        //   example 2: in_array('vlado', {0: 'Kevin', vlado: 'van', 1: 'Zonneveld'})
                        //   returns 2: false
                        //   example 3: in_array(1, ['1', '2', '3'])
                        //   example 3: in_array(1, ['1', '2', '3'], false)
                        //   returns 3: true
                        //   returns 3: true
                        //   example 4: in_array(1, ['1', '2', '3'], true)
                        //   returns 4: false

                        var key = ''
                        var strict = !!argStrict

                        // we prevent the double check (strict && arr[key] === ndl) || (!strict && arr[key] === ndl)
                        // in just one for, in order to improve the performance
                        // deciding wich type of comparation will do before walk array
                        if (strict) {
                            for (key in haystack) {
                                if (haystack[key] === needle) {
                                    return true
                                }
                            }
                        } else {
                            for (key in haystack) {
                                if (haystack[key] == needle) { // eslint-disable-line eqeqeq
                                    return true
                                }
                            }
                        }
                        return false
                    }

                    function resetHighlight(e) {
                        geojson.resetStyle(e.target);
                        info.update();
                    }


                    function zoomToFeature(e) {
                        map.fitBounds(e.target.getBounds());
                    }

                    function onEachFeature(feature, layer) {
                        layer.on({
                            //mouseover: highlightFeature,
                            click: highlightFeature,
                            dblclick: resetHighlight,
                            //click: zoomToFeature
                        });
                    }

                    geojson = L.geoJson(statesData, {
                        style: style,
                        onEachFeature: onEachFeature
                    }).addTo(map);

                    map.attributionControl.addAttribution('Population data &copy; <a href="http://census.gov/">US Census Bureau</a>');


                    var legend = L.control({ position: 'bottomright' });

                    legend.onAdd = function(map) {

                        var div = L.DomUtil.create('div', 'info legend'),
                            grades = [0, 10, 20, 50, 100, 200, 500, 1000],
                            labels = [],
                            from, to;

                        for (var i = 0; i < grades.length; i++) {
                            from = grades[i];
                            to = grades[i + 1];

                            labels.push(
                                '<i style="background:' + getColor(from + 1) + '"></i> ' +
                                from + (to ? '&ndash;' + to : '+'));
                        }

                        div.innerHTML = labels.join('<br>');
                        return div;
                    };

                    legend.addTo(map);
                    return;

       	
       	
       	
    };
    
    vm.renderMap();

}

MapviewController.$inject = ['$scope'];

window.angular.module('icdsApp').directive("mapview",  ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        bindToController: true,
        templateUrl: function () {
            return templateProviderService.getTemplate('mapview.directive');
        },
        controller: MapviewController,
    };
}]);