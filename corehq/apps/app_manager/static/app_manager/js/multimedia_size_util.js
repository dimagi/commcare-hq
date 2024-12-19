hqDefine('app_manager/js/multimedia_size_util',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/bootstrap3/alert_user',
    'hqwebapp/js/initial_page_data',
], function ($, _, ko, alertUser, initialPageData) {
    var multimediaSize = function (name, size) {
        var self = {};
        self.name = ko.observable(name);
        self.size = ko.observable(size);
        return self;
    };
    var multimediaSizesContainer = function (buildProfiles) {
        var self = {};
        self.views = [];
        self.buildProfiles = ko.observableArray(buildProfiles);
        self.buildProfileId = ko.observable();
        self.buildProfileId.subscribe(function (buildProfileId) {
            _.each(self.views, function (view) {
                view.buildProfileId(buildProfileId);
            });
        });
        return self;
    };
    var multimediaSizeView = function (firstAppID, secondAppID) {
        var self = {};
        self.firstAppID = firstAppID;
        self.secondAppID = secondAppID;
        self.comparison = !!secondAppID;
        if (self.comparison) {
            self.defaultUrl = initialPageData.reverse("compare_multimedia_sizes");
        } else {
            self.defaultUrl = initialPageData.reverse("get_multimedia_sizes", firstAppID);
        }
        self.buildProfileId = ko.observable();
        self.url = ko.observable(self.defaultUrl);
        self.sizes = ko.observableArray();
        self.loadState = ko.observable(null);
        self.showSpinner = ko.observable(false);
        self.load = function () {
            self.loadState('loading');
            $.ajax({
                url: self.url(),
                success: function (content) {
                    self.sizes(_.map(content, function (mmsize, mmType) {
                        return multimediaSize(mmType, mmsize);
                    }));
                    self.loadState('loaded');
                },
                error: function (data) {
                    if (_.has(data, 'responseJSON')) {
                        alertUser.alert_user(data.responseJSON.message, "danger");
                    } else {
                        alert(gettext('Oops, there was a problem loading this section. Please try again.'));
                    }
                    self.loadState('error');
                },
            });
        };
        self.buildProfileId.subscribe(function (buildProfileId) {
            if (buildProfileId) {
                if (self.comparison) {
                    self.url(initialPageData.reverse("compare_multimedia_sizes_for_build_profile", buildProfileId));
                } else {
                    self.url(initialPageData.reverse("get_multimedia_sizes_for_build_profile",
                        self.firstAppID, buildProfileId));
                }
            } else {
                self.loadDefault();
            }
        });
        self.loadDefault = function () {
            self.url(self.defaultUrl);
        };
        self.url.subscribe(function () {
            self.load();
        });
        self.load();
        return self;
    };
    return {
        multimediaSizeView: multimediaSizeView,
        multimediaSizesContainer: multimediaSizesContainer,
    };
});
