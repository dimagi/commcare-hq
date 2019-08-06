hqDefine('hqwebapp/js/base_ace', [
    'jquery',
    'knockout',
    'ace-builds/src-min-noconflict/ace',
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/mode-xml',
    'ace-builds/src-min-noconflict/ext-searchbox',
], function (
    $,
    ko,
    ace,
    jsonMode,  // eslint-disable-line no-unused-vars
    xmlMode,   // eslint-disable-line no-unused-vars
    searchBox  // eslint-disable-line no-unused-vars
) {

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
    };
});
