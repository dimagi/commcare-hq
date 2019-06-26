/**
 *  Knockout Pagination Component
 *
 *  Include the <pagination> element on on your knockout page with the following parameters:
 *      goToPage(page): A function that updates your view with new items for the given page.
 *      perPage: A knockout observable that holds the number of items per page.
 *          This will be updated when the user changes the number of items using the dropdown.
 *          This should be used in your `goToPage` function to return the correct number of items.
 *      totalItems: A knockout observable that returns the total number of items
 *      inlinePageListOnly: Optional. True or false. If true, leave off the "Showing X to Y of Z entries"
 *          text and the associated dropdown.
 *      showSpinner: Optional. An observable. If provided, the widget will replace the current page number
 *          with a spinner when this observable's value is truthy. Useful for ajax-based pagination
 *          (calling code should set the observable to true before kicking off ajax request, then false
 *          in the success and error callbacks).
 *      slug: Optional. A string unique among pagination widgets. If provided, used to save perPage value
 *          in a cookie.
 *      itemsTextTemplate: Optional. A string that contains <%= firstItem %>, <%= lastItem %>, <%= maxItems %>
 *          which shows up next to the left of the limit dropdown.
 *
 *  See releases_table.html for an example.
 */

hqDefine('hqwebapp/js/components/pagination', [
    'knockout',
    'underscore',
], function (
    ko,
    _
) {
    return {
        viewModel: function (params) {
            var self = {};

            // load initial values based on GET parameters
            self.initialValues = {};
            self._url = new URL(window.location.href);
            if (params.pageSlug) {
                self.initialValues.page = parseInt(self._url.searchParams.get(params.pageSlug));
            }
            if (params.limitSlug) {
                self.initialValues.limit = parseInt(self._url.searchParams.get(params.limitSlug));
            }
            self.watchChanges = (typeof params.watchChanges !== 'undefined') ? params.watchChanges : true;

            self.currentPage = ko.observable(self.initialValues.page || self.currentPage || 1);

            self.totalItems = params.totalItems;
            self.totalItems.subscribe(function (newValue) {
                if (self.watchChanges()) {
                    self.goToPage(1);
                }
            });

            self.slug = params.slug;
            self.inlinePageListOnly = !!params.inlinePageListOnly;
            self.perPage = ko.isObservable(params.perPage) ? params.perPage : ko.observable(params.perPage);
            if (!self.inlinePageListOnly) {
                self.perPageCookieName = 'ko-pagination-' + self.slug;
                self.perPage(self.initialValues.limit || $.cookie(self.perPageCookieName) || self.perPage());
                self.perPage.subscribe(function (newValue) {
                    if (self.watchChanges()) {
                        self.goToPage(1);
                    }
                    if (self.slug) {
                        $.cookie(self.perPageCookieName, newValue, { expires: 365, path: '/' });
                    }
                });
            }

            self.perPageOptionsText = function (num) {
                return _.template(gettext('<%= num %> per page'))({ num: num });
            };

            self.numPages = ko.computed(function () {
                return Math.ceil(self.totalItems() / self.perPage());
            });

            self.maxPagesShown = params.maxPagesShown || 9;
            self.showSpinner = params.showSpinner || ko.observable(false);

            self.nextPage = function (model, e) {
                self.goToPage(Math.min(self.currentPage() + 1, self.numPages()), e);
            };
            self.previousPage = function (model, e) {
                self.goToPage(Math.max(self.currentPage() - 1, 1), e);
            };
            self.goToPage = function (page, e) {
                // make sure that the first goToPage that's called does not override the initialValues from GET
                self.currentPage(self.initialValues.page || page);
                self.initialValues.page = undefined;
                params.goToPage(self.currentPage());
                if (e) {
                    e.stopPropagation();
                }
            };
            self.itemsShowing = ko.computed(function () {
                return self.currentPage() * self.perPage();
            });
            self.itemsText = ko.computed(function () {
                var lastItem = Math.min(self.currentPage() * self.perPage(), self.totalItems());
                return _.template(
                    params.itemsTextTemplate || gettext('Showing <%= firstItem %> to <%= lastItem %> of <%= maxItems %> entries')
                )({
                    firstItem: ((self.currentPage() - 1) * self.perPage()) + 1,
                    lastItem: isNaN(lastItem) ? 1 : lastItem,
                    maxItems: self.totalItems(),
                });
            });
            self.pagesShown = ko.computed(function () {
                var pages = [];
                for (var pageNum = 1; pageNum <= self.numPages(); pageNum++) {
                    var midPoint = Math.floor(self.maxPagesShown / 2),
                        leftHalf = pageNum >= self.currentPage() - midPoint,
                        rightHalf = pageNum <= self.currentPage() + midPoint,
                        pageVisible = (leftHalf && rightHalf) || pages.length < self.maxPagesShown && pages[pages.length - 1] > self.currentPage();
                    if (pageVisible) {
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
