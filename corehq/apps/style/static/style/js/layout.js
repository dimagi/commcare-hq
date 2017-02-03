var hqLayout = {};

hqLayout.selector = {
    navigation: '#hq-navigation',
    content: '#hq-content',
    footer: '#hq-footer',
    sidebar: '#hq-sidebar',
    breadcrumbs: '#hq-breadcrumbs',
    messages: '#hq-messages-container',
};

hqLayout.values = {
    footerHeight: 0,
    isFooterVisible: true,
    isAppbuilderResizing: false,
};

hqLayout.utils = {
    getCurrentScrollPosition: function () {
        return $(window).scrollTop() + $(window).height();
    },
    getFooterShowPosition: function () {
        return $(document).height() - (hqLayout.values.footerHeight / 3);
    },
    getAvailableContentWidth: function () {
        var $sidebar = $(hqLayout.selector.sidebar);
        // todo fix extra 10 px padding needed when sidebar suddenly disappears
        // on modal.
        var absorbedWidth = $sidebar.outerWidth() + 12;
        return $(window).outerWidth() - absorbedWidth;
    },
    getAvailableContentHeight: function () {
        var $navigation = $(hqLayout.selector.navigation),
            $footer = $(hqLayout.selector.footer),
            $breadcrumbs = $(hqLayout.selector.breadcrumbs);
        var absorbedHeight = $navigation.outerHeight() + $footer.outerHeight();
        if ($breadcrumbs.length) {
            absorbedHeight += $breadcrumbs.outerHeight();
        }
        return $(window).height() - absorbedHeight;
    },
    isScrolledToFooter: function () {
        return hqLayout.utils.getCurrentScrollPosition() >= hqLayout.utils.getFooterShowPosition();
    },
    isScrollable: function () {
        return $(document).height() > $(window).height();
    },
    setIsAppbuilderResizing: function (isOn) {
        hqLayout.values.isAppbuilderResizing = isOn;
    },
    setBalancePreviewFn: function (fn) {
        hqLayout.actions.balancePreview = fn;
    }
};

hqLayout.actions = {
    initialize: function () {
        hqLayout.values.footerHeight = $(hqLayout.selector.footer).innerHeight();
    },
    balanceSidebar: function () {
        var $sidebar = $(hqLayout.selector.sidebar),
            $content = $(hqLayout.selector.content);
        if ($content.length) {
            var availableHeight = hqLayout.utils.getAvailableContentHeight(),
                contentHeight = $content.innerHeight();
            if (contentHeight > availableHeight) {
                $content.css('padding-bottom', 15 + 'px');
                contentHeight = $content.outerHeight();
            }

            if ($sidebar.length && !hqLayout.values.isAppbuilderResizing) {
                var newSidebarHeight = Math.max(availableHeight, contentHeight);
                $sidebar.css('min-height', newSidebarHeight + 'px');
            } else {
                if ($sidebar.outerHeight() >  $content.outerHeight()) {
                    $content.css('min-height', $sidebar.outerHeight() + 'px');
                }
            }
        }
    },
    balanceWidths: function () {
        var $content = $(hqLayout.selector.content),
            $sidebar = $(hqLayout.selector.sidebar);
        if ($content.length && $sidebar.length) {
            $content.css('width', hqLayout.utils.getAvailableContentWidth() + 'px');
        }

    },
    balancePreview: function () {
        // set with setBalancePreviewFn in utils.
    }
};

$(window).on('load', function () {
    hqLayout.actions.initialize();
    if (hqLayout.values.isAppbuilderResizing) {
        hqLayout.actions.balanceWidths();
    }
    hqLayout.actions.balanceSidebar();
    hqLayout.actions.balancePreview();
});

$(window).resize(function () {
    if (hqLayout.values.isAppbuilderResizing) {
        hqLayout.actions.balanceWidths();
    }
    hqLayout.actions.balanceSidebar();
    hqLayout.actions.balancePreview();
});

$(window).scroll(function () {
    hqLayout.actions.balanceSidebar();
});
