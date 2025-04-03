import $ from 'jquery';
import 'select2/dist/js/select2.full.min';
import Alpine from 'alpinejs';

import utils from 'hqwebapp/js/alpinejs/directives/select2';

/***
 * These directives are intended as alpine replacements for the knockout-based
 * select2 utilities in `reports/js/filters/select2s`.
 */

const _updateFormOnChange = (el) => {
    $(el).on('change', () => {
        const parentForm = el.form;
        if (parentForm) {
            parentForm.dispatchEvent(new CustomEvent('reportFilterUpdated', {
                el: el,
                name: el.name,
            }));
        }
    });
};

Alpine.directive('report-select2', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-report-select2-multi to your select element.
     *
     *      <select x-report-select2="{% html_attr config %}"></select>
     *
     *      See `CaseStatusPinnedFilter` for an example of how to format the config
     *      The report-select2 config is very specific to the `filter_context` of that class.
     *
     */
    const config = (expression) ? JSON.parse(expression) : {};
    if (config.pagination.enabled) {
        _createPaginatedSelect2(el, config);
    } else {
        _createSelect2(el, config);
    }

    _updateFormOnChange(el);

    cleanup(() => {
        utils.select2Cleanup(el);
    });
});

Alpine.directive('report-select2-multi', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-report-select2-multi to your select element.
     *
     *      <select x-report-select2-multi="{% html_attr config %}"></select>
     *
     *      See `CaseOwnersPinnedFilter` for an example of how to format the config.
     *      The report-select2 config is very specific to the `filter_context` of that class.
     *
     */
    const config = (expression) ? JSON.parse(expression) : {};
    if (config.endpoint !== undefined) {
        _createAsyncSelect2Multi(el, config);
    } else {
        _createSelect2Multi(el, config);
    }

    _updateFormOnChange(el);

    cleanup(() => {
        utils.select2Cleanup(el);
    });
});

document.body.addEventListener('htmx:afterSettle', (event) => {
    /**
     * This fixes a bug for forms using x-select2 after submitting, validating, and swapping back into
     * the DOM using HTMX.
     *
     * Without this fix, you will get the **visible** <select> stacked on top of the select2, and no
     * validation classes are passed to the select2.
     */
    utils.fixSelect2htmx(event, '[x-report-select2]');
    utils.fixSelect2htmx(event, '[x-report-select2-multi]');
});

const _createSelect2 = (el, config) => {
    el.appendChild(new Option(config.select.default_text, ''));
    config.select.options.forEach(option => {
        el.appendChild(new Option(option.text, option.val));
    });
    $(el).select2({
        clearable: true,
    });
    if (config.select.selected) {
        $(el).val(config.select.selected);
        $(el).trigger('change.select2');
    }
};

const _createPaginatedSelect2 = (el, config) => {
    $(el).select2({
        ajax: {
            url: config.pagination.url,
            type: 'POST',
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return {
                    q: params.term,
                    page: params.page,
                    handler: config.pagination.handler,
                    action: config.pagination.action,
                };
            },
            processResults: function (data, params) {
                params.page = params.page || 1;
                if (data.success) {
                    var limit = data.limit;
                    var hasMore = (params.page * limit) < data.total;
                    return {
                        results: data.items,
                        pagination: {
                            more: hasMore,
                        },
                    };
                }
            },
        },
        allowClear: true,
        placeholder: config.select.default_text || ' ',
    });
};

const _createAsyncSelect2Multi = (el, config) => {
    const pageLimit = 10;
    config.select.options.forEach(option => {
        el.appendChild(new Option(option.text, option.val));
    });
    $(el).select2({
        placeholder: config.select.placeholder,
        ajax: {
            url: config.endpoint,
            dataType: 'json',
            delay: 500,
            data: function (params) {
                return {
                    q: params.term,
                    page_limit: pageLimit,
                    page: params.page,
                };
            },
            processResults: function (data, params) {
                params.page = params.page || 1;
                const more = data.more || data.pagination && data.pagination.more || (params.page * pageLimit) < data.total;
                return {
                    results: data.results,
                    pagination: {
                        more: more,
                    },
                };
            },
        },
        multiple: true,
    });
    if (config.select.selected && config.select.selected.length) {
        config.select.selected.forEach(item => {
            // NOTE: `id` used instead of `value` (above) due to inconsistencies in the original report filter
            // eventually, we should make sure everything is consistent
            el.appendChild(new Option(item.text, item.id));
        });
        $(el).trigger({
            type: 'select2:select',
            params: {
                data: config.select.selected,
            },
        });
        $(el).val(config.select.selected.map(item => item.id));
        $(el).trigger('change.select2');
    }
};

const _createSelect2Multi = (el, config) => {
    config.select.options.forEach(option => {
        el.appendChild(new Option(option.text, option.value));
    });
    $(el).select2({
        multiple: true,
    });
};
