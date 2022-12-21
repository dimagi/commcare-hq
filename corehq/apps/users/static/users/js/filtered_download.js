hqDefine('users/js/filtered_download', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/widgets',      // role selection
    'locations/js/widgets',     // location search
    'hqwebapp/js/components.ko',    // select toggle widget
    'hqwebapp/js/knockout_bindings.ko', // slideVisible binding
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

        self.count = ko.observable(null);
        self.buttonHTML = ko.computed(function () {
            if (self.count() === null) {
                return "<i class='fa fa-spin fa-spinner'></i>";
            }
            var template = self.count() === 1 ? gettext("Download <%- count %> user") : gettext("Download <%- count %> users");
            return _.template(template)({
                count: self.count(),
            });
        });

        self.countUsers = function () {
            self.count(null);
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
                    self.count(data.count);
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
