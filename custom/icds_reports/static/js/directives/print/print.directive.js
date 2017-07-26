function PrintReportController() {
    var vm = this;

    vm.print = function() {
        var innerContents = document.getElementsByClassName('report-content')[0].innerHTML;
        var head_copy = document.head;
        var popupWinindow = window.open('', '_blank', 'width=1100,height=700,scrollbars=no,menubar=no,toolbar=no,location=no,status=no,titlebar=no');
        popupWinindow.document.open();
        popupWinindow.document.write(head_copy.innerHTML + '<body style="width: 1100px !important;" onload="window.print()">' + innerContents + '</body>');
        popupWinindow.document.close();
    };
}

window.angular.module('icdsApp').directive('printReport', function() {
    return {
        restrict: 'E',
        template: '<i uib-popover-html="\'Print page\'" popover-placement="left" popover-trigger="\'mouseenter\'" class="fa fa-2x fa-print pointer" style="padding: 3px;" aria-hidden="true" ng-click="$ctrl.print()"></i>',
        scope: {
        },
        bindToController: true,
        controller: PrintReportController,
        controllerAs: '$ctrl',
    };
});