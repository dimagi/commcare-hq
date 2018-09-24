hqDefine('app_manager/js/download_index_main',[
    'jquery',
    'underscore',
    'hqwebapp/js/base_ace',
    'app_manager/js/download_async_modal',
    'app_manager/js/source_files',
],function ($, _, baseAce) {

    $(function () {
        //Use hqRequire to load the ace modes from CDN


        var elements = $('.prettyprint');
        _.each(elements, function (elem) {

            var fileName = $(elem).data('filename'),
                mode = fileName.endsWith('json') ? 'ace/mode/json' : 'ace/mode/xml',
                option = {
                    useWorker: false,
                    readOnly: true,
                };

            baseAce.initAceEditor(elem, mode, option,undefined);

        });


    });

});