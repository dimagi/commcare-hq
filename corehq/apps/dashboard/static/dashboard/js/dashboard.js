hqDefine("dashboard/js/dashboard", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function(
    $,
    ko,
    _,
    initialPageData
) {
    var TileModel = function(options) {
        var self = this;
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
            self.currentPage = ko.observable();         // 1-indexed
            self.pageList = ko.observableArray();

            // Set via ajax
            self.totalPages = ko.observable();
            self.items = ko.observableArray();
        }

        // Control visibility of various parts of tile content
        self.showBackgroundIcon = ko.computed(function() {
            return self.hasItemList() && !self.hasError();
        });
        self.showSpinner = ko.computed(function() {
            // Show spinner if this is an ajax tile, it's still waiting for one or both requests,
            // and neither request has errored out
            return self.hasItemList()
                   && (self.items().length === 0 || self.totalPages() === undefined)
                   && !self.hasError();
        });
        self.showItemList = ko.computed(function() {
            return !self.showSpinner() && !self.hasError();
        });
        self.showIconLink = ko.computed(function() {
            return !self.hasItemList() || self.hasError();
        });

        // Paging
        if (self.hasItemList()) {
            // Tiles with a lot of pages can't list them all out in the pagination widget.
            // This function determines which page numbers to display.
            self.updatePagination = function() {
                var maxPages = 6,
                    midpoint = Math.floor(maxPages / 2),
                    lowestPage = 1,
                    highestPage = Math.min(self.totalPages(), maxPages);

                // If current page is getting close to the edge of visible pages,
                // bump up which pages are visible. The exact math isn't important, just
                // that the page above and below currentPage, if they exist, are visible.
                if (self.totalPages() > maxPages && self.currentPage() > midpoint) {
                    highestPage = Math.min(self.totalPages(), maxPages + self.currentPage() - midpoint);
                    lowestPage = highestPage - maxPages;
                }

                self.pageList(_.range(lowestPage, highestPage + 1));
            };

            self.currentPage.subscribe(function(newValue) {
                // If request takes a noticeable amount of time, clear items, which will show spinner
                var done = false;
                _.delay(function() {
                    if (!done) {
                        self.items([]);     // clear items to show spinner
                    }
                }, 500);

                // Send request for items on current page
                var itemRequest = $.ajax({
                    method: "GET",
                    url: initialPageData.reverse('dashboard_tile', self.slug),
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

                // Total number of pages is also a separate request, but it only needs to run once
                // and then self.totalPages() never changes again
                if (self.totalPages()) {
                    self.updatePagination();
                } else {
                    var totalPagesRequest = $.ajax({
                        method: "GET",
                        url: initialPageData.reverse('dashboard_tile_total', self.slug),
                        success: function(data) {
                            self.totalPages(Math.ceil(data.total / self.itemsPerPage) );
                            if (data.total === 0) {
                                self.hasItemList(false);
                            }
                        },
                        error: function() {
                            self.hasError(true);
                        },
                    });
                    $.when(itemRequest, totalPagesRequest).then(function() {
                        self.updatePagination();
                    });
                }
            });

            self.incrementPage = function(increment) {
                var newCurrentPage = self.currentPage() + increment;
                if (newCurrentPage <= 0 || newCurrentPage > self.totalPages()) {
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
            tiles: initialPageData.get("dashboard_tiles"),
        }));
    });
});
