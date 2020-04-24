window.angular.module('icdsApp').factory('templateProviderService', ['isMobile', function (isMobile) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    function getTemplate(templateName) {
        if (isMobile) {
            return url('icds-ng-template-mobile', templateName);
        } else {
            return url('icds-ng-template', templateName);
        }
    }
    return {
        getTemplate: getTemplate,
        getMapChartTemplate: function () {
            return getTemplate('map-chart');
        },
    };
}]);
