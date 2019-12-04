var url = hqImport('hqwebapp/js/initial_page_data').reverse;


function KpiController($rootScope, $location, haveAccessToFeatures) {
    this.haveAccessToFeatures = haveAccessToFeatures;
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

    this.showPercentInfo = function () {
        var selected_month = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selected_year =  parseInt($location.search()['year']) || new Date().getFullYear();
        var current_month = new Date().getMonth() + 1;
        var current_year = new Date().getFullYear();

        return selected_month !== current_month || selected_year !== current_year;
    };

    this.isNumber = window.angular.isNumber;

    // used by mobile dashboard only
    this.showHelp = function (heading, help) {
        $rootScope.$broadcast('showHelp', heading, help);
    };
}

KpiController.$inject = ['$rootScope', '$location', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive("kpi",  ['templateProviderService', function (templateProviderService) {
    return {
        restrict:'E',
        scope: {
            data: '=',
        },
        bindToController: true,
        templateUrl: function () {
            return templateProviderService.getTemplate('kpi.directive');
        },
        controller: KpiController,
        controllerAs: "$ctrl",
    };
}]);
