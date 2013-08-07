/*globals $ */
var JsonTable, JsonRow;
(function() {
    JsonRow = (function(){
        function JsonRow(options){
            var self = this,
                key;
            this.data = options.data;
            this.order = options.order || {};
            this._render = options.render || {};
            this.table = options.table;
            this.cells = [];
            this._getId = options.getId;
            for(key in this.data) {
                if (this.data.hasOwnProperty(key)) {
                    this.cells.push({key: key, value: this.data[key]});
                }
            }
            this.cells.sortBy(function(){
                return self.order.indexOf(this.key);
            });
        }
        JsonRow.prototype = {
            render: function(options){
                var copy,
                    self = this,
                    $row = $("<tr></tr>"),
                    i;
                options = options || {copy: false};
                copy = options.copy;
                if(!copy){
                    $row.append($("<td><input type='checkbox' /></td>"));
                    this.$checkbox = $("[type='checkbox']", $row);
                    this.$checkbox.change(function(){
                        self.table.setSelected(self, self.isSelected());
                    });
                }
                for(i = 0; i < this.cells.length; i += 1) {
                    $row.append("<td>" + this.renderCell(this.cells[i]) + "</td>");
                }


                return $row;
            },
            isSelected: function(){
               return this.$checkbox.is(":checked");
            },
            renderCell: function(cell) {
                if(this._render.hasOwnProperty(cell.key)) {
                    return this._render[cell.key].apply(this.data, [cell.value]);
                } else {
                    return cell.value;
                }
            },
            getId: function() {
                return this._getId(this.data);
            }
        };
        return JsonRow;
    }());

    JsonTable = (function(){
        function JsonTable(options){
            var self = this,
                h, i;
            this.data = options.data;
            this.order = options.order || [];
            this._render = options.render || {};
            this.$element = $(options.element);
            this.headers = [];
            this.rows = [];
            this.selected = {};

            for(h in this.data[0]) {
                if (this.data[0].hasOwnProperty(h)) {
                    this.headers.push(h);
                }
            }
            this.headers.sortBy(function(h){
                return self.order.indexOf(h);
            });

            for(i = 0; i < this.data.length; i += 1) {
                var row = new JsonRow({
                    data: this.data[i],
                    order: this.order,
                    render: this._render,
                    table: this,
                    getId: options.getId
                });
                this.rows.push(row);
            }
            this.refresh();
        }
        JsonTable.prototype = {
            render: function() {
                var $table = $("<table></table>"),
                    $hrow = $("<tr><th>Select</th></tr>"),
                    h, i;
                for(h = 0; h < this.headers.length; h += 1) {
                    $hrow.append($("</th><th>" + this.headers[h] + "</th>"));
                }
                $table.append($hrow);
                for(i = 0; i < this.rows.length; i += 1) {
                    $table.append(this.rows[i].render());
                }
                return $table;
            },
            refresh: function(){
                this.$element.html("");
                this.$element.append(this.render());
            },
            setSelected: function(row, isSelected) {
                if(isSelected) {
                    this.selected[row.getId()] = row;
                } else {
                    delete this.selected[row.getId()];
                }
                this.$element.trigger('change-selected');
            },
            getSelected: function(){
                var selected = [],
                    id;
                for(id in this.selected) {
                    if (this.selected.hasOwnProperty(id)) {
                        selected.push(this.selected[id].data);
                    }
                }
                return selected;
            }
        };
        return JsonTable;
    }());

}());