window.angular.module('icdsApp').factory('downloadService', ['$http', function($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;
    return {
        createTask: function(data) {
            gtag.event('ISSNIP Service', 'Fetching data started', 'Creating Task');
            return $http.post(url('icds_export_indicator'),
                $.param(data),
                {
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                }
            ).then(
                function(response) {
                    gtag.event('ISSNIP Service', 'Fetching data succeeded', 'Creating Task');
                    return response.data;
                },
                function() {
                    gtag.event('ISSNIP Service', 'Fetching data failed', 'Creating Task');
                }
            );
        },
        getStatus: function(task_id) {
            gtag.event('ISSNIP Service', 'Fetching data started', 'Checking Status');
            return $http.get(url('issnip_pdf_status'), {
                params: {task_id: task_id},
            }).then(
                function(response) {
                    gtag.event('ISSNIP Service', 'Fetching data succeeded', 'Checking Status');
                    return response.data;
                },
                function() {
                    gtag.event('ISSNIP Service', 'Fetching data failed', 'Checking Status');
                }
            );
        },
        downloadCasData: function (data) {
            gtag.event('CAS Data', 'Fetching data started', 'Creating Task');
            return $http.post(url('cas_export'),
                $.param(data),
                {
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                }
            ).then(
                function (response) {
                    gtag.event('CAS Data', 'Fetching data succeeded', 'Creating Task');
                    return response.data;
                },
                function () {
                    gtag.event('CAS Data', 'Fetching data failed', 'Creating Task');
                }
            );
        },
    };
}]);
