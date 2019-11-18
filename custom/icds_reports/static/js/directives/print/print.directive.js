/* global moment */

function PrintReportController() {
    var vm = this;

    vm.print = function() {
        var innerContents = document.getElementsByClassName('report-content')[0].innerHTML;
        var head_copy = document.head;
        var popupWindow = window.open('', '_blank', 'width=1100,height=700,scrollbars=no,menubar=no,toolbar=no,location=no,status=no,titlebar=no');

        var reportNameHtml = '<div>Report Name: ' + $('#reportTitle').text() + '</div>';
        var dateHtml = '<div>Date printed: ' + moment().format('YYYY-MM-DD') + '</div>';
        var locationNameHtml = '<div>Location name: ' + ($('#locationName').text() || 'National') + '</div>';

        var reportMetaData = dateHtml + reportNameHtml + locationNameHtml;

        popupWindow.document.open();
        popupWindow.document.write(
            head_copy.innerHTML +
            '<body style="width: 1100px !important;" onload="window.print()">' +
            reportMetaData +
            "<div class='report-content'>" +
            innerContents +
            '</div></body>'
        );
        popupWindow.document.close();
    };
}

window.angular.module('icdsApp').directive('printReport', function() {
    return {
        restrict: 'E',
        template: '<i uib-popover-html="\'Print page\'" popover-placement="left" popover-trigger="\'mouseenter\'" class="fa fa-2x fa-print pointer light-grey" style="margin-top: 12px;" aria-hidden="true" ng-click="$ctrl.print()"></i>',
        scope: {
        },
        bindToController: true,
        controller: PrintReportController,
        controllerAs: '$ctrl',
    };
});
