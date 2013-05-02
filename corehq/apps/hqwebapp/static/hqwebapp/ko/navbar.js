var HQNavBar = function (o) {
    var self = this;
    self.navigationTabs = ko.observableArray();
    self.navBar = o.navBar || $('#hq-navigation-bar');
    self.tabBar = self.navBar.find('ul[class="nav"]');
    self.buttonBar = self.navBar.find('div[class*="secondary-nav"]');

    self.isThereOverlap = function () {
        while( (self.tabBar.offset().left+self.tabBar.width()) > self.buttonBar.offset().left) {
            self.navigationTabs.push(self.tabBar.find('li').last());
            self.tabBar.find('li').last().remove();
        }
    };

    $(window).resize( function (data, event) {
        self.isThereOverlap();
    });
};

