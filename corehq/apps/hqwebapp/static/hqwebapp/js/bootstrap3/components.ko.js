hqDefine("hqwebapp/js/bootstrap3/components.ko", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/components/inline_edit',
    'hqwebapp/js/components/pagination',
    'hqwebapp/js/components/search_box',
    'hqwebapp/js/components/select_toggle',
    'hqwebapp/js/components/bootstrap3/feedback',
    'hqwebapp/js/components/key_value_list',
], function (
    $,
    ko,
    _,
    inlineEdit,
    pagination,
    searchBox,
    selectToggle,
    feedback,
    keyValueList
) {
    var components = {
        'inline-edit': inlineEdit,
        'pagination': pagination,
        'search-box': searchBox,
        'select-toggle': selectToggle,
        'feedback': feedback,
        'key-value-list': keyValueList,
    };

    _.each(components, function (moduleName, elementName) {
        ko.components.register(elementName, moduleName);
    });

    // var ethan = {
    //     viewModel: function(params) {
    //         // Data: value is either null, 'like', or 'dislike'
    //         this.chosenValue = params.value;

    //         // Behaviors
    //         this.like = function() { this.chosenValue('like'); }.bind(this);
    //         this.dislike = function() { this.chosenValue('dislike'); }.bind(this);
    //     },
    //     template:
    //     '<div class="like-or-dislike" data-bind="visible: !chosenValue()">\
    //         <button data-bind="click: like">Like it</button>\
    //         <button data-bind="click: dislike">Dislike it</button>\
    //     </div>\
    //     <div class="result" data-bind="visible: chosenValue">\
    //         You <strong data-bind="text: chosenValue"></strong> it\
    //     </div>'
    // };

    // console.log(ethan);
    // console.log(keyValueList);

    // ko.components.register('key-value-list', keyValueList);

    $(function () {
        _.each(_.keys(components), function (elementName) {
            _.each($(elementName), function (el) {
                var $el = $(el);
                if (!($el.data('apply-bindings') === false)) {
                    $(el).koApplyBindings();
                }
            });
        });
    });

    return 1;
});
