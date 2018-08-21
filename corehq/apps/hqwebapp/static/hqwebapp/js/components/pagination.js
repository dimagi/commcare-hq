// Knockout Pagination Component
// Include the <pagination> element on on your knockout page with the following parameters:
// goToPage(page): a function that updates your view with new items for the given page.
// perPage: a knockout observable that holds the number of items per page. This will be updated when the user changes the number of items using the dropdown. This should be used in your `goToPage` function to return the correct number of items.
// totalItems: a knockout observable that returns the total number of items
// See releases_table.html for an example.
// This component must be nested within another element that has had knockout bindings applied to it.

hqDefine('hqwebapp/js/components/pagination', [
    'knockout',
    'underscore',
], function(
    ko,
    _
) {
    return {
        viewModel: function(params){
            var self = {};

            self.currentPage = ko.observable(params.currentPage || 1);
            self.totalItems = params.totalItems;
            self.totalItems.subscribe(function(newValue) {
                self.goToPage(1);
            });
            self.perPage = ko.isObservable(params.perPage) ? params.perPage : ko.observable(params.perPage);
            self.numPages = ko.computed(function(){
                return Math.ceil(self.totalItems() / self.perPage());
            });
            self.perPage.subscribe(function(){
                self.goToPage(1);
            });
            self.inlinePageListOnly = !!params.inlinePageListOnly;
            self.maxPagesShown = params.maxPagesShown || 9;

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
            self.itemsText = ko.computed(function(){
                var lastItem = Math.min(self.currentPage() * self.perPage(), self.totalItems());
                return _.template(
                    gettext('Showing <%= firstItem %> to <%= lastItem %> of <%= maxItems %> entries')
                )({
                    firstItem: ((self.currentPage() - 1) * self.perPage()) + 1,
                    lastItem: isNaN(lastItem) ? 1 : lastItem,
                    maxItems: self.totalItems(),
                });
            });
            self.pagesShown = ko.computed(function(){
                var pages = [];
                for (var pageNum = 1; pageNum <= self.numPages(); pageNum++){
                    var midPoint = Math.floor(self.maxPagesShown / 2),
                        leftHalf = pageNum >= self.currentPage() - midPoint,
                        rightHalf = pageNum <= self.currentPage() + midPoint,
                        pageVisible = (leftHalf && rightHalf) || pages.length < self.maxPagesShown && pages[pages.length - 1] > self.currentPage();
                    if (pageVisible){
                        pages.push(pageNum);
                    }
                }
                return pages;
            });
            return self;
        },
        template: '<div data-bind="template: { name: \'ko-pagination-template\' }"></div>',
    };
});
