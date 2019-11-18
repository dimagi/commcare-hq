hqDefine("hqwebapp/js/layout", ['jquery'], function ($) {
    var self = {};

    self.selector = {
        navigation: '#hq-navigation',
        content: '#hq-content',
        appmanager: '#js-appmanager-body',
        footer: '#hq-footer',
        sidebar: '#hq-sidebar',
        breadcrumbs: '#hq-breadcrumbs',
        messages: '#hq-messages-container',
        publishStatus: '#js-publish-status',
    };

    self.values = {
        footerHeight: 0,
        isFooterVisible: true,
        isAppbuilderResizing: false,
    };

    self.balancePreviewPromise = $.Deferred();
    self.utils = {
        getCurrentScrollPosition: function () {
            return $(window).scrollTop() + $(window).height();
        },
        getFooterShowPosition: function () {
            return $(document).height() - (self.values.footerHeight / 3);
        },
        getAvailableContentWidth: function () {
            var $sidebar = $(self.selector.sidebar);
            // todo fix extra 10 px padding needed when sidebar suddenly disappears
            // on modal.
            var absorbedWidth = $sidebar.outerWidth();
            return $(window).outerWidth() - absorbedWidth;
        },
        getAvailableContentHeight: function () {
            var $navigation = $(self.selector.navigation),
                $footer = $(self.selector.footer),
                $breadcrumbs = $(self.selector.breadcrumbs),
                $messages = $(self.selector.messages);

            var absorbedHeight = $navigation.outerHeight();
            if ($footer.length) {
                absorbedHeight += $footer.outerHeight();
            }
            if ($breadcrumbs.length) {
                absorbedHeight += $breadcrumbs.outerHeight();
            }
            if ($messages.length) {
                absorbedHeight += $messages.outerHeight();
            }
            return $(window).height() - absorbedHeight;
        },
        isScrolledToFooter: function () {
            return self.utils.getCurrentScrollPosition() >= self.utils.getFooterShowPosition();
        },
        isScrollable: function () {
            return $(document).height() > $(window).height();
        },
        setIsAppbuilderResizing: function (isOn) {
            self.values.isAppbuilderResizing = isOn;
        },
        setBalancePreviewFn: function (fn) {
            self.balancePreviewPromise.resolve(fn);
        },
    };

    self.actions = {
        initialize: function () {
            self.values.footerHeight = $(self.selector.footer).innerHeight();
        },
        balanceSidebar: function () {
            var $sidebar = $(self.selector.sidebar),
                $content = $(self.selector.content),
                $appmanager = $(self.selector.appmanager);

            if ($appmanager.length) {
                var availableHeight = self.utils.getAvailableContentHeight(),
                    contentHeight = $appmanager.outerHeight();

                if ($sidebar.length) {
                    var newSidebarHeight = Math.max(availableHeight, contentHeight);
                    $sidebar.css('min-height', newSidebarHeight + 'px');

                    if ($sidebar.outerHeight() >  $appmanager.outerHeight()) {
                        $content.css('min-height', $sidebar.outerHeight() + 'px');
                        $appmanager.css('min-height', $sidebar.outerHeight() + 'px');
                    }
                }

            } else if ($content.length) {
                var availableHeight = self.utils.getAvailableContentHeight(),
                    contentHeight = $content.innerHeight();

                if (contentHeight > availableHeight) {
                    $content.css('padding-bottom', 15 + 'px');
                    contentHeight = $content.outerHeight();
                }

                if ($sidebar.length && !self.values.isAppbuilderResizing) {
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
            var $content = $(self.selector.content),
                $sidebar = $(self.selector.sidebar),
                $appmanager = $(self.selector.appmanager);

            if ($content.length && $sidebar.length && $appmanager.length === 0) {
                $content.css('width', self.utils.getAvailableContentWidth() + 'px');
            }

        },
        balancePreview: function () {
            // set with setBalancePreviewFn in utils.
            self.balancePreviewPromise.done(function (callback) {
                if (_.isFunction(callback)) {
                    callback();
                }
            });
        },
        showPublishStatus: function () {
            $(self.selector.publishStatus).fadeIn();
        },
        hidePublishStatus: function () {
            $(self.selector.publishStatus).fadeOut();
        },
    };

    $(window).on('load', function () {
        self.actions.initialize();
        if (self.values.isAppbuilderResizing) {
            self.actions.balanceWidths();
        }
        self.actions.balanceSidebar();
        self.actions.balancePreview();
    });

    $(window).resize(function () {
        if (self.values.isAppbuilderResizing) {
            self.actions.balanceWidths();
        }
        self.actions.balanceSidebar();
        self.actions.balancePreview();
    });

    $(window).scroll(function () {
        self.actions.balanceSidebar();
    });

    return {
        getMessagesContainer: function () { return $(self.selector.messages); },
        getNavigationContainer: function () { return $(self.selector.navigation);},
        hidePublishStatus: self.actions.hidePublishStatus,
        showPublishStatus: self.actions.showPublishStatus,
        setBalancePreviewFn: self.utils.setBalancePreviewFn,
        setIsAppbuilderResizing: self.utils.setIsAppbuilderResizing,
        getAvailableContentHeight: self.utils.getAvailableContentHeight,
    };
});
