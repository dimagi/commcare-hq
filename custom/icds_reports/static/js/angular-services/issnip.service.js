var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('issnipService', ['$http', function($http) {
    return {
        createTask: function(data) {
            return $http.post(url('icds_export_indicator'),
                $.param(data),
                {headers: {'Content-Type': 'application/x-www-form-urlencoded'}}
            ).then(function (response) {
                return response.data;
            });
        },
        getStatus: function(task_id) {
            return $http.get(url('issnip_pdf_status'), {
                params: {task_id: task_id},
            }).then(function(response) {
                return response.data;
            });
        },
    };
}]);
