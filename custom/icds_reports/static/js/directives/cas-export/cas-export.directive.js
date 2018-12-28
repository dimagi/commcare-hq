/* global moment */

function CasExportController($rootScope, $location, locationHierarchy, locationsService, userLocationId, haveAccessToFeatures,
                             downloadService) {
    var vm = this;

    $rootScope.report_link = '';

    locationsService.getRootLocations().then(function(data) {
        vm.locations = data.locations;
    });

    vm.filterOptions = [
        {label: 'Data not Entered for weight (Unweighed)', id: 'unweighed'},
        {label: 'Data not Entered for height (Unmeasured)', id: 'umeasured'},
        {label: 'Severely Underweight', id: 'severely_underweight'},
        {label: 'Moderately Underweight', id: 'moderately_underweight'},
        {label: 'Normal (weight-for-age)', id: 'normal_wfa'},
        {label: 'Severely Stunted', id: 'severely_stunted'},
        {label: 'Moderately Stunted', id: 'moderately_stunted'},
        {label: 'Normal (height-for-age)', id: 'normal_hfa'},
        {label: 'Severely Wasted', id: 'severely_wasted'},
        {label: 'Moderately Wasted', id: 'moderately_wasted'},
        {label: 'Normal (weight-for-height)', id: 'normal_wfh'},
    ];


    vm.userLocationId = userLocationId;

    var currentDay = moment().date(); //in  moment date() function returns number of day in month
    var startByMonth = 0;
    if (currentDay <= 15) {
        startByMonth = 1
    }

    var twoAgoMonth = moment().subtract(startByMonth + 2,'months');
    var prevMonth = moment().subtract(startByMonth + 1 ,'months');
    var currentMonth = moment().subtract(startByMonth ,'months');

    vm.months = [
        {id: currentMonth.month() + 1, name: currentMonth.format('MMMM YYYY')},
        {id: prevMonth.month() + 1, name: prevMonth.format('MMMM YYYY')},
        {id: twoAgoMonth.month() + 1, name: twoAgoMonth.format('MMMM YYYY')}
    ];

    vm.selectedLocation = userLocationId;
    vm.selectedMonth = currentMonth.month() + 1;
    vm.selectedIndicator = void(0);

    vm.indicators = [
        {id: 1, name: 'Child'},
        {id: 2, name: 'Pregnant and Lactating Women'},
        {id: 3, name: 'AWC'}
    ];

    vm.allFiltersSelected = function () {
        return vm.selectedLocation !== null && vm.selectedMonth !== null && vm.selectedIndicator !== null
    }

}

CasExportController.$inject = ['$rootScope', '$location', 'locationHierarchy', 'locationsService', 'userLocationId',
    'haveAccessToFeatures', 'downloadService'];

window.angular.module('icdsApp').directive("casExport", function() {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict:'E',
        scope: {
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'cas-export.directive'),
        controller: CasExportController,
        controllerAs: "$ctrl",
    };
});
