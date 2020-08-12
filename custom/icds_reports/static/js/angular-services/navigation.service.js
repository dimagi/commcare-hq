window.angular.module('icdsApp').factory('navigationService', function () {
    return {
        getPagePath: function (path, params) {
            // constructs a page path like
            // #/maternal_and_child/underweight_children/map?month=5&year=2017&location_name=&location_id
            // from a base path and set of key / value parameters
            var page_path = "#/" + path;
            if (Object.keys(params).length > 0) {
                page_path += '?';
            }
            window.angular.forEach(params, function (v, k) {
                if (v === undefined || v === null) {
                    v = '';
                }
                page_path += (k + '=' + v + '&');
            });
            return page_path;
        },
        getAWCTabFromPagePath: function (path) {
            var awcReportPath = 'awc_reports';
            // Routes for various tabs on PS page
            var tabRoutes = {
                'maternal_child': 'maternal_child',
                'maternal_and_child': 'maternal_child',
                'demographics': 'demographics',
                'awc_infrastructure': 'awc_infrastructure',
                'icds_cas_reach': 'pse',
            };
            for (var tab in tabRoutes) {
                if (path.indexOf(tab) !== -1) {
                    awcReportPath += '/' + tabRoutes[tab];
                    break;
                }
            }
            return awcReportPath;
        },
        isMapDisplayed: function (path) {
            return path.indexOf('/map') !== -1;
        },
    };
});
