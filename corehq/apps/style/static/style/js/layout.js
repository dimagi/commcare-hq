var hqLayout = {};

hqLayout.selector = {
    navigation: '#hq-navigation',
    content: '#hq-content',
    footer: '#hq-footer',
    sidebar: '#hq-sidebar',
    breadcrumbs: '#hq-breadcrumbs'
};

hqLayout.values = {
    footerHeight: 0,
    isFooterVisible: true
};

hqLayout.utils = {
    getCurrentScrollPosition: function () {
        return $(window).scrollTop() + $(window).height();
    },
    getFooterShowPosition: function () {
        return $(document).height() - (hqLayout.values.footerHeight / 3);
    },
    getAvailableContentHeight: function () {
        var $navigation = $(hqLayout.selector.navigation),
            $footer = $(hqLayout.selector.footer),
            $breadcrumbs = $(hqLayout.selector.breadcrumbs);
        var absorbedHeight = $navigation.outerHeight() + $footer.outerHeight();
        if ($breadcrumbs) {
            absorbedHeight += $breadcrumbs.outerHeight();
        }
        return $(window).height() - absorbedHeight;
    },
    isScrolledToFooter: function () {
        return hqLayout.utils.getCurrentScrollPosition() >= hqLayout.utils.getFooterShowPosition();
    },
    isScrollable: function () {
        return $(document).height() > $(window).height();
    }
};

hqLayout.actions = {
    initialize: function () {
        hqLayout.values.footerHeight = $(hqLayout.selector.footer).innerHeight();
    },
    balanceSidebar: function () {
        var $sidebar = $(hqLayout.selector.sidebar),
            $content = $(hqLayout.selector.content);
        if ($sidebar && $content) {
            console.log('---');
            var availableHeight = hqLayout.utils.getAvailableContentHeight(),
                contentHeight = $content.innerHeight();
            if (contentHeight > availableHeight) {
                $content.css('padding-bottom',
                        $(hqLayout.selector.footer).outerHeight() + 15 + 'px');
                contentHeight = $content.outerHeight();
            }

            var newSidebarHeight = Math.max(availableHeight, contentHeight);
            $sidebar.css('min-height', newSidebarHeight + 'px');
        }
    },
    recheckFooterStatus: function () {
        if (hqLayout.utils.isScrolledToFooter()) {
            console.log('is scrolled to footer');
            hqLayout.actions.showFooter()
        } else if (hqLayout.utils.isScrollable() && !(hqLayout.utils.isScrolledToFooter())) {
            hqLayout.actions.hideFooter();
        } else {
            hqLayout.actions.showFooter();
        }
    },
    showFooter: function () {
        if (!hqLayout.values.isFooterVisible) {
            $(hqLayout.selector.footer).animate({
                bottom: "0"
            });
            hqLayout.values.isFooterVisible = true;
        }
    },
    hideFooter: function () {
        if (hqLayout.values.isFooterVisible) {
            $(hqLayout.selector.footer).animate({
                bottom: -hqLayout.values.footerHeight
            });
            hqLayout.values.isFooterVisible = false;
        }
    }
};

$(window).load(function () {
    hqLayout.actions.initialize();
    hqLayout.actions.balanceSidebar();
    hqLayout.actions.recheckFooterStatus();
});

$(window).resize(function () {
    hqLayout.actions.balanceSidebar();
    hqLayout.actions.recheckFooterStatus();
});

$(window).scroll(function () {
    hqLayout.actions.recheckFooterStatus();
});
