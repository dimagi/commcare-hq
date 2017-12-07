hqDefine("dashboard/js/dashboard", function() {
    var TileModel = function(options) {
        var self = this;
        self.title = options.title;
        self.slug = options.slug;
        self.icon = options.icon;
        self.url = options.url;
        self.helpText = options.help_text;
        self.hasError = ko.observable(false);

        self.hasItemList = options.pagination && options.pagination.pages;
        if (self.hasItemList) {
            self.itemsPerPage = options.pagination.items_per_page;
            self.totalPages = options.pagination.pages;
            self.currentPage = ko.observable();         // 1-indexed
            self.pageList = ko.observableArray();
            self.items = ko.observableArray();
        }

        // Control visibility of various parts of tile content
        self.showBackgroundIcon = ko.computed(function() {
            return self.hasItemList && !self.hasError();
        });
        self.showSpinner = ko.computed(function() {
            return self.hasItemList && self.items().length === 0 && !self.hasError();
        });
        self.showItemList = ko.computed(function() {
            return !self.showSpinner() && !self.hasError();
        });
        self.showIconLink = ko.computed(function() {
            return !self.hasItemList || self.hasError();
        });

        // Paging
        if (self.hasItemList) {
            self.currentPage.subscribe(function(newValue) {
                // If request takes a noticeable amount of time, clear items, which will show spinner
                var done = false;
                _.delay(function() {
                    if (!done) {
                        self.items([]);     // clear items to show spinner
                    }
                }, 500);

                // Send request
                $.ajax({
                    method: "GET",
                    url: hqImport('hqwebapp/js/initial_page_data').reverse('dashboard_tile', self.slug),
                    data: {
                        itemsPerPage: self.itemsPerPage,
                        currentPage: newValue,
                    },
                    success: function(data) {
                        self.items(data.items);
                        done = true;
                    },
                    error: function() {
                        self.hasError(true);
                    },
                });

                // Update pagination
                var maxPages = 6,
                    midpoint = Math.floor(maxPages / 2),
                    lowestPage = 1,
                    highestPage = Math.min(self.totalPages, maxPages);

                // If current page is getting close to the edge of visible pages,
                // bump up which pages are visible. The exact math isn't important, just
                // that the page above and below currentPage, if they exist, are visible.
                if (self.totalPages > maxPages && self.currentPage() > midpoint) {
                    highestPage = Math.min(self.totalPages, maxPages + self.currentPage() - midpoint);
                    lowestPage = highestPage - maxPages;
                }

                self.pageList(_.range(lowestPage, highestPage + 1));
            });

            self.incrementPage = function(increment) {
                var newCurrentPage = self.currentPage() + increment;
                if (newCurrentPage <= 0 || newCurrentPage > self.totalPages) {
                    return;
                }
                self.currentPage(newCurrentPage);
            };

            // Initialize with first page of data
            self.currentPage(1);
        }

        return self;
    };

    var DashboardModel = function(options) {
        var self = this;
        self.tiles = _.map(options.tiles, function(t) { return new TileModel(t); });

        return self;
    };

    $(function() {
        $("#dashboard-tiles").koApplyBindings(new DashboardModel({
            tiles: hqImport("hqwebapp/js/initial_page_data").get("dashboard_tiles"),
        }));
    });
});
