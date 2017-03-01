/* globals hqDefine */
hqDefine('app_manager/js/import_app.js', function () {
    function CompressionViewModel(source, post_url){
        var self = this;
        self.name = ko.observable("");
        self.source = ko.observable(source);
        self.save = function(formElement) {
            $.postGo(post_url,
                     {name : self.name(),
                      compressed: LZW.compress(self.source())}
                    );
            return false;
        };
    }

    $(function () {
        $(".historyBack").click(function () {
            history.back();
            return false;
        });
 
        var source = hqImport('hqwebapp/js/initial_page_data.js').get('export_json');
        var post_url = hqImport('hqwebapp/js/urllib.js').reverse('import_app');
        $('#app-import-form').koApplyBindings(new CompressionViewModel(source, post_url));
    });
});
