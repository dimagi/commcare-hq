hqDefine('reach/js/filters/location_model', [
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
            }
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

        self.setDefaultOption = function () {
            self.selectedLocation(self.userLocationId || reachUtils.DEFAULTLOCATION.id);
        };

        return self;
    };

    return {
        locationModel: locationModel,
    };
});
