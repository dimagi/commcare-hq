window.angular.module('icdsApp').directive("locationFilter", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            location: '=',
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'location_filter'),
        controller: function LocationFilterControler() {
            this.locations = [
                {name: 'Location 1'},
                {name: 'Location 2'},
                {name: 'Location 3'},
                {name: 'Location 4'},
                {name: 'Location 5'},
            ];
        },
        controllerAs: "$locationCtrl",
    };
});