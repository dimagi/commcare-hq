/*globals jQuery */

(function ($) {
    jQuery.fn.dropdown = function () {
        var $dropdown = this.addClass('dropdown'),
            $button = $('> *:first-child', this).addClass('ui-corner ui-corner-top').disableSelection(),
            $list = $button.next().css({zIndex: 1001, left: 0}).addClass("shadow ui-corner ui-corner-bottom"),
            isOpen,
            open = function (val) {
                if (val === undefined) {
                    return isOpen;
                } else {
                    isOpen = val;
                    if (isOpen) {
                        $dropdown.addClass('dropdown-open');
                        $button.addClass('shadow').removeClass('ui-corner-bottom');
                        Shield.open($list.css({top: $button.outerHeight(true)-1}), function () {
                            open(false);
                        });
                    } else {
                        $dropdown.removeClass('dropdown-open');
                        $button.removeClass('shadow').addClass('ui-corner-bottom');
                        Shield.close();
                    }
                }
            },
            downIcon = 'ui-icon-triangle-1-s';
        $('<div class="ui-icon" />').addClass(downIcon).prependTo($button);
        open(false);

        $list.hide();
        $list.click(function () {
            open(false);
        });
        $list.find('> li').click(function () {
            var href = $('a', this).attr('href');
            if (href && href !== "#") {
                window.location.href = href;
            } else {
                $('form', this).submit();
            }
        });
        $button.click(function () {
            open(!open());
            return false;
        });
    };
    
    document.write(
        "<style>" +
        "   .dropdown {" +
        "       position: relative;" +
        "       white-space: nowrap;" +
        "   }" +
        "   .dropdown a:hover {" +
        "       text-decoration: none;" +
        "   }" +
        "    .dropdown > *:first-child {" +
        "       display: block;" +
        "       cursor: pointer;" +
        "       border: 1px solid #CCC;" +
        "       background-color: white;" +
        "       padding: .5em 1em;" +
        "       font-weight: bold;" +
        "       color: #0067B1;" +
        "   }" +
        "   .dropdown.dropdown-open > *:first-child," +
        "   .dropdown > *:first-child:hover," +
        "   .dropdown > ul > li > *:hover {" +
        "       background-color: #0067B1;" +
        "       color: #FFF;" +
        "   }" +
        "   .dropdown.dropdown-open > *:first-child a," +
        "   .dropdown > *:first-child:hover a," +
        "   .dropdown > ul > li > *:hover a {" +
        "       color: #FFF;" +
        "   }" +
        "   .dropdown > * + * {" +
        "       position: absolute;" +
        "       padding: 0;" +
        "       top: 0;" +
        "       left: 0;" +
        "       background-color: white;" +
        "       border: 1px solid #CCC;" +
        "   }" +
        "   .dropdown > ul {" +
        "       display: table;" +
        "       list-style: none;" +
        "       border-collapse: collapse;" +
        "       margin: 0;" +
        "   }" +
        "   .dropdown > ul > li {" +
        "       display: table-row;" +
        "       cursor: pointer;" +
        "   }" +
        "   .dropdown > ul > li > * {" +
        "       display: table-cell;" +
        "       border: 1px solid #CCC;" +
        "       padding: .5em 1em;" +
        "   }" +
        "</style>"
    );
    
}(jQuery));