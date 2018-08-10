// Knockout Pagination Component
// Include the <pagination> element on on your knockout page with the following parameters:
// goToPage(page): a function that updates your view with new items for the given page.
// perPage: a knockout observable that holds the number of items per page. This will be updated when the user changes the number of items using the dropdown. This should be used in your `goToPage` function to return the correct number of items.
// totalItems: a knockout observable that returns the total number of items
// See releases_table.html for an example.
// This component must be nested within another element that has had knockout bindings applied to it.

hqDefine('hqwebapp/js/components/pagination', function() {
    return {
        viewModel: function(params){
            var self = {};

            self.currentPage = ko.observable(params.currentPage || 1);
            self.totalItems = params.totalItems;
            self.perPage = params.perPage;
            self.numPages = ko.computed(function(){
                return Math.ceil(self.totalItems() / self.perPage());
            });
            self.perPage.subscribe(function(){
                self.goToPage(1);
            });
            self.nextPage = function(){
                self.goToPage(Math.min(self.currentPage() + 1, self.numPages()));
            };
            self.previousPage = function(){
                self.goToPage(Math.max(self.currentPage() - 1, 1));
            };
            self.goToPage = function(page){
                self.currentPage(page);
                params.goToPage(self.currentPage());
            };
            self.itemsShowing = ko.computed(function(){
                return self.currentPage() * self.perPage();
            });
            self.pagesShown = ko.computed(function(){
                var pages = [];
                for (var i = 1; i <= self.numPages(); i++){
                    if (i >= self.currentPage() - 2 && i <= self.currentPage() + 2){
                        pages.push(i);
                    }
                    else if (pages.length < 5 && pages[pages.length - 1] > self.currentPage()){
                        pages.push(i);
                    };
                };
                return pages;
            });
            return self;
        },
        template: '<div data-bind="template: { name: \'ko-pagination-template\' }"></div>'
    };
});
