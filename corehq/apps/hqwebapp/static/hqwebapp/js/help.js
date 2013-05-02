var InlineHelp = (function($){
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
            Shield.open(self.$text);
        });

    });
    return InlineHelp;
})(jQuery);