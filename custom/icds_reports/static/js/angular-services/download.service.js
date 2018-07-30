var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var issnipServiceEventCategory = google.trackCategory('ISSNIP Service');

window.angular.module('icdsApp').factory('downloadService', ['$http', function($http) {
    return {
        createTask: function(data) {
            issnipServiceEventCategory.event(
                'Fetching data started', 'Creating Task', {'data': data}
            );
            return $http.post(url('icds_export_indicator'),
                $.param(data),
                {headers: {'Content-Type': 'application/x-www-form-urlencoded'}}
            ).then(
                function(response) {
                    issnipServiceEventCategory.event(
                        'Fetching data succeeded', 'Creating Task', {'data': data}
                    );
                    return response.data;
                },
                function() {
                    issnipServiceEventCategory.event(
                        'Fetching data failed', 'Creating Task', {'data': data}
                    );
                }
            );
        },
        getStatus: function(task_id) {
            issnipServiceEventCategory.event(
                'Fetching data started', 'Checking Status', {'task_id': task_id}
            );
            return $http.get(url('issnip_pdf_status'), {
                params: {task_id: task_id},
            }).then(
                function(response) {
                    issnipServiceEventCategory.event(
                        'Fetching data succeeded', 'Checking Status', {'task_id': task_id}
                    );
                    return response.data;
                },
                function() {
                    issnipServiceEventCategory.event(
                        'Fetching data failed', 'Checking Status', {'task_id': task_id}
                    );
                }
            );
        },
    };
}]);
