hqDefine('reach/js/filters/location_filter', [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    'hqwebapp/js/initial_page_data',
    'reach/js/utils/reach_utils'
], function (
    $,
    ko,
    _,
    moment,
    initialPageData,
    reachUtils
) {
    return {
        viewModel: function (params) {
            var self = {};
            self.showFilter = ko.observable(false);
            self.hierarchyConfig = ko.observableArray();

            var userRoleType = initialPageData.get('user_role_type');
            if (userRoleType === reachUtils.USERROLETYPES.MOHFW) {
                self.hierarchyConfig([
                    {slug: 'state', name: 'state', parent: ''},
                    {slug: 'district', name: 'District', parent: 'state'},
                    {slug: 'taluka', name: 'Taluka', parent: 'district'},
                    {slug: 'phc', name: 'Primary Health Centre (PHC)', parent: 'taluka'},
                    {slug: 'sc', name: 'Sub-centre (SC)', parent: 'phc'},
                    {slug: 'village', name: 'Village', parent: 'sc'},
                ])
            } else {
                self.hierarchyConfig([
                    {slug: 'state', name: 'state', parent: ''},
                    {slug: 'district', name: 'District', parent: 'state'},
                    {slug: 'block', name: 'Block', parent: 'district'},
                    {slug: 'sector', name: ' Sector (Project) ', parent: 'block'},
                    {slug: 'awc', name: 'AWC', parent: 'sector'}
                ])
            }

            self.resetFilter = function () {
                self.selectedMonth(moment().month() + 1);
                self.selectedYear(moment().year())
            };

            self.applyFilters = function() {
                params.postData.selectedMonth = self.selectedMonth();
                params.postData.selectedYear = self.selectedYear();
                self.showFilter(false);
                params.callback(params.postData)
            };
            return self
        },
        template: '<div data-bind="template: { name: \'location-template\' }"></div>',
    };
});
