hqDefine('hqwebapp/js/base_ace', [
    'jquery',
    'underscore',
    'knockout',
    'ace-builds/src-min-noconflict/ace',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    ko,
    ace,
    initialPageData
) {
    var self = {};
    self.editor = [];

    ace.config.set('basePath', initialPageData.get('ace_base_path'));
    ace.require("ace/mode/json");
    ace.require("ace/mode/xml");
    ace.require("ace/ext/searchbox");

    var initAceEditor = function (element, mode, options, value) {
        var defaultOptions = {
            showPrintMargin: false,
            maxLines: 40,
            minLines: 3,
            fontSize: 14,
            wrap: true,
            useWorker: false,
            readOnly: true,
        };
        options = $.extend(defaultOptions, options);

        var editor = ace.edit(element, options);

        editor.session.setMode(mode);
        if (value) {
            editor.getSession().setValue(value);
        }
        return editor;

    };


    var initJsonWidget = function (element) {
        var $element = $(element),
            editorElement = $element.after('<pre />').next()[0];
        var editor = initAceEditor(editorElement, 'ace/mode/json', {
            useWorker: true,
            readOnly: false,
        }, $element.val());
        $element.hide();

        editor.getSession().on('change', function () {
            $element.val(editor.getSession().getValue());
        });
    };

    var getEditors = function () {
        return self.editor;
    };

    /**
     * initObservableJsonWidget allows the ACE editor to be applied to
     * elements controlled by Knockout observables. The is useful for
     * forms that are managed by a Knockout view model, because, for
     * example, they can be added or removed from the page dynamically.
     *
     * This function relies on the element having its `name` attribute
     * set to the same name as the view model's observable property.
     * e.g.
     *
     *     my_template.html:
     *     ...
     *     <form>
     *       <textarea name="foo" bind-data="value: foo"></texarea>
     *     ...
     *
     *     my_view_model.js:
     *     ...
     *     var viewModel = function () {
     *         var self = {};
     *         self.foo = ko.observable();
     *     ...
     *
     */
    var initObservableJsonWidget = function (element) {
        var $element = $(element),
            editorElement = $element.after('<pre />').next()[0],
            viewModel = ko.dataFor(element),
            fieldName = $element.attr('name'),  // The element must have its `name` attribute set.
            observable = viewModel[fieldName];  // The view model property must have the same name as the field.
        var editor = initAceEditor(editorElement, 'ace/mode/json', {
            useWorker: true,
            readOnly: false,
        }, observable());
        $element.hide();

        editor.getSession().on('change', function () {
            observable(editor.getSession().getValue());
        });
        self.editor.push(editor);
        return editor;
    };


    $(function () {
        _.each($('.jsonwidget'), initJsonWidget);
        // We don't need to bother initializing Observable JSON widgets;
        // the reason we use Observables is because they are created
        // dynamically, so they will be initialized when they are
        // created.
    });

    return {
        initJsonWidget: initJsonWidget,
        initObservableJsonWidget: initObservableJsonWidget,
        initAceEditor: initAceEditor,
        getEditors: getEditors,
    };
});
