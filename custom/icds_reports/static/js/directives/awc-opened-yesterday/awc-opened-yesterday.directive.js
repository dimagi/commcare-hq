var url = hqImport('hqwebapp/js/urllib.js').reverse;

angular.module('icdsApp').directive('awcOpenedYesterday', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'awc-opened-yesterday.directive'),
        bindToController: true,
        controller: function() {
            this.step = 'map';

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
