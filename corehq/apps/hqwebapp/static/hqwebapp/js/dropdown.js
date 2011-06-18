/*globals jQuery */

(function ($) {
    jQuery.fn.dropdown = function () {
        var $dropdown = this.addClass('dropdown'),
            $button = $('> *:first-child', this).addClass('ui-corner ui-corner-top'),
            $list = $('> ul', this).css({zIndex: 1001, left: 0}).addClass("shadow ui-corner ui-corner-bottom"),
            $shield = $('<div />').css({position: "absolute", top: "0", left: "0", zIndex: 1000, background: null}).appendTo('body'),
            $window = $(window),
            isOpen,
            open = function (val) {
                if (val === undefined) {
                    return isOpen;
                } else {
                    isOpen = val;
                    if (isOpen) {
                        $dropdown.addClass('dropdown-open');
                        $button.addClass('shadow').removeClass('ui-corner-bottom');
                        $list.css({top: $button.outerHeight(true)-1}).show();
                        $shield.show();
                    } else {
                        $dropdown.removeClass('dropdown-open');
                        $button.removeClass('shadow').addClass('ui-corner-bottom');
                        $list.hide();
                        $shield.hide();
                    }
                }
            },
            initShield = function () {
                $shield.css({width: $window.width(), height: $window.height()});
            },
            downIcon = 'ui-icon-triangle-1-s';
        $('<div class="ui-icon" />').addClass(downIcon).prependTo($button);
        initShield();
        $(window).resize(initShield);
        open(false);

        $list.hide();
        $list.click(function () {
            open(false);
        });
        $button.click(function () {
            open(!open());
            return false;
        });
        $shield.click(function () {
            if (open()) {
                open(false);
            }
        });
    };
    
    document.write(
        "<style>\
            .dropdown {\
                position: relative;\
                white-space: nowrap;\
            }\
            .dropdown > *:first-child {\
                display: block;\
                border: 1px solid #CCC;\
                background-color: white;\
                padding: .5em 1em;\
                font-weight: bold;\
            }\
            .dropdown.dropdown-open > *:first-child, .dropdown > *:first-child:hover, .dropdown li > *:hover {\
                background-color: #DDF;\
            }\
            .dropdown ul {\
                display: table;\
                list-style: none;\
                border-collapse: collapse;\
                margin: 0;\
                position: absolute;\
                padding: 0;\
                top: 0;\
                left: 0;\
            }\
            .dropdown li {\
                display: table-row;\
            }\
            .dropdown li > * {\
                display: table-cell;\
                border: 1px solid #CCC;\
                background-color: white;\
                padding: .5em 1em;\
            }\
        </style>"
    );
    
}(jQuery));