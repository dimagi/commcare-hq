hqDefine('app_manager/js/import_app', function () {
    function CompressionViewModel(source, post_url) {
        var self = this;
        self.know = 'why';
        self.name = ko.observable("");
        self.source = ko.observable(source);
        self.save = function (formElement) {
            $.postGo(post_url, {
                name: self.name(),
                compressed: hqImport("hqwebapp/js/lib/compression").LZW.compress(self.source()),
            });
            return false;
        };
    }

    $(function () {
        $(".historyBack").click(function () {
            history.back();
            return false;
        });

        var source = hqImport('hqwebapp/js/initial_page_data').get('export_json');
        var post_url = hqImport('hqwebapp/js/initial_page_data').reverse('import_app');
        $('#app-import-form').koApplyBindings(new CompressionViewModel(source, post_url));
    });
});
