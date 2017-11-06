var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MainController($http) {
    var vm = this;
    vm.title = "Prevision vs Achievements";

    vm.test1 = 10;
    debugger;

    var get_url = url('champ_pva');
    $http({
        method: "GET",
        url: get_url,
        params: {},
    }).then(function(response) {
        debugger;
        vm.chartData = response.data.chart
    });

    vm.chartOptions = {
        "chart": {
            "type": "multiBarChart",
            "height": 450,
            "margin": {
                "top": 20,
                "right": 20,
                "bottom": 60,
                "left": 100
            },
            "clipEdge": true,
            "staggerLabels": false,
            "transitionDuration": 500,
            "stacked": false,
            "showControls": false,
            "xAxis": {
                "axisLabel": "",
                "showMaxMin": false
            },
            "yAxis": {
                "axisLabel": "",
                "axisLabelDistance": 40
            }
        }
    };
}

MainController.$inject = ['$http'];

window.angular.module('champApp', ['nvd3'])
    .controller('MainController', MainController);

