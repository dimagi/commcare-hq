hqDefine("reports/js/case_details", function() {
    var PagingModel = function(options) {
        var self = this;

        self.currentPage = new ko.observable();
        self.totalPages = options.totalPages;
        self.itemsPerPage = options.itemsPerPage;

        self.incrementPage = function(increment) {
            var newCurrentPage = self.currentPage() + increment;
            if (newCurrentPage <= 0 || newCurrentPage > self.totalPages) {
                return;
            }
            self.currentPage(newCurrentPage);
        }

        self.visibleItems = ko.observableArray([1]);

        self.isVisible = ko.computed(function(a, b, c) {
            return true;
        });

        self.currentPage.subscribe(function(newValue) {
            self.visibleItems.splice(0);    // remove all items
            for (var index = 0; index < self.itemsPerPage; index++) {
                self.visibleItems.push(self.itemsPerPage * (newValue - 1) + index);
            }
        });

        // Initialize to first page
        self.currentPage(1);

        return self;
    };

    $(function() {
        $('#close_case').submit(function() {
            hqImport('analytix/js/google').track.event('Edit Data', 'Close Case', '-', "", {}, function () {
                document.getElementById('close_case').submit();
            });
            return false;
        });

        var $editPropertiesModal = $("#edit-dynamic-properties");
        $("#edit-dynamic-properties-trigger").click(function() {
            $editPropertiesModal.modal();
        });
        $editPropertiesModal.koApplyBindings(new PagingModel($editPropertiesModal.data()));
    });
});
