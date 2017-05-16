/* global d3 */

var url = hqImport('hqwebapp/js/urllib.js').reverse;


function UnderweightChildrenReportController($routeParams, maternalChildService) {
    var vm = this;
    vm.step = $routeParams.step;
    vm.steps = [
        {route: '/underweight_children/1', label: 'MapView'},
        {route: '/underweight_children/2', label: 'ChartView'},
    ];

    vm.mapData = {};
    vm.mapPlugins = {
        customTable: function() {
            var html = [
                '<table style="width: 250px;">',
                '<td style="border-right: 1px solid black; padding-right: 10px; padding-bottom: 10px; font-size: 2em;"><i class="fa fa-line-chart" aria-hidden="true"></i></td>',
                '<td style="padding-left: 10px; padding-bottom: 10px;">Average: 4%</td>',
                '<tr/>',
                '<tr>',
                '<td style="border-right: 1px solid black; font-size: 2em;"><i class="fa fa-info" aria-hidden="true"></td>',
                '<td style="padding-left: 10px;">Percentage of children with weight-for-age less than -2 standard deviations of the WHO Child Growth Standards median</td>',
                '<tr/>',
                '<tr>',
                '<td style="border-right: 1px solid black; font-size: 2em;"><i class="fa fa-clock-o" aria-hidden="true"></td>',
                '<td style="padding-left: 10px;">Last updated: 1/5/2017 | Monthly</td>',
                '<tr/>',
                '</table>',
            ];
            d3.select(this.options.element).append('div')
                .attr('class', '')
                .attr('style', 'position: absolute; width: 150px; bottom: 5%; right: 25%;')
                .html(html.join(''));
        },
    };

    vm.fills = {
        '0-25%': '#eef2ff',
        '26%-50%': '#bcd6e7',
        '51%-75%': '#6baed6',
        '76%-100%': '#2171b5',
        'defaultFill': '#eef2ff',
    };

    maternalChildService.getUnderweightChildrenData().then(function(response) {
        vm.mapData = response.data;
    });
}

UnderweightChildrenReportController.$inject = ['$routeParams', 'maternalChildService'];

window.angular.module('icdsApp').directive('underweightChildrenReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'underweight-children-report.directive'),
        bindToController: true,
        controller: UnderweightChildrenReportController,
        controllerAs: '$ctrl',
    };
});
