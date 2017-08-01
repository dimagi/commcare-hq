function KpiController($location) {

    this.goToStep = function(path) {
        var page_path = "#/" + path;
        if (Object.keys($location.search()).length > 0) {
            page_path += '?';
        }
        window.angular.forEach($location.search(), function(v, k) {
            page_path += (k + '=' + v + '&');
        });
        return page_path;
    };

}

KpiController.$inject = ['$location'];

window.angular.module('icdsApp').directive("kpi", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            data: '=',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'kpi.directive'),
        controller: KpiController,
        controllerAs: "$ctrl",
    };
});