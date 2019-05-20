hqDefine('aaa/js/filters/location_model', [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    'hqwebapp/js/initial_page_data',
    'aaa/js/utils/reach_utils',
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
        self.loc = ko.observable(reachUtils.DEFAULTLOCATION.id);

        self.getLocations = function (parentSelectedId) {
            var params = {
                parentSelectedId: parentSelectedId,
                locationType: self.slug,
            };
            $.post(initialPageData.reverse('location_api'), params, function (data) {
                self.setData(data);
            });
        };

        self.setData = function (data) {
            self.locations([reachUtils.DEFAULTLOCATION].concat(data.data));
            if (self.userLocationId !== void(0) && self.selectedLocation() === reachUtils.DEFAULTLOCATION.id) {
                var location = _.find(self.locations(), function (item) {
                    return item.id === self.userLocationId;
                });
                self.selectedLocation(location.id);
            } else {
                self.selectedLocation(params.selectedLocation || reachUtils.DEFAULTLOCATION.id);
            }
            self.loc(params.selectedLocation || self.userLocationId || reachUtils.DEFAULTLOCATION.id);
        };

        self.setChild = function (child) {
            self.child = child;
        };

        self.selectedLocation.subscribeChanged(function (newValue, oldValue) {
            params.postData.selectedLocation = newValue;
            if (newValue !== oldValue && self.child !== null) {
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

        self.setDefaultOption = function (runCallback) {
            self.selectedLocation(self.userLocationId || reachUtils.DEFAULTLOCATION.id);
            self.loc(self.userLocationId || reachUtils.DEFAULTLOCATION.id);
            if (self.child !== null) {
                self.child.setDefaultOption(false);
            }
            if (runCallback) {
                params.callback();
            }
        };

        self.locationName = ko.computed(function () {
            var location = _.find(self.locations(), function (location) {
                return location.id === self.loc();
            });
            return location.name;
        }, self);

        self.hideName = ko.computed(function () {
            if (self.parent === '' || self.parent.loc() !== reachUtils.DEFAULTLOCATION.id) {
                return false;
            }
            return self.loc() === reachUtils.DEFAULTLOCATION.id;
        }, self);

        self.applyFilter = function () {
            self.loc(self.selectedLocation());
        };

        return self;
    };

    return {
        locationModel: locationModel,
    };
});
