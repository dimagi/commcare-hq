var InlineHelp = (function($){
    var $shield = $('<div />').css({position: "absolute", top: "0", left: "0", zIndex: 1000, background: null}),
        $window = $(window),
        initShield = function () {
            $shield.css({top: $window.scrollTop(),width: $window.width(), height: $window.height()});
        },
        $currentlyOpen;
    $shield.open = function (div) {
        $currentlyOpen = div.css({zIndex: 1001}).show();
        $shield.show();
    };
    $shield.close = function () {
        $shield.hide();
        $currentlyOpen.fadeOut();
    };
    $(function () {
        $shield.appendTo("body");
        initShield();
        $window.resize(initShield);
        $window.scroll(initShield);
        $shield.hide();
    });
    $shield.click(function () {
        $shield.close();
    });
    function InlineHelp(link, text, key) {
        this.$link = $(link);
        this.$text = $(text).addClass('ui-corner-all');
        this.url = this.$text.text() === "" ? InlineHelp.get_url(key) : null;
    }
    InlineHelp.get_url = (function(key) {
        var parts = key.split('/');
        return "/static/" + parts[0] + "/help/" + parts[1] + ".txt";
    });
    InlineHelp.LINK_HTML = "[<a href='#'>?</a>]";

    InlineHelp.prototype.renderLink = (function(){
        var self = this;
        self.$link.html(InlineHelp.LINK_HTML);

    });
    InlineHelp.prototype.renderText = (function(callback){
        var self = this;
        if (this.url) {
            $.get(this.url, function(data){
                self.$text.html(data);
            });
        }
    });
    InlineHelp.prototype.init = (function(){
        var self = this;
        self.renderLink();
        self.renderText();
        self.$text.hide();
        self.$link.click(function(e){
            e.preventDefault();
            $shield.open(self.$text);
        });

    });
    InlineHelp.$shield = $shield;
    InlineHelp.$currentlyOpen = $currentlyOpen;
    return InlineHelp;
})(jQuery);