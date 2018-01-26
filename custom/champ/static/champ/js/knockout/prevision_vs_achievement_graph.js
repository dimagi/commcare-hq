ko.bindingHandlers.select2 = {
    init: function (element, valueAccessor, allBindings, viewModel, bindingContext) {
        var options = valueAccessor();
        $(element).select2(options);
    }
};

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrecisionVsAcievementsGraphModel() {
    var self = this;
    self.testingString = ko.observable("1234");
    self.title = ko.observable("Prevision vs Achievements");
    self.availableValues = ko.observableArray();

    self.target_district = ko.observable();

    self.getData = function() {
        var get_url = url('hierarchy');
        $.getJSON(get_url, function(data) {
            self.availableValues(data.districts);
        })
    };

    self.getData();

    self.districtOnSelect = function ($item, data) {
        vm.filters.target_cbo = [];
        vm.filters.target_userpl = [];
        vm.filters.target_clienttype = [];

        if ($item.id === '') {
            vm.filters.target_district = [$item.id];
        } else if (vm.filters.target_district.indexOf('') !== -1) {
            vm.filters.target_district = [$item.id];
        }

        var ids = vm.filters.target_district;

        if (ids.length === 0 || $item.id === '') {
            vm.cbos = vm.cbosTmp.slice();
            vm.userpls = vm.userplsTmp.slice();
        } else {
            vm.cbos = [ALL_OPTION].concat(vm.cbosTmp.slice().filter(function (item) {
                return ids.indexOf(item.parent_id) !== -1;
            }));
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    var cbos = vm.cbosTmp.slice().filter(function (cbo) {
                        return ids.indexOf(cbo.parent_id) !== -1;
                    }).map(function (cbo) { return cbo.id; });
                    return cbos.indexOf(clienttype.parent_id) !== -1;
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            }));

        }

    };

}