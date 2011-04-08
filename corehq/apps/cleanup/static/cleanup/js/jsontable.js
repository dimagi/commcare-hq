var JsonTable, JsonRow;
(function($) {
    var cmp = (function(f){
        return (function(a,b){
            var f_a = f(a);
            var f_b = f(b);
            if(f_a > f_b) return 1;
            else if(f_a == f_b) return 0;
            else return -1;
        });
    });


    JsonRow = (function(){
        function JsonRow(options){
            var self = this;
            this.data = options.data;
            this.order = options.order || {};
            this._render = options.render || {};
            this.table = options.table;
            this.cells = [];
            this._getId = options.getId;
            for(var key in this.data) {
                this.cells.push({key: key, value: this.data[key]});
            }
            this.cells.sort(cmp(function(cell){
                return self.order.indexOf(cell.key);
            }));
        }
        JsonRow.prototype = {
            render: function(options){
                if(!options) {options = {copy: false};}
                var copy = options.copy;
                var self = this;
                var $row = $("<tr></tr>");
                if(!copy){
                    $row.append($("<td><input type='checkbox' /></td>"));
                    this.$checkbox = $("[type='checkbox']", $row);
                    this.$checkbox.change(function(){
                        self.table.setSelected(self, self.isSelected());
                    });
                }
                for(var i in this.cells) {
                    $row.append("<td>" + this.renderCell(this.cells[i]) + "</td>");
                }


                return $row;
            },
            isSelected: function(){
               return this.$checkbox.is(":checked");
            },
            renderCell: function(cell) {
                if(cell.key in this._render) {
                    return this._render[cell.key](cell.value);
                } else {
                    return cell.value;
                }
            },
            getId: function() {
                return this._getId(this.data);
            }
        };
        return JsonRow;
    })();

    JsonTable = (function(){
        function JsonTable(options){
            var self = this;
            this.data = options.data;
            this.order = options.order || [];
            this._render = options.render || {};
            this.$element = $(options.element);
            this.$selected = $(options.selected);
            this.headers = [];
            this.rows = [];
            this.selected = {};

            for(var h in this.data[0]) {
                this.headers.push(h);
            }
            this.headers.sort(cmp(function(h){
                return self.order.indexOf(h);
            }));
            for(var i in this.data) {
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
                var $table = $("<table></table>");
                var $hrow = $("<tr><th>Select</th></tr>");
                for(var h in this.headers) {
                    $hrow.append($("</th><th>" + this.headers[h] + "</th>"));
                }
                $table.append($hrow);
                for(var i in this.rows) {
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
                var selected = [];
                for(var id in this.selected) {
                    selected.push(this.selected[id].data);
                }
                return selected;
            }
        };
        return JsonTable;
    })();

})(jQuery);