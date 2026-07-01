import "commcarehq";
import "hqwebapp/js/htmx_base";
import Alpine from "alpinejs";
import "hqwebapp/js/alpinejs/directives/datepicker";
import initialPageData from "hqwebapp/js/initial_page_data";

// Input-slot type sentinels. These MUST stay in sync with the constants in
// corehq/apps/case_search/endpoint_capability.py (INPUT_TYPE_CHOICE,
// INPUT_TYPE_MATCH_FIELD). The capability metadata is the contract that drives
// both this UI and backend query validation, so a mismatch silently diverges
// the two.
const SLOT_TYPE_CHOICE = "choice";
const SLOT_TYPE_MATCH_FIELD = "match_field";

Alpine.data("endpointForm", () => {
    return {
        name: initialPageData.get("initial_name"),
        targetType: initialPageData.get("initial_target_type"),
        targetCasetype: initialPageData.get("initial_case_type"),
        parameters: initialPageData.get("initial_parameters") || [],
        testParamValues: {},
        query: initialPageData.get("initial_query"),
        capability: initialPageData.get("capability"),
        _nextId: 1,
        // Exposed so condition_row.html can compare against the sentinel rather
        // than re-typing the "choice" literal.
        slotTypeChoice: SLOT_TYPE_CHOICE,

        get currentFields() {
            return this.capability.case_types[this.targetCasetype] || {};
        },

        getFieldDef(fieldName) {
            return this.currentFields[fieldName] || null;
        },

        getOperationsForField(fieldName) {
            const f = this.getFieldDef(fieldName);
            return f ? f.operations : [];
        },

        getInputSchemaForOperation(node) {
            const operation = node.operator;
            const inputs = this.capability.operator_input_schemas[operation] || [];
            return inputs.map(input =>
                input.type === SLOT_TYPE_MATCH_FIELD
                    ? { ...input, type: this.getFieldType(node.field) }
                    : input,
            );
        },

        getFieldType(fieldName) {
            const f = this.getFieldDef(fieldName);
            return f ? f.type : "";
        },

        typeIconClass(type) {
            return (
                {
                    text: "fa-solid fa-font",
                    number: "fa-solid fa-hashtag",
                    date: "fa-solid fa-calendar-days",
                    datetime: "fa-solid fa-calendar-days",
                    select: "fa-solid fa-list",
                    geopoint: "fa-solid fa-location-dot",
                }[type] || "fa-solid fa-circle"
            );
        },

        initializeIds(node) {
            node._id = this._nextId++;
            if (node.children) {
                node.children.forEach((child) => this.initializeIds(child));
            }
        },

        // The stored spec and builder state share the same shape, so the only
        // adjustment needed is at the root: the builder always renders a
        // group, so wrap a bare-component or empty/legacy root in an `all`
        // group.
        normalizeRoot(node) {
            if (node && ["all", "any", "none"].includes(node.type)) {
                return node;
            }
            if (node && node.type === "component") {
                return { type: "all", children: [node] };
            }
            return { type: "all", children: (node && node.children) || [] };
        },

        init() {
            this.query = this.normalizeRoot(this.query);
            this.initializeIds(this.query);
        },

        onCasetypeChange() {
            this.query = { type: "all", children: [] };
        },

        addParameter() {
            this.parameters.push({ name: "", type: "text"});
        },

        removeParameter(idx) {
            this.parameters.splice(idx, 1);
        },

        getParametersOfType(fieldType) {
            return this.parameters.filter(param => param.type === fieldType).map(param => param.name);
        },

        _newCondition() {
            return {
                _id: this._nextId++,
                type: "component",
                field: "",
                operator: "",
                inputs: {},
            };
        },

        addCondition(group) {
            if (!group.children) {
                group.children = [];
            }
            group.children.push(this._newCondition());
        },

        addGroup(parentGroup, type) {
            if (!parentGroup.children) {
                parentGroup.children = [];
            }
            parentGroup.children.push({
                _id: this._nextId++,
                type: type,
                children: [this._newCondition()],
            });
        },

        removeNode(parentGroup, idx) {
            parentGroup.children.splice(idx, 1);
        },

        onFieldChange(node) {
            node.operator = "";
            node.inputs = {};
        },

        onOperatorChange(node) {
            const schema = this.getInputSchemaForOperation(node);
            if (schema.every((slot) => slot.name in (node.inputs || {}))) {
                return;
            }
            node.inputs = {};
            for (const slot of schema) {
                node.inputs[slot.name] = this._defaultInputForSlot(slot);
            }
        },

        _defaultInputForSlot(slot) {
            // Choice slots are constant-only; default to the first valid option
            // so the dropdown is never blank (which would fail validation).
            if (slot.type === SLOT_TYPE_CHOICE) {
                return { type: "constant", value: (slot.options || [])[0] || "" };
            }
            return { type: "constant", value: "" };
        },

        getInputValue(node, slotName) {
            if (!node.inputs[slotName]) {
                node.inputs[slotName] = { type: "constant", value: "" };
            }
            return node.inputs[slotName];
        },

        setInputType(node, slotName, valueType) {
            const current = node.inputs[slotName] || {};
            if (valueType === "constant") {
                node.inputs[slotName] = {
                    type: "constant",
                    value: current.value || "",
                };
            } else if (valueType === "parameter") {
                node.inputs[slotName] = {
                    type: "parameter",
                    value: "",
                };
            }
        },

        // Strip Alpine-only `_id` keys so the persisted query JSON stays clean.
        stripIds(node) {
            if (Array.isArray(node)) {
                return node.map((n) => this.stripIds(n));
            }
            if (node && typeof node === "object") {
                const out = {};
                for (const [key, value] of Object.entries(node)) {
                    if (key === "_id") {
                        continue;
                    }
                    out[key] = this.stripIds(value);
                }
                return out;
            }
            return node;
        },

        // Builder state and the stored spec share the same shape, so emitting
        // the spec is just dropping the Alpine-only `_id` keys.
        strippedQuery() {
            return this.stripIds(this.query);
        },
    };
});

Alpine.start();
