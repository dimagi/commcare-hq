import Alpine from 'alpinejs';

let nextId = 1;

function makeId() {
    return nextId++;
}

function makeGroup(operator) {
    return {_id: makeId(), type: 'group', operator: operator || 'and', children: []};
}

function makeTerm() {
    return {_id: makeId(), type: 'term', variable: '', operator: '', value_type: 'constant', value: ''};
}

/**
 * Generic query builder Alpine component.
 *
 * Configuration is received via a 'query-builder:config' CustomEvent on
 * `window` with `detail` containing:
 *   - `types`: array of {name, operators} where each operator is {name, has_value}
 *   - `variables`: array of {id, name, type} — used on the left side of conditions
 *   - `parameters`: array of {id, name} — available on the right side of conditions
 */
Alpine.data('queryBuilder', () => ({
    root: null,
    variables: [],
    parameters: [],
    types: [],

    init() {
        this.root = makeGroup('and');

        window.addEventListener('query-builder:config', (e) => {
            if (e.detail) {
                if (e.detail.variables) {
                    this.variables = e.detail.variables;
                }
                if (e.detail.parameters) {
                    this.parameters = e.detail.parameters;
                }
                if (e.detail.types) {
                    this.types = e.detail.types;
                }
            }
        });
    },

    addTerm(group) {
        group.children.push(makeTerm());
    },

    addGroup(parent) {
        parent.children.push(makeGroup('and'));
    },

    removeChild(parent, index) {
        parent.children.splice(index, 1);
    },

    getTypeForVariable(varId) {
        const variable = this.variables.find(v => v.id === varId);
        if (!variable) {
            return null;
        }
        return this.types.find(t => t.name === variable.type) || null;
    },

    getOperatorsForVariable(varId) {
        const type = this.getTypeForVariable(varId);
        if (!type) {
            return [];
        }
        return type.operators;
    },

    operatorHasValue(varId, opName) {
        const type = this.getTypeForVariable(varId);
        if (!type) {
            return false;
        }
        const op = type.operators.find(o => o.name === opName);
        return op ? op.has_value : false;
    },

    serializeNode(node) {
        if (node.type === 'group') {
            return {
                operator: node.operator,
                children: node.children.map(c => this.serializeNode(c)),
            };
        }
        const result = {variable: node.variable, operator: node.operator};
        if (this.operatorHasValue(node.variable, node.operator)) {
            result.value_type = node.value_type;
            result.value = node.value;
        }
        return result;
    },

    get serialized() {
        if (!this.root) {
            return '{}';
        }
        return JSON.stringify(this.serializeNode(this.root), null, 2);
    },
}));
