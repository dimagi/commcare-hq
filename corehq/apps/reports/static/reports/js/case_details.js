hqDefine("reports/js/case_details", function() {
    var PagingModel = function(options) {
        var self = this;

        self.propertyNames = options.propertyNames || [];   // ordered list of names
        self.properties = options.properties  || {};        // map of name => value
        self.currentPage = new ko.observable();
        self.totalPages = new ko.observable();
        self.itemsPerPage = 10;
        self.showPagination = self.propertyNames.length > self.itemsPerPage;
        self.query = new ko.observable();

        self.incrementPage = function(increment) {
            var newCurrentPage = self.currentPage() + increment;
            if (newCurrentPage <= 0 || newCurrentPage > self.totalPages) {
                return;
            }
            self.currentPage(newCurrentPage);
        }

        self.visibleItems = ko.observableArray([]);
        self.visiblePages = ko.observableArray([]);

        self.query.subscribe(function(newValue) {
            if (self.currentPage() == 1) {
                self.currentPage.valueHasMutated();     // force items to filter, which is handled by currentPage.subscribe below
            }
            self.currentPage(1);
            self.totalPages(Math.ceil(_.filter(self.propertyNames, self.matchesQuery).length / self.itemsPerPage) || 1);
        });

        self.totalPages.subscribe(function(newValue) {
            self.visiblePages(_.map(_.range(newValue), function(p) { return p + 1; }));
        });

        self.matchesQuery = function(propertyName) {
            return !self.query() || propertyName.indexOf(self.query()) !== -1;
        };

        self.showNoData = ko.computed(function() {
            return self.visibleItems().length === 0;
        });

        self.currentPage.subscribe(function(newValue) {
            self.visibleItems.splice(0);    // remove all items
            var added = 0,
                index = 0;

            while (added < self.itemsPerPage * (newValue - 1) && index < self.propertyNames.length) {
                if (self.matchesQuery(self.propertyNames[index])) {
                    added++;
                }
                index++;
            }

            added = 0;
            while (added < self.itemsPerPage && index < self.propertyNames.length) {
                if (self.matchesQuery(self.propertyNames[index])) {
                    self.visibleItems.push({
                        name: self.propertyNames[index],
                        value: self.properties[self.propertyNames[index]],
                    });
                    added++;
                }
                index++;
            }
        });

        self.propertyChange = function(model, e) {
            var $input = $(e.currentTarget);
            self.properties[$input.data('name')] = $input.val();
        };

        self.submitForm = function(model, e) {
            $(e.currentTarget).disableButton();
            $.post({
                url: hqImport("hqwebapp/js/initial_page_data").reverse("edit_case"),
                data: self.properties,
                success: function(data) {
                    window.location.reload();
                },
            });
            return true;
        };

        // Initialize
        self.currentPage(1);
        self.query("");

        return self;
    };

    $(function() {
        $('#close_case').submit(function() {
            hqImport('analytix/js/google').track.event('Edit Data', 'Close Case', '-', "", {}, function () {
                document.getElementById('close_case').submit();
            });
            return false;
        });

        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            $editPropertiesModal = $("#edit-dynamic-properties");
        $("#edit-dynamic-properties-trigger").click(function() {
            $editPropertiesModal.modal();
        });
        $editPropertiesModal.koApplyBindings(new PagingModel({
            properties: initial_page_data('dynamic_properties'),
            propertyNames: initial_page_data('dynamic_properties_names'),
        }));
    });
});
