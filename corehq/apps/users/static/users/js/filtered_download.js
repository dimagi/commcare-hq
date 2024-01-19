hqDefine('users/js/filtered_download', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/widgets',      // role selection
    'locations/js/widgets',     // location search
    'hqwebapp/js/bootstrap3/components.ko',    // select toggle widget
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // slideVisible binding
], function (
    $,
    ko,
    _,
    initialPageData
) {
    function FiltersModel(options) {
        var self = {};

        self.role_id = ko.observable();
        self.search_string = ko.observable();
        self.location_id = ko.observable();
        self.selected_location_only = ko.observable();
        self.user_active_status = ko.observable();
        self.columns = ko.observable();
        self.domains = ko.observableArray();

        self.isCrossDomain = ko.computed(function () {
            return self.domains() && self.domains().length > 0;
        });

        self.user_count = ko.observable(null);
        self.group_count = ko.observable(null);
        self.areStatsLoading = ko.computed(function () {
            return self.user_count() === null;
        });
        self.haveStatsLoaded = ko.computed(function () {
            return !self.areStatsLoading();
        });
        self.statsText = ko.computed(function () {
            var template = self.user_count() === 1 ? gettext("<%- user_count %> user") : gettext("<%- user_count %> users");
            if (self.group_count() !== 0 && self.columns() !== 'usernames') {
                template += self.group_count() === 1 ? gettext(" and <%- group_count %> group") : gettext(" and <%- group_count %> groups");
            }
            return _.template(template)({
                user_count: self.user_count(),
                group_count: self.group_count(),
            });
        });

        self.countUsers = function () {
            self.user_count(null);
            self.group_count(null);
            var data = {
                search_string: self.search_string(),
                domains: self.domains(),
                user_active_status: self.user_active_status(),
            };

            if (!self.isCrossDomain()) {
                data = _.extend(data, {
                    role_id: self.role_id(),
                    location_id: self.location_id(),
                    selected_location_only: self.selected_location_only(),
                });
            }
            $.get({
                url: options.url,
                data: data,
                success: function (data) {
                    self.user_count(data.user_count);
                    self.group_count(data.group_count);
                },
                error: function () {
                    alert(gettext("Error determining number of matching users"));
                },
            });
        };

        self.role_id.subscribe(self.countUsers);
        self.search_string.subscribe(self.countUsers);
        self.location_id.subscribe(self.countUsers);
        self.columns.subscribe(self.countUsers);
        self.domains.subscribe(self.countUsers);
        self.selected_location_only.subscribe(self.countUsers);
        self.user_active_status.subscribe(self.countUsers);

        return self;
    }

    $(function () {
        $("#user-filters").koApplyBindings(FiltersModel({
            'url': initialPageData.get('count_users_url'),
        }));
    });
});
