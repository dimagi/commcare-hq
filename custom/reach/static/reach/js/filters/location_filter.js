hqDefine('reach/js/filters/location_filter', [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    'hqwebapp/js/initial_page_data',
    'reach/js/utils/reach_utils',
], function (
    $,
    ko,
    _,
    moment,
    initialPageData,
    reachUtils
) {

    var locationModel = function (params) {
        var self = {};
        self.slug = params.slug;
        self.name = params.name;
        self.parent = params.parent;
        self.child = null;
        self.userLocationId = params.userLocationId;
        self.locations = ko.observableArray([reachUtils.DEFAULTLOCATION]);
        self.selectedLocation = ko.observable(reachUtils.DEFAULTLOCATION.id);

        self.getLocations = function (parentSelectedId) {
            var params = {
                parentSelectedId: parentSelectedId,
                locationType: self.slug,
            };
            $.post(initialPageData.reverse('location_api'), params, function (data) {
                self.locations([reachUtils.DEFAULTLOCATION].concat(data.data));
                if (self.userLocationId !== void(0) && self.selectedLocation() === reachUtils.DEFAULTLOCATION.id) {
                    var location = _.find(self.locations(), function (item) {
                        return item.id === self.userLocationId;
                    });
                    self.selectedLocation(location.id);
                }
            });
        };

        self.setChild = function (child) {
            self.child = child;
        };

        self.selectedLocation.subscribe(function (selectedLocation) {
            params.postData.selectedLocation = selectedLocation;
            if (selectedLocation === reachUtils.DEFAULTLOCATION.id && self.child !== null) {
                self.child.selectedLocation(reachUtils.DEFAULTLOCATION.id);
            }
        });

        if (self.parent !== '') {
            self.parent.selectedLocation.subscribe(function (parentSelectedId) {
                self.getLocations(parentSelectedId);
            });
        } else {
            self.getLocations(null);
        }

        self.isDisabled = function () {
            if (self.userLocationId !== void(0)) {
                return true;
            }
            if (self.parent === '') {
                return false;
            }
            return self.parent.selectedLocation() === reachUtils.DEFAULTLOCATION.id;
        };

        self.setDefaultOption = function () {
            self.selectedLocation(self.userLocationId || reachUtils.DEFAULTLOCATION.id);
        };

        return self;
    };

    return {
        viewModel: function (params) {
            var self = {};
            self.showFilter = ko.observable(false);
            self.hierarchyConfig = ko.observableArray();

            var userRoleType = initialPageData.get('user_role_type');
            var userLocationIds = initialPageData.get('user_location_ids');

            var state = locationModel({slug: 'state', name: 'State', parent: '', userLocationId: userLocationIds[0], postData: params.postData});
            var district = locationModel({slug: 'district', name: 'District', parent: state, userLocationId: userLocationIds[1], postData: params.postData});
            state.setChild(district);
            if (userRoleType === reachUtils.USERROLETYPES.MOHFW) {
                var taluka = locationModel({slug: 'taluka', name: 'Taluka', parent: district, userLocationId: userLocationIds[2], postData: params.postData});
                var phc = locationModel({slug: 'phc', name: 'Primary Health Centre (PHC)', parent: taluka, userLocationId: userLocationIds[3], postData: params.postData});
                var sc = locationModel({slug: 'sc', name: 'Sub-centre (SC)', parent: phc, userLocationId: userLocationIds[4], postData: params.postData});
                var village = locationModel({slug: 'village', name: 'Village', parent: sc, userLocationId: userLocationIds[5], postData: params.postData});
                district.setChild((taluka));
                taluka.setChild(phc);
                phc.setChild(sc);
                sc.setChild(village);
                self.hierarchyConfig([
                    state,
                    district,
                    taluka,
                    phc,
                    sc,
                    village,
                ]);
            } else {
                var block = locationModel({slug: 'block', name: 'Block', parent: district, userLocationId: userLocationIds[2], postData: params.postData});
                var sector = locationModel({slug: 'sector', name: 'Sector (Project)', parent: block, userLocationId: userLocationIds[3], postData: params.postData});
                var awc = locationModel({slug: 'awc', name: 'AWC', parent: sector, userLocationId: userLocationIds[4], postData: params.postData});
                district.setChild((block));
                block.setChild(sector);
                sector.setChild(awc);
                self.hierarchyConfig([
                    state,
                    district,
                    block,
                    sector,
                    awc,
                ]);
            }

            self.resetFilter = function () {
                _.each(self.hierarchyConfig(), function (location) {
                    location.setDefaultOption();
                });
            };

            self.applyFilters = function () {
                self.showFilter(false);
                params.callback();
            };
            return self;
        },
        template: '<div data-bind="template: { name: \'location-template\' }"></div>',
    };
});
