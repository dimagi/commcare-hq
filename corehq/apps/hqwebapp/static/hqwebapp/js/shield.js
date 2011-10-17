Shield = (function () {
    var Shield = {},
        $shield = $('<div />').css({position: "fixed", bottom: "0", left: "0", zIndex: 1000, background: null}),
        $window = $(window),
        initShield = function () {
            $shield.css({width: $window.width(), height: $window.height()});
        },
        $currentlyOpen,
        onClose;
    Shield.open = function (div, onCloseCallback) {
        if ($currentlyOpen) {
            Shield.close();
        }
        $currentlyOpen = div.css({zIndex: 1001}).show();
        onClose = onCloseCallback;
        $shield.show();
    };
    Shield.close = function () {
        $shield.hide();
        if ($currentlyOpen) {
            $currentlyOpen.fadeOut();
            $currentlyOpen = undefined;
            if (onClose) {
                onClose();
                onClose = undefined;
            }
        }
    };
    Shield.getCurrent = function () {
        return $currentlyOpen;
    };

    $(function () {
        $shield.appendTo("body");
        initShield();
        $window.resize(initShield);
        $window.scroll(initShield);
        $shield.hide();
    });
    $shield.click(function () {
        Shield.close();
    });
    return Shield;
}());