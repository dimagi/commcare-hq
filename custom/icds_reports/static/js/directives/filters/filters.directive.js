window.angular.module('icdsApp').directive("filters", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            data: '=',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'filters'),
        controller: function() {},
        controllerAs: "$ctrl",
    };
});