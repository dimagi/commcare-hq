Shield = (function () {
    var Shield = {},
        $shield = $('<div id="shield"/>').css({position: "fixed", bottom: "0", left: "0", zIndex: 1000, background: null}),
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
        if (!div.parent().length) {
            $shield.append(div.click(function (e) {
                return false;
            }));
        }
        $currentlyOpen = div.css({zIndex: 1001}).show();
        onClose = onCloseCallback;
        $shield.show();
    };
    Shield.close = function (effect) {
        effect = effect || 'fadeOut';
        if ($currentlyOpen) {
            if (effect === 'fadeOut') {
                $currentlyOpen.fadeOut(function () {
                    $shield.hide();
                });
            } else {
                $currentlyOpen.hide();
                $shield.hide();
            }
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