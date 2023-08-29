hqDefine("hqwebapp/js/bootstrap3/knockout_bindings.ko", [
    'jquery',
    'underscore',
    'knockout',
    'jquery-ui/ui/widgets/sortable',
], function (
    $,
    _,
    ko
) {
    // Need this due to https://github.com/knockout/knockout/pull/2324
    // so that ko.bindingHandlers.foreach.update works properly
    ko.options.foreachHidesDestroyed = true;


    ko.bindingHandlers.hqbSubmitReady = {
        update: function (element, valueAccessor) {
            var value = (valueAccessor()) ? valueAccessor()() : null;
            if (value)
                $(element).addClass("btn-primary").removeClass("disabled");
            else
                $(element).addClass("disabled").removeClass("btn-primary");
        },
    };

    ko.bindingHandlers.fadeVisible = {
        // from knockout.js examples
        init: function (element, valueAccessor) {
            var value = valueAccessor();
            $(element).toggle(ko.utils.unwrapObservable(value));
        },
        update: function (element, valueAccessor) {
            var value = valueAccessor();
            ko.utils.unwrapObservable(value) ? $(element).fadeIn() : $(element).fadeOut();
        },
    };

    ko.bindingHandlers.fadeVisibleInOnly = {
        // from knockout.js examples
        init: function (element, valueAccessor) {
            var value = valueAccessor();
            $(element).toggle(ko.utils.unwrapObservable(value));
        },
        update: function (element, valueAccessor) {
            var value = valueAccessor();
            ko.utils.unwrapObservable(value) ? $(element).fadeIn() : $(element).hide();
        },
    };

    ko.bindingHandlers.langcode = {
        init: function (element, valueAccessor, allBindings) {
            var originalValue = ko.utils.unwrapObservable(valueAccessor());
            ko.bindingHandlers.value.init(element, valueAccessor, function () {
                var valueUpdate = allBindings.get('valueUpdate') || [];
                if (typeof valueUpdate === 'string') {
                    valueUpdate = [valueUpdate];
                }
                valueUpdate.push('autocompletechange');
                valueUpdate.push('autocompleteclose');
                return {
                    get: function (key) {
                        if (key === 'valueUpdate') {
                            return valueUpdate;
                        } else {
                            return allBindings.get(key);
                        }
                    },
                    has: function (key) {
                        if (key === 'valueUpdate') {
                            return true;
                        } else {
                            return allBindings.has(key);
                        }
                    },
                };
            }());
            $(element).langcodes(originalValue);
        },
        update: ko.bindingHandlers.value.update,
    };

    ko.bindingHandlers.sortable = {
        updateSortableList: function (itemList) {
            _(itemList()).each(function (item, index) {
                if (item._sortableOrder === undefined) {
                    item._sortableOrder = ko.observable(index);
                } else {
                    item._sortableOrder(index);
                }
            });
        },
        getList: function (valueAccessor) {
            /* this function's logic follows that of ko.bindingHandlers.foreach.makeTemplateValueAccessor */
            var modelValue = valueAccessor(),
                unwrappedValue = ko.utils.peekObservable(modelValue);
            if ((!unwrappedValue) || typeof unwrappedValue.length === "number") {
                return modelValue;
            } else {
                return unwrappedValue['data'];
            }
        },
        init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            // based on http://www.knockmeout.net/2011/05/dragging-dropping-and-sorting-with.html
            // note: although by this point we've deviated from that solution quite a bit
            var list = ko.bindingHandlers.sortable.getList(valueAccessor);
            var forceUpdate = function () {
                ko.bindingHandlers.sortable.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
            };
            list.subscribe(forceUpdate);
            $(element).sortable({
                handle: '.sortable-handle',
                helper: function (event, element) {
                    // Use a helper element attached directly to body to get
                    // around any overflow styling in the list's ancestors
                    return element.clone().appendTo("body");
                },
                update: function (event, ui) {
                    var parent = ui.item.parent(),
                        oldPosition = ui.item.data('order');
                    if (oldPosition === undefined) {
                        console.warn(
                            "NOT UPDATING THE SORT OF THE ACTUAL LIST! " +
                            "Did you forget to add `attr: {'data-order': _sortableOrder}` " +
                            "to the data-bind attribute of your main sorting " +
                            "element?"
                        );
                        return;
                    }
                    oldPosition = parseInt(oldPosition);
                    var newPosition = ko.utils.arrayIndexOf(parent.children(), ui.item.get(0)),
                        item = list()[oldPosition];

                    if (item === undefined) {
                        forceUpdate();
                        console.warn('Fetched an undefined item. Check your code.');
                        return;
                    }

                    if (item !== undefined) {
                        //remove the item and add it back in the right spot
                        if (newPosition >= 0) {

                            var newList = _.without(list(), item);
                            newList.splice(newPosition, 0, item);
                            list(newList);

                            // Knockout 2.3 fix: refresh all of the `data-order`s
                            // this is an O(n) operation, so if experiencing slowness
                            // start here
                            parent.children().each(function (i) {
                                $(this).data('order', i);
                            });
                        }
                    }
                },
            });
            return ko.bindingHandlers.foreach.init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
        update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            var list = ko.bindingHandlers.sortable.getList(valueAccessor);
            ko.bindingHandlers.sortable.updateSortableList(list);
            return ko.bindingHandlers.foreach.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
    };

    // Loosely based on https://jsfiddle.net/hQnWG/614/
    ko.bindingHandlers.multirow_sortable = {
        updateSortableList: function (itemList) {
            _(itemList()).each(function (item, index) {
                if (item._sortableOrder === undefined) {
                    item._sortableOrder = ko.observable(index);
                } else {
                    item._sortableOrder(index);
                }
            });
        },
        getList: function (valueAccessor) {
            /* this function's logic follows that of ko.bindingHandlers.foreach.makeTemplateValueAccessor */
            var modelValue = valueAccessor(),
                unwrappedValue = ko.utils.peekObservable(modelValue);  // Unwrap without setting a dependency here
            // If unwrappedValue is the array, pass in the wrapped value on its own
            // The value will be unwrapped and tracked within the template binding
            if ((!unwrappedValue) || _.isArray(unwrappedValue)) {
                return modelValue;
            } else {
                return unwrappedValue['data'];
            }
        },
        init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            var list = ko.bindingHandlers.multirow_sortable.getList(valueAccessor);
            var forceUpdate = function () {
                ko.bindingHandlers.multirow_sortable.update(
                    element, valueAccessor, allBindingsAccessor, viewModel, bindingContext
                );
            };
            list.subscribe(forceUpdate);

            $(element).on('click', '.send-to-top', function () {
                var row = getRowFromClickedElement($(this));
                setIgnoreClick(row);
                moveRowToIndex(row, 0);
            });

            $(element).on('click', '.send-to-bottom', function () {
                var row = getRowFromClickedElement($(this));
                setIgnoreClick(row);
                moveRowToIndex(row, list().length - 1);
            });

            $(element).on('click', '.export-table-checkbox', function () {
                var row = getRowFromClickedElement($(this));
                setIgnoreClick(row);
            });

            $(element).on('click', 'tr', function (e) {
                if ($(this).hasClass('ignore-click')) {
                    // Don't do anything if send-to-top, send-to-bottom, or select-for-export was clicked.
                    $(this).removeClass('ignore-click');
                } else if (e.ctrlKey || e.metaKey) {
                    // CTRL-clicking (CMD on OSX) toggles whether a row is highlighted for sorting.
                    var exportColumn = getExportColumnByRow($(this));
                    exportColumn.selectedForSort(!exportColumn.selectedForSort());
                    $(this).toggleClass('last-clicked').siblings().removeClass('last-clicked');
                } else if (e.shiftKey) {
                    // Clicking the shift key highlights all rows between the shift-clicked row
                    // and the previously clicked row.
                    var shiftSelectedIndex = getIndexFromRow($(this)),
                        lastClickedIndex = 0,
                        start = null,
                        end = null;
                    if ($('.last-clicked').length > 0) {
                        lastClickedIndex = getIndexFromRow($('.last-clicked').eq(0));
                    }
                    if (shiftSelectedIndex < lastClickedIndex) {
                        start = shiftSelectedIndex;
                        end = lastClickedIndex;
                    } else {
                        start = lastClickedIndex;
                        end = shiftSelectedIndex;
                    }
                    for (var i = start; i <= end; i++) {
                        list()[i].selectedForSort(true);
                    }
                } else {
                    // Clicking a row selects it for sorting and unselects all other rows.
                    $(this).addClass('last-clicked').siblings().removeClass('last-clicked');
                    for (var i = 0; i < list().length; i++) {
                        list()[i].selectedForSort(false);
                    }
                    getExportColumnByRow($(this)).selectedForSort(true);
                }
            });

            $(element).sortable({
                delay: 150,
                helper: function (e, item) {
                    // If the dragged row isn't selected for sorting, select it and unselect all other rows.
                    var exportColumn = getExportColumnByRow(item);
                    if (!exportColumn.selectedForSort()) {
                        for (var i = 0; i < list().length; i++) {
                            list()[i].selectedForSort(false);
                        }
                        exportColumn.selectedForSort(true);
                    }
                    // Only show the row that is clicked and dragged.
                    item.siblings('.selected-for-sort').hide();
                    return item;
                },
                // Drop the rows in the chosen location.
                // Maintain the original order of the selected rows.
                stop: function (e, ui) {
                    ui.item.after($('.selected-for-sort'));

                    var previousRow = ui.item.prev()[0],
                        previousIndex = null;
                    if (previousRow) {
                        previousIndex = parseInt(previousRow.attributes['data-order'].value);
                    }

                    var movedIndices = [];
                    $('.selected-for-sort').each(function (index, element) {
                        movedIndices.push(parseInt(element.attributes['data-order'].value));
                    });
                    movedIndices.sort();

                    var originalList = list.splice(0, list().length);

                    var insertDraggedElements = function () {
                        movedIndices.forEach(function (movedIndex) {
                            list.push(originalList[movedIndex]);
                        });
                    };

                    // Insert rows at top of list.
                    if (previousIndex === null) {
                        insertDraggedElements();
                    }
                    originalList.forEach(function (originalListElement, originalListIndex) {
                        // Other rows stay in their original order.
                        if (!movedIndices.includes(originalListIndex)) {
                            list.push(originalListElement);
                        }
                        // Insert rows in the middle of the list.
                        if (originalListIndex === previousIndex) {
                            insertDraggedElements();
                        }
                    });
                },
            });

            // Helper functions

            var getIndexFromRow = function (row) {
                return parseInt(row[0].attributes['data-order'].value);
            };

            var getExportColumnByRow = function (row) {
                return list()[getIndexFromRow(row)];
            };

            var setIgnoreClick = function (row) {
                row.addClass('ignore-click').siblings().removeClass('ignore-click');
            };

            var getRowFromClickedElement = function (element) {
                return element.closest('tr');
            };

            var moveRowToIndex = function (row, newIndex) {
                var oldIndex = getIndexFromRow(row);
                row.remove();
                var currentListItem = list.splice(oldIndex, 1)[0];
                list.splice(newIndex, 0, currentListItem);
            };

            return ko.bindingHandlers.foreach.init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
        update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            var list = ko.bindingHandlers.multirow_sortable.getList(valueAccessor);
            ko.bindingHandlers.multirow_sortable.updateSortableList(list);
            return ko.bindingHandlers.foreach.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
    };

    ko.bindingHandlers.modal = {
        init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            $(element).addClass('modal fade').modal({
                show: false,
            });
            //        ko.bindingHandlers['if'].init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
        update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            ko.bindingHandlers.visible.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
            var value = ko.utils.unwrapObservable(valueAccessor());
            //        ko.bindingHandlers['if'].update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
            if (value) {
                $(element).modal('show');
            } else {
                $(element).modal('hide');
            }
        },
    };

    ko.bindingHandlers.openModal = {
        /**
         * Create modal content in script element with ID:
         *  <script type="text/html" id="id-of-template">
         *      <!-- modal content -->
         *  </script>
         *
         * Use binding to open the modal on click:
         *  <a data-bind="openModal: 'id-of-template'">...</a>
         *
         * Alternately provide a condition to use to determine if the modal should open:
         *  <a data-bind="openModal: {templateId: 'id-of-template', if: isAllowed}">...</a>
         *
         */
        init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            let value = valueAccessor(),
                templateID = value,
                ifValue = true;
            if (typeof value === 'object') {
                templateID = value.templateId;
                ifValue = _.has(value, 'if') ? value.if : true;
            }
            var modal = $('<div></div>').addClass('modal fade').appendTo('body'),
                newValueAccessor = function () {
                    var clickAction = function () {
                        if (!ifValue) {
                            return;
                        }
                        ko.bindingHandlers.template.init(modal.get(0), function () {
                            return templateID;
                        }, allBindingsAccessor, viewModel, bindingContext);
                        ko.bindingHandlers.template.update(modal.get(0), function () {
                            return templateID;
                        }, allBindingsAccessor, viewModel, bindingContext);
                        modal.modal('show');
                    };
                    return clickAction;
                };
            ko.bindingHandlers.click.init(element, newValueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
    };

    ko.bindingHandlers.openRemoteModal = {
        init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            var modal = $('<div></div>').addClass('modal fade').appendTo('body'),
                newValueAccessor = function () {
                    var clickAction = function () {
                        modal.load($(element).data('ajaxSource'));
                        modal.modal('show');
                    };
                    return clickAction;
                };
            ko.bindingHandlers.click.init(element, newValueAccessor, allBindingsAccessor, viewModel, bindingContext);
        },
        update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            $(element).data('ajaxSource', ko.utils.unwrapObservable(valueAccessor()));
        },
    };

    ko.bindingHandlers.slideVisible = {
        'update': function (element, valueAccessor) {
            var value = ko.utils.unwrapObservable(valueAccessor());
            if (value) {
                $(element).hide().slideDown();
            } else if (!value) {
                $(element).slideUp();
            }
        },
    };

    ko.bindingHandlers.bootstrapTabs = {
        init: function (element) {
            var tabLinkSelector = 'ul.nav > li > a';
            var activate = function () {
                var n = $(tabLinkSelector, element).index(this);
                $(tabLinkSelector, element).parents().removeClass('active');
                $(this).parent().addClass('active');
                $('.tab-pane', element).removeClass('active');
                $('.tab-pane:eq(' + n + ')', element).addClass('active');
            };
            $(element).on('click', tabLinkSelector, activate);
            // Wait for the rest of the element to be rendered before init'ing
            // (bit of a race condition)
            setTimeout(function () {
                $('ul.nav > li.active > a', element).each(activate);
            }, 0);
        },
    };

    ko.bindingHandlers.optstr = {
        /*
            I find this often to be nicer than the built-in 'options' bindingHandler
            optstr: [{label: 'Yes', value: true},  {label: 'No', value: false}]
            optstrValue: 'value' (default)
            optstrText: 'label' (default)
            value: (ko.observable)
         */
        update: function (element, valueAccessor, allBindings) {
            var optionObjects = ko.utils.unwrapObservable(valueAccessor());
            var optstrValue = allBindings.get('optstrValue') || 'value';
            var optstrText = allBindings.get('optstrText') || 'label';
            var optionStrings = ko.utils.arrayMap(optionObjects, function (o) {
                return o[optstrValue];
            });
            var optionsText = function (optionString) {
                for (var i = 0; i < optionObjects.length; i++) {
                    if (optionObjects[i][optstrValue] === optionString) {
                        if (typeof optstrText === 'string') {
                            return optionObjects[i][optstrText];
                        } else {
                            return optstrText(optionObjects[i]);
                        }
                    }
                }
            };

            return ko.bindingHandlers.options.update(element, function () {
                return optionStrings;
            }, {
                get: function (key) {
                    if (key === 'optionsText') {
                        return optionsText;
                    } else {
                        return allBindings.get(key);
                    }
                },
                has: function (key) {
                    if (key === 'optionsText') {
                        return true;
                    } else {
                        return allBindings.has(key);
                    }
                },
            });
        },
    };

    ko.bindingHandlers.valueDefault = {
        init: ko.bindingHandlers.value.init,
        update: function (element, valueAccessor, allBindingsAccessor) {
            var value = valueAccessor();
            if (!value()) {
                value(ko.utils.unwrapObservable(allBindingsAccessor()['default']));
            }
            return ko.bindingHandlers.value.update(element, valueAccessor);
        },
    };

    ko.bindingHandlers.multiTypeahead = {
        init: function (element, valueAccessor) {
            var contacts = valueAccessor();
            $(element).multiTypeahead({
                source: contacts,
            }).focus();
        },
    };

    /**
     * A custom knockout binding that replaces the element's contents with a jquery
     * element.
     * @type {{update: update}}
     */
    ko.bindingHandlers.jqueryElement = {
        init: function () {
            // This excludes this element from ko.applyBindings
            // which means that whatever controls that element
            // is free to use its own knockout without conflicting
            return {
                controlsDescendantBindings: true,
            };
        },
        update: function (element, valueAccessor, allBindings, viewModel, bindingContext) {
            $(element).empty();
            $(element).append(ko.unwrap(valueAccessor()));
        },
    };

    ko.bindingHandlers.__copyPasteSharedInit = function () {
        var offScreen = {
            top: -10000,
            left: -10000,
        };
        var hiddenTextarea = $('<textarea></textarea>').css({
            position: 'absolute',
            width: 0,
            height: 0,
        }).css(offScreen).appendTo('body');
        var focusTextarea = function ($element, value) {
            hiddenTextarea.css({
                top: $element.offset().top,
            });
            hiddenTextarea.val(value);
            hiddenTextarea.focus();
            hiddenTextarea.select();
        };
        var unfocusTextarea = function ($element) {
            $element.focus();
            return hiddenTextarea.val();
        };
        // Firefox only fires copy/paste when it thinks it's appropriate
        // Chrome doesn't fire copy/paste after key down has changed the focus
        // So we need implement both copy/paste as catching keystrokes Ctrl+C/V
        $(document).on('copy paste keydown', function (e) {
            var $element, callback;
            if (e.type === 'copy' || e.metaKey && String.fromCharCode(e.keyCode) === 'C') {
                $element = $(':focus');
                callback = $element.data('copyCallback');
                if (callback) {
                    focusTextarea($element, callback());
                    setTimeout(function () {
                        unfocusTextarea($element);
                    }, 0);
                }
            } else if (e.type === 'paste' || e.metaKey && String.fromCharCode(e.keyCode) === 'V') {
                $element = $(':focus');
                callback = $element.data('pasteCallback');
                if (callback) {
                    focusTextarea($element);
                    setTimeout(function () {
                        var pasteValue = unfocusTextarea($element);
                        // part of the above hack
                        // on chrome this gets called twice,
                        // the first time with a blank value
                        if (pasteValue) {
                            callback(pasteValue);
                        }
                    }, 0);
                }
            }
        });

        // only ever call this function once
        ko.bindingHandlers.__copyPasteSharedInit = function () {};
    };

    ko.bindingHandlers.copy = {
        init: function (element, valueAccessor) {
            ko.bindingHandlers.__copyPasteSharedInit();
            $(element).data('copyCallback', valueAccessor());
        },
    };

    ko.bindingHandlers.paste = {
        init: function (element, valueAccessor) {
            ko.bindingHandlers.__copyPasteSharedInit();
            var callback = valueAccessor();
            $(element).data('pasteCallback', valueAccessor());
        },
    };

    /**
     * Normally, bindings can't overlap, this binding allows them to. For example:
     *
     * <div id="a">
     *     <div data-bind="stopBinding: true">
     *          <div id="b">
     *              <p>foo</p>
     *          </div>
     *     </div>
     * </div>
     *
     * $('#a').koApplyBindings({});
     * $('#b').koApplyBindings({});
     *
     *
     * Taken straight from:
     * http://www.knockmeout.net/2012/05/quick-tip-skip-binding.html
     */
    ko.bindingHandlers.stopBinding = {
        init: function () {
            return {
                controlsDescendantBindings: true,
            };
        },
    };
    ko.virtualElements.allowedBindings.stopBinding = true;

    ko.bindingHandlers.popover = {
        update: function (element, valueAccessor) {
            var options = ko.utils.unwrapObservable(valueAccessor());
            if (options.html) {
                options.sanitize = false;
            }
            if (options.title || options.content) { // don't show empty popovers
                $(element).popover(options);
            }
        },
    };

    ko.bindingHandlers.initializeValue = {
        init: function (element, valueAccessor) {
            valueAccessor()(element.getAttribute('value'));
        },
        update: function (element, valueAccessor) {
            var value = valueAccessor();
            element.setAttribute('value', ko.utils.unwrapObservable(value));
        },
    };

    ko.bindingHandlers.bind_element = {
        init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            var field = valueAccessor() || '$e';
            if (viewModel[field]) {
                console.log('warning: element already bound');
                return;
            }
            viewModel[field] = element;
            if (viewModel.onBind) {
                viewModel.onBind(bindingContext);
            }
        },
    };

    ko.bindingHandlers.sortableList = {
        // Defines a knockout binding for the jquery UI sortable interaction which allows
        // reordering elements with a drag and drop interface
        // The element to be used to drag and drop must have a grip class defined
        // Optionally sortableListSelector can be defined as a selector that describes what items are sortable
        init: function (element, valueAccessor, allBindings) {
            var list = valueAccessor(),
                itemSelector = allBindings().sortableListSelector;

            $(element).sortable({
                handle: '.grip',
                cursor: 'move',
                update: function (event, ui) {
                    //retrieve our actual data item
                    var item = ko.dataFor(ui.item.get(0));
                    //figure out its new position
                    var position = ko.utils.arrayIndexOf(ui.item.parent().children(), ui.item[0]);
                    //remove the item and add it back in the right spot
                    if (position >= 0) {
                        list.remove(item);
                        list.splice(position, 0, item);
                    }
                    ui.item.remove();
                },
            });
            if (itemSelector) {
                $(element).sortable("option", "items", itemSelector);
            }
        },
    };

    ko.bindingHandlers.onEnterKey = {
        // calls a function when the enter key is pressed on an input
        init: function (element, valueAccessor, allBindings, viewModel) {
            $(element).keypress(function (event) {
                if (event.key === "Enter" || event.keyCode === 13) {
                    valueAccessor()();
                    return false;
                }
                return true;
            });
        },
    };

    return 1;
});
