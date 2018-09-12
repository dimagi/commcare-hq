var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('downloadService', ['$http', function($http) {
    return {
        createTask: function(data) {
            window.ga('send', 'event', {
                'eventCategory': 'ISSNIP Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Creating Task',
            });
            return $http.post(url('icds_export_indicator'),
                $.param(data),
                {headers: {'Content-Type': 'application/x-www-form-urlencoded'}}
            ).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'ISSNIP Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Creating Task',
                    });
                    return response.data;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'ISSNIP Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Creating Task',
                    });
                }
            );
        },
        getStatus: function(task_id) {
            window.ga('send', 'event', {
                'eventCategory': 'ISSNIP Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Checking Status',
            });
            return $http.get(url('issnip_pdf_status'), {
                params: {task_id: task_id},
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'ISSNIP Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Checking Status',
                    });
                    return response.data;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'ISSNIP Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Checking Status',
                    });
                }
            );
        },
    };
}]);
