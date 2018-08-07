hqDefine('hqwebapp/js/components/pagination', function() {
    return {
        viewModel: function(params){
            var self = {};
            self.currentPage = ko.observable(params.currentPage || 1);
            self.totalItems = ko.observable(params.totalItems || 500);
            self.perPage = ko.observable(params.perPage || 10);
            self.numPages = ko.computed(function(){
                return Math.ceil(self.totalItems() / self.perPage());
            });

            self.nextPage = function(){
                self.currentPage(Math.min(self.currentPage() + 1, self.numPages()));
            };
            self.previousPage = function(){
                self.currentPage(Math.max(self.currentPage() - 1, 1));
            };
            self.goToPage = function(page){
                self.currentPage(page);
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
