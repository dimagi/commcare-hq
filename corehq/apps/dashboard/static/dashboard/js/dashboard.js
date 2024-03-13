hqDefine("dashboard/js/dashboard", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/components.ko',    // pagination widget
    'hqwebapp/js/bootstrap3/main',     // post-link function
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var tileModel = function (options) {
        var self = {};
        self.title = options.title;
        self.slug = options.slug;
        self.icon = options.icon;
        self.url = options.url;
        self.helpText = options.help_text;
        self.hasError = ko.observable(false);

        // Might get updated if this tile supports an item list but it's empty
        self.hasItemList = ko.observable(options.has_item_list);

        if (self.hasItemList()) {
            self.itemsPerPage = 5;

            // Set via ajax
            self.totalItems = ko.observable();
            self.totalPages = ko.observable();
            self.items = ko.observableArray();
        }

        // Control visibility of various parts of tile content
        self.showBackgroundIcon = ko.computed(function () {
            return self.hasItemList() && !self.hasError();
        });
        self.showSpinner = ko.computed(function () {
            // Show spinner if this is an ajax tile, it's still waiting for one or both requests,
            // and neither request has errored out
            return self.hasItemList()
                   && (self.items().length === 0 || self.totalPages() === undefined)
                   && !self.hasError();
        });
        self.showItemList = ko.computed(function () {
            return !self.showSpinner() && !self.hasError();
        });
        self.showIconLink = ko.computed(function () {
            return !self.hasItemList() || self.hasError();
        });

        // Paging
        if (self.hasItemList()) {
            self.goToPage = function (page) {
                // If request takes a noticeable amount of time, clear items, which will show spinner
                var done = false;
                _.delay(function () {
                    if (!done) {
                        self.items([]);     // clear items to show spinner
                    }
                }, 500);

                // Send request for items on current page
                $.ajax({
                    method: "GET",
                    url: initialPageData.reverse('dashboard_tile', self.slug),
                    data: {
                        itemsPerPage: self.itemsPerPage,
                        currentPage: page,
                    },
                    success: function (data) {
                        self.items(data.items);
                        done = true;
                    },
                    error: function () {
                        self.hasError(true);
                    },
                });

                // Total number of pages is also a separate request, but it only needs to run once
                // and then self.totalPages() never changes again
                if (self.totalItems() === undefined) {
                    $.ajax({
                        method: "GET",
                        url: initialPageData.reverse('dashboard_tile_total', self.slug),
                        success: function (data) {
                            self.totalItems(data.total);
                            self.totalPages(Math.ceil(data.total / self.itemsPerPage));
                            if (data.total === 0) {
                                self.hasItemList(false);
                            }
                        },
                        error: function () {
                            self.hasError(true);
                        },
                    });
                }
            };

            // Initialize with first page of data
            self.goToPage(1);
        }

        return self;
    };

    var dashboardModel = function (options) {
        var self = {};
        self.tiles = _.map(options.tiles, function (t) { return tileModel(t); });
        return self;
    };

    $(function () {
        $("#dashboard-tiles").koApplyBindings(dashboardModel({
            tiles: initialPageData.get("dashboard_tiles"),
        }));
    });
});
