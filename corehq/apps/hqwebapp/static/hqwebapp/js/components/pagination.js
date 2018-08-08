hqDefine('hqwebapp/js/components/pagination', function() {
    return {
        viewModel: function(params){
            var self = {};

            self.currentPage = ko.observable(params.currentPage || 1);
            self.totalItems = params.totalItems;
            self.perPage = ko.observable(params.perPage || 5);
            self.numPages = ko.computed(function(){
                return Math.ceil(self.totalItems() / self.perPage());
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
