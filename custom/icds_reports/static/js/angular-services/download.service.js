var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('downloadService', ['$http', function($http) {
    return {
        createTask: function(data) {
            return $http.post(url('icds_export_indicator'),
                $.param(data),
                {headers: {'Content-Type': 'application/x-www-form-urlencoded'}}
            ).then(function (response) {
                return response.data;
            });
        },
        getStatus: function(task_id, isIssnipMonthlyRegister) {
            return $http.get(url('export_status'), {
                params: {
                    task_id: task_id,
                    is_issnip_monthly_register: isIssnipMonthlyRegister ? true : null,
                },
            }).then(function(response) {
                return response.data;
            });
        },
    };
}]);
