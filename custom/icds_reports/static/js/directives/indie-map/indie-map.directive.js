/* global d3 */

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {},
        template: '<div class="indie-map-directive"><datamap map="$ctrl.map"></datamap></div>',
        bindToController: true,
        controller: function() {
            this.map = {
                scope: 'ind',
                responsive: true,
                setProjection: function(element) {
                    var projection = d3.geo.mercator()
                        .center([80, 25])
                        .scale(1200)
                        .translate([element.offsetWidth / 2, element.offsetHeight / 4]);
                    var path = d3.geo.path()
                        .projection(projection);

                    return {path: path, projection: projection};
                },
            };
        },
        controllerAs: '$ctrl',
    };
});
