var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('issnipStatusService', ['$http', function($http) {
    return {
        getStatus: function(task_id) {
            return $http.get(url('issnip_pdf_status'), {
                params: {task_id: task_id},
            }).then(function(response) {
                return response.data;
            });
        },
    };
}]);
