
define('css/css!../bower_components/jstree/dist/themes/default/style',[],function(){});
/*globals jQuery, define, module, exports, require, window, document, postMessage */
(function (factory) {
	"use strict";
	if (typeof define === 'function' && define.amd) {
		define('jquery.jstree',['jquery'], factory);
	}
	else if(typeof module !== 'undefined' && module.exports) {
		module.exports = factory(require('jquery'));
	}
	else {
		factory(jQuery);
	}
}(function ($, undefined) {
	"use strict";
/*!
 * jsTree 3.3.3
 * http://jstree.com/
 *
 * Copyright (c) 2014 Ivan Bozhanov (http://vakata.com)
 *
 * Licensed same as jquery - under the terms of the MIT License
 *   http://www.opensource.org/licenses/mit-license.php
 */
/*!
 * if using jslint please allow for the jQuery global and use following options:
 * jslint: loopfunc: true, browser: true, ass: true, bitwise: true, continue: true, nomen: true, plusplus: true, regexp: true, unparam: true, todo: true, white: true
 */
/*jshint -W083 */

	// prevent another load? maybe there is a better way?
	if($.jstree) {
		return;
	}

	/**
	 * ### jsTree core functionality
	 */

	// internal variables
	var instance_counter = 0,
		ccp_node = false,
		ccp_mode = false,
		ccp_inst = false,
		themes_loaded = [],
		src = $('script:last').attr('src'),
		document = window.document; // local variable is always faster to access then a global

	/**
	 * holds all jstree related functions and variables, including the actual class and methods to create, access and manipulate instances.
	 * @name $.jstree
	 */
	$.jstree = {
		/**
		 * specifies the jstree version in use
		 * @name $.jstree.version
		 */
		version : '3.3.3',
		/**
		 * holds all the default options used when creating new instances
		 * @name $.jstree.defaults
		 */
		defaults : {
			/**
			 * configure which plugins will be active on an instance. Should be an array of strings, where each element is a plugin name. The default is `[]`
			 * @name $.jstree.defaults.plugins
			 */
			plugins : []
		},
		/**
		 * stores all loaded jstree plugins (used internally)
		 * @name $.jstree.plugins
		 */
		plugins : {},
		path : src && src.indexOf('/') !== -1 ? src.replace(/\/[^\/]+$/,'') : '',
		idregex : /[\\:&!^|()\[\]<>@*'+~#";.,=\- \/${}%?`]/g,
		root : '#'
	};
	
	/**
	 * creates a jstree instance
	 * @name $.jstree.create(el [, options])
	 * @param {DOMElement|jQuery|String} el the element to create the instance on, can be jQuery extended or a selector
	 * @param {Object} options options for this instance (extends `$.jstree.defaults`)
	 * @return {jsTree} the new instance
	 */
	$.jstree.create = function (el, options) {
		var tmp = new $.jstree.core(++instance_counter),
			opt = options;
		options = $.extend(true, {}, $.jstree.defaults, options);
		if(opt && opt.plugins) {
			options.plugins = opt.plugins;
		}
		$.each(options.plugins, function (i, k) {
			if(i !== 'core') {
				tmp = tmp.plugin(k, options[k]);
			}
		});
		$(el).data('jstree', tmp);
		tmp.init(el, options);
		return tmp;
	};
	/**
	 * remove all traces of jstree from the DOM and destroy all instances
	 * @name $.jstree.destroy()
	 */
	$.jstree.destroy = function () {
		$('.jstree:jstree').jstree('destroy');
		$(document).off('.jstree');
	};
	/**
	 * the jstree class constructor, used only internally
	 * @private
	 * @name $.jstree.core(id)
	 * @param {Number} id this instance's index
	 */
	$.jstree.core = function (id) {
		this._id = id;
		this._cnt = 0;
		this._wrk = null;
		this._data = {
			core : {
				themes : {
					name : false,
					dots : false,
					icons : false,
					ellipsis : false
				},
				selected : [],
				last_error : {},
				working : false,
				worker_queue : [],
				focused : null
			}
		};
	};
	/**
	 * get a reference to an existing instance
	 *
	 * __Examples__
	 *
	 *	// provided a container with an ID of "tree", and a nested node with an ID of "branch"
	 *	// all of there will return the same instance
	 *	$.jstree.reference('tree');
	 *	$.jstree.reference('#tree');
	 *	$.jstree.reference($('#tree'));
	 *	$.jstree.reference(document.getElementByID('tree'));
	 *	$.jstree.reference('branch');
	 *	$.jstree.reference('#branch');
	 *	$.jstree.reference($('#branch'));
	 *	$.jstree.reference(document.getElementByID('branch'));
	 *
	 * @name $.jstree.reference(needle)
	 * @param {DOMElement|jQuery|String} needle
	 * @return {jsTree|null} the instance or `null` if not found
	 */
	$.jstree.reference = function (needle) {
		var tmp = null,
			obj = null;
		if(needle && needle.id && (!needle.tagName || !needle.nodeType)) { needle = needle.id; }

		if(!obj || !obj.length) {
			try { obj = $(needle); } catch (ignore) { }
		}
		if(!obj || !obj.length) {
			try { obj = $('#' + needle.replace($.jstree.idregex,'\\$&')); } catch (ignore) { }
		}
		if(obj && obj.length && (obj = obj.closest('.jstree')).length && (obj = obj.data('jstree'))) {
			tmp = obj;
		}
		else {
			$('.jstree').each(function () {
				var inst = $(this).data('jstree');
				if(inst && inst._model.data[needle]) {
					tmp = inst;
					return false;
				}
			});
		}
		return tmp;
	};
	/**
	 * Create an instance, get an instance or invoke a command on a instance.
	 *
	 * If there is no instance associated with the current node a new one is created and `arg` is used to extend `$.jstree.defaults` for this new instance. There would be no return value (chaining is not broken).
	 *
	 * If there is an existing instance and `arg` is a string the command specified by `arg` is executed on the instance, with any additional arguments passed to the function. If the function returns a value it will be returned (chaining could break depending on function).
	 *
	 * If there is an existing instance and `arg` is not a string the instance itself is returned (similar to `$.jstree.reference`).
	 *
	 * In any other case - nothing is returned and chaining is not broken.
	 *
	 * __Examples__
	 *
	 *	$('#tree1').jstree(); // creates an instance
	 *	$('#tree2').jstree({ plugins : [] }); // create an instance with some options
	 *	$('#tree1').jstree('open_node', '#branch_1'); // call a method on an existing instance, passing additional arguments
	 *	$('#tree2').jstree(); // get an existing instance (or create an instance)
	 *	$('#tree2').jstree(true); // get an existing instance (will not create new instance)
	 *	$('#branch_1').jstree().select_node('#branch_1'); // get an instance (using a nested element and call a method)
	 *
	 * @name $().jstree([arg])
	 * @param {String|Object} arg
	 * @return {Mixed}
	 */
	$.fn.jstree = function (arg) {
		// check for string argument
		var is_method	= (typeof arg === 'string'),
			args		= Array.prototype.slice.call(arguments, 1),
			result		= null;
		if(arg === true && !this.length) { return false; }
		this.each(function () {
			// get the instance (if there is one) and method (if it exists)
			var instance = $.jstree.reference(this),
				method = is_method && instance ? instance[arg] : null;
			// if calling a method, and method is available - execute on the instance
			result = is_method && method ?
				method.apply(instance, args) :
				null;
			// if there is no instance and no method is being called - create one
			if(!instance && !is_method && (arg === undefined || $.isPlainObject(arg))) {
				$.jstree.create(this, arg);
			}
			// if there is an instance and no method is called - return the instance
			if( (instance && !is_method) || arg === true ) {
				result = instance || false;
			}
			// if there was a method call which returned a result - break and return the value
			if(result !== null && result !== undefined) {
				return false;
			}
		});
		// if there was a method call with a valid return value - return that, otherwise continue the chain
		return result !== null && result !== undefined ?
			result : this;
	};
	/**
	 * used to find elements containing an instance
	 *
	 * __Examples__
	 *
	 *	$('div:jstree').each(function () {
	 *		$(this).jstree('destroy');
	 *	});
	 *
	 * @name $(':jstree')
	 * @return {jQuery}
	 */
	$.expr.pseudos.jstree = $.expr.createPseudo(function(search) {
		return function(a) {
			return $(a).hasClass('jstree') &&
				$(a).data('jstree') !== undefined;
		};
	});

	/**
	 * stores all defaults for the core
	 * @name $.jstree.defaults.core
	 */
	$.jstree.defaults.core = {
		/**
		 * data configuration
		 *
		 * If left as `false` the HTML inside the jstree container element is used to populate the tree (that should be an unordered list with list items).
		 *
		 * You can also pass in a HTML string or a JSON array here.
		 *
		 * It is possible to pass in a standard jQuery-like AJAX config and jstree will automatically determine if the response is JSON or HTML and use that to populate the tree.
		 * In addition to the standard jQuery ajax options here you can suppy functions for `data` and `url`, the functions will be run in the current instance's scope and a param will be passed indicating which node is being loaded, the return value of those functions will be used.
		 *
		 * The last option is to specify a function, that function will receive the node being loaded as argument and a second param which is a function which should be called with the result.
		 *
		 * __Examples__
		 *
		 *	// AJAX
		 *	$('#tree').jstree({
		 *		'core' : {
		 *			'data' : {
		 *				'url' : '/get/children/',
		 *				'data' : function (node) {
		 *					return { 'id' : node.id };
		 *				}
		 *			}
		 *		});
		 *
		 *	// direct data
		 *	$('#tree').jstree({
		 *		'core' : {
		 *			'data' : [
		 *				'Simple root node',
		 *				{
		 *					'id' : 'node_2',
		 *					'text' : 'Root node with options',
		 *					'state' : { 'opened' : true, 'selected' : true },
		 *					'children' : [ { 'text' : 'Child 1' }, 'Child 2']
		 *				}
		 *			]
		 *		}
		 *	});
		 *
		 *	// function
		 *	$('#tree').jstree({
		 *		'core' : {
		 *			'data' : function (obj, callback) {
		 *				callback.call(this, ['Root 1', 'Root 2']);
		 *			}
		 *		});
		 *
		 * @name $.jstree.defaults.core.data
		 */
		data			: false,
		/**
		 * configure the various strings used throughout the tree
		 *
		 * You can use an object where the key is the string you need to replace and the value is your replacement.
		 * Another option is to specify a function which will be called with an argument of the needed string and should return the replacement.
		 * If left as `false` no replacement is made.
		 *
		 * __Examples__
		 *
		 *	$('#tree').jstree({
		 *		'core' : {
		 *			'strings' : {
		 *				'Loading ...' : 'Please wait ...'
		 *			}
		 *		}
		 *	});
		 *
		 * @name $.jstree.defaults.core.strings
		 */
		strings			: false,
		/**
		 * determines what happens when a user tries to modify the structure of the tree
		 * If left as `false` all operations like create, rename, delete, move or copy are prevented.
		 * You can set this to `true` to allow all interactions or use a function to have better control.
		 *
		 * __Examples__
		 *
		 *	$('#tree').jstree({
		 *		'core' : {
		 *			'check_callback' : function (operation, node, node_parent, node_position, more) {
		 *				// operation can be 'create_node', 'rename_node', 'delete_node', 'move_node' or 'copy_node'
		 *				// in case of 'rename_node' node_position is filled with the new node name
		 *				return operation === 'rename_node' ? true : false;
		 *			}
		 *		}
		 *	});
		 *
		 * @name $.jstree.defaults.core.check_callback
		 */
		check_callback	: false,
		/**
		 * a callback called with a single object parameter in the instance's scope when something goes wrong (operation prevented, ajax failed, etc)
		 * @name $.jstree.defaults.core.error
		 */
		error			: $.noop,
		/**
		 * the open / close animation duration in milliseconds - set this to `false` to disable the animation (default is `200`)
		 * @name $.jstree.defaults.core.animation
		 */
		animation		: 200,
		/**
		 * a boolean indicating if multiple nodes can be selected
		 * @name $.jstree.defaults.core.multiple
		 */
		multiple		: true,
		/**
		 * theme configuration object
		 * @name $.jstree.defaults.core.themes
		 */
		themes			: {
			/**
			 * the name of the theme to use (if left as `false` the default theme is used)
			 * @name $.jstree.defaults.core.themes.name
			 */
			name			: false,
			/**
			 * the URL of the theme's CSS file, leave this as `false` if you have manually included the theme CSS (recommended). You can set this to `true` too which will try to autoload the theme.
			 * @name $.jstree.defaults.core.themes.url
			 */
			url				: false,
			/**
			 * the location of all jstree themes - only used if `url` is set to `true`
			 * @name $.jstree.defaults.core.themes.dir
			 */
			dir				: false,
			/**
			 * a boolean indicating if connecting dots are shown
			 * @name $.jstree.defaults.core.themes.dots
			 */
			dots			: true,
			/**
			 * a boolean indicating if node icons are shown
			 * @name $.jstree.defaults.core.themes.icons
			 */
			icons			: true,
			/**
			 * a boolean indicating if node ellipsis should be shown - this only works with a fixed with on the container
			 * @name $.jstree.defaults.core.themes.ellipsis
			 */
			ellipsis		: false,
			/**
			 * a boolean indicating if the tree background is striped
			 * @name $.jstree.defaults.core.themes.stripes
			 */
			stripes			: false,
			/**
			 * a string (or boolean `false`) specifying the theme variant to use (if the theme supports variants)
			 * @name $.jstree.defaults.core.themes.variant
			 */
			variant			: false,
			/**
			 * a boolean specifying if a reponsive version of the theme should kick in on smaller screens (if the theme supports it). Defaults to `false`.
			 * @name $.jstree.defaults.core.themes.responsive
			 */
			responsive		: false
		},
		/**
		 * if left as `true` all parents of all selected nodes will be opened once the tree loads (so that all selected nodes are visible to the user)
		 * @name $.jstree.defaults.core.expand_selected_onload
		 */
		expand_selected_onload : true,
		/**
		 * if left as `true` web workers will be used to parse incoming JSON data where possible, so that the UI will not be blocked by large requests. Workers are however about 30% slower. Defaults to `true`
		 * @name $.jstree.defaults.core.worker
		 */
		worker : true,
		/**
		 * Force node text to plain text (and escape HTML). Defaults to `false`
		 * @name $.jstree.defaults.core.force_text
		 */
		force_text : false,
		/**
		 * Should the node should be toggled if the text is double clicked . Defaults to `true`
		 * @name $.jstree.defaults.core.dblclick_toggle
		 */
		dblclick_toggle : true
	};
	$.jstree.core.prototype = {
		/**
		 * used to decorate an instance with a plugin. Used internally.
		 * @private
		 * @name plugin(deco [, opts])
		 * @param  {String} deco the plugin to decorate with
		 * @param  {Object} opts options for the plugin
		 * @return {jsTree}
		 */
		plugin : function (deco, opts) {
			var Child = $.jstree.plugins[deco];
			if(Child) {
				this._data[deco] = {};
				Child.prototype = this;
				return new Child(opts, this);
			}
			return this;
		},
		/**
		 * initialize the instance. Used internally.
		 * @private
		 * @name init(el, optons)
		 * @param {DOMElement|jQuery|String} el the element we are transforming
		 * @param {Object} options options for this instance
		 * @trigger init.jstree, loading.jstree, loaded.jstree, ready.jstree, changed.jstree
		 */
		init : function (el, options) {
			this._model = {
				data : {},
				changed : [],
				force_full_redraw : false,
				redraw_timeout : false,
				default_state : {
					loaded : true,
					opened : false,
					selected : false,
					disabled : false
				}
			};
			this._model.data[$.jstree.root] = {
				id : $.jstree.root,
				parent : null,
				parents : [],
				children : [],
				children_d : [],
				state : { loaded : false }
			};

			this.element = $(el).addClass('jstree jstree-' + this._id);
			this.settings = options;

			this._data.core.ready = false;
			this._data.core.loaded = false;
			this._data.core.rtl = (this.element.css("direction") === "rtl");
			this.element[this._data.core.rtl ? 'addClass' : 'removeClass']("jstree-rtl");
			this.element.attr('role','tree');
			if(this.settings.core.multiple) {
				this.element.attr('aria-multiselectable', true);
			}
			if(!this.element.attr('tabindex')) {
				this.element.attr('tabindex','0');
			}

			this.bind();
			/**
			 * triggered after all events are bound
			 * @event
			 * @name init.jstree
			 */
			this.trigger("init");

			this._data.core.original_container_html = this.element.find(" > ul > li").clone(true);
			this._data.core.original_container_html
				.find("li").addBack()
				.contents().filter(function() {
					return this.nodeType === 3 && (!this.nodeValue || /^\s+$/.test(this.nodeValue));
				})
				.remove();
			this.element.html("<"+"ul class='jstree-container-ul jstree-children' role='group'><"+"li id='j"+this._id+"_loading' class='jstree-initial-node jstree-loading jstree-leaf jstree-last' role='tree-item'><i class='jstree-icon jstree-ocl'></i><"+"a class='jstree-anchor' href='#'><i class='jstree-icon jstree-themeicon-hidden'></i>" + this.get_string("Loading ...") + "</a></li></ul>");
			this.element.attr('aria-activedescendant','j' + this._id + '_loading');
			this._data.core.li_height = this.get_container_ul().children("li").first().height() || 24;
			this._data.core.node = this._create_prototype_node();
			/**
			 * triggered after the loading text is shown and before loading starts
			 * @event
			 * @name loading.jstree
			 */
			this.trigger("loading");
			this.load_node($.jstree.root);
		},
		/**
		 * destroy an instance
		 * @name destroy()
		 * @param  {Boolean} keep_html if not set to `true` the container will be emptied, otherwise the current DOM elements will be kept intact
		 */
		destroy : function (keep_html) {
			if(this._wrk) {
				try {
					window.URL.revokeObjectURL(this._wrk);
					this._wrk = null;
				}
				catch (ignore) { }
			}
			if(!keep_html) { this.element.empty(); }
			this.teardown();
		},
		/**
		 * Create prototype node
		 */
		_create_prototype_node : function () {
			var _node = document.createElement('LI'), _temp1, _temp2;
			_node.setAttribute('role', 'treeitem');
			_temp1 = document.createElement('I');
			_temp1.className = 'jstree-icon jstree-ocl';
			_temp1.setAttribute('role', 'presentation');
			_node.appendChild(_temp1);
			_temp1 = document.createElement('A');
			_temp1.className = 'jstree-anchor';
			_temp1.setAttribute('href','#');
			_temp1.setAttribute('tabindex','-1');
			_temp2 = document.createElement('I');
			_temp2.className = 'jstree-icon jstree-themeicon';
			_temp2.setAttribute('role', 'presentation');
			_temp1.appendChild(_temp2);
			_node.appendChild(_temp1);
			_temp1 = _temp2 = null;

			return _node;
		},
		/**
		 * part of the destroying of an instance. Used internally.
		 * @private
		 * @name teardown()
		 */
		teardown : function () {
			this.unbind();
			this.element
				.removeClass('jstree')
				.removeData('jstree')
				.find("[class^='jstree']")
					.addBack()
					.attr("class", function () { return this.className.replace(/jstree[^ ]*|$/ig,''); });
			this.element = null;
		},
		/**
		 * bind all events. Used internally.
		 * @private
		 * @name bind()
		 */
		bind : function () {
			var word = '',
				tout = null,
				was_click = 0;
			this.element
				.on("dblclick.jstree", function (e) {
						if(e.target.tagName && e.target.tagName.toLowerCase() === "input") { return true; }
						if(document.selection && document.selection.empty) {
							document.selection.empty();
						}
						else {
							if(window.getSelection) {
								var sel = window.getSelection();
								try {
									sel.removeAllRanges();
									sel.collapse();
								} catch (ignore) { }
							}
						}
					})
				.on("mousedown.jstree", $.proxy(function (e) {
						if(e.target === this.element[0]) {
							e.preventDefault(); // prevent losing focus when clicking scroll arrows (FF, Chrome)
							was_click = +(new Date()); // ie does not allow to prevent losing focus
						}
					}, this))
				.on("mousedown.jstree", ".jstree-ocl", function (e) {
						e.preventDefault(); // prevent any node inside from losing focus when clicking the open/close icon
					})
				.on("click.jstree", ".jstree-ocl", $.proxy(function (e) {
						this.toggle_node(e.target);
					}, this))
				.on("dblclick.jstree", ".jstree-anchor", $.proxy(function (e) {
						if(e.target.tagName && e.target.tagName.toLowerCase() === "input") { return true; }
						if(this.settings.core.dblclick_toggle) {
							this.toggle_node(e.target);
						}
					}, this))
				.on("click.jstree", ".jstree-anchor", $.proxy(function (e) {
						e.preventDefault();
						if(e.currentTarget !== document.activeElement) { $(e.currentTarget).focus(); }
						this.activate_node(e.currentTarget, e);
					}, this))
				.on('keydown.jstree', '.jstree-anchor', $.proxy(function (e) {
						if(e.target.tagName && e.target.tagName.toLowerCase() === "input") { return true; }
						if(e.which !== 32 && e.which !== 13 && (e.shiftKey || e.ctrlKey || e.altKey || e.metaKey)) { return true; }
						var o = null;
						if(this._data.core.rtl) {
							if(e.which === 37) { e.which = 39; }
							else if(e.which === 39) { e.which = 37; }
						}
						switch(e.which) {
							case 32: // aria defines space only with Ctrl
								if(e.ctrlKey) {
									e.type = "click";
									$(e.currentTarget).trigger(e);
								}
								break;
							case 13: // enter
								e.type = "click";
								$(e.currentTarget).trigger(e);
								break;
							case 37: // left
								e.preventDefault();
								if(this.is_open(e.currentTarget)) {
									this.close_node(e.currentTarget);
								}
								else {
									o = this.get_parent(e.currentTarget);
									if(o && o.id !== $.jstree.root) { this.get_node(o, true).children('.jstree-anchor').focus(); }
								}
								break;
							case 38: // up
								e.preventDefault();
								o = this.get_prev_dom(e.currentTarget);
								if(o && o.length) { o.children('.jstree-anchor').focus(); }
								break;
							case 39: // right
								e.preventDefault();
								if(this.is_closed(e.currentTarget)) {
									this.open_node(e.currentTarget, function (o) { this.get_node(o, true).children('.jstree-anchor').focus(); });
								}
								else if (this.is_open(e.currentTarget)) {
									o = this.get_node(e.currentTarget, true).children('.jstree-children')[0];
									if(o) { $(this._firstChild(o)).children('.jstree-anchor').focus(); }
								}
								break;
							case 40: // down
								e.preventDefault();
								o = this.get_next_dom(e.currentTarget);
								if(o && o.length) { o.children('.jstree-anchor').focus(); }
								break;
							case 106: // aria defines * on numpad as open_all - not very common
								this.open_all();
								break;
							case 36: // home
								e.preventDefault();
								o = this._firstChild(this.get_container_ul()[0]);
								if(o) { $(o).children('.jstree-anchor').filter(':visible').focus(); }
								break;
							case 35: // end
								e.preventDefault();
								this.element.find('.jstree-anchor').filter(':visible').last().focus();
								break;
							case 113: // f2 - safe to include - if check_callback is false it will fail
								e.preventDefault();
								this.edit(e.currentTarget);
								break;
							default:
								break;
							/*!
							// delete
							case 46:
								e.preventDefault();
								o = this.get_node(e.currentTarget);
								if(o && o.id && o.id !== $.jstree.root) {
									o = this.is_selected(o) ? this.get_selected() : o;
									this.delete_node(o);
								}
								break;

							*/
						}
					}, this))
				.on("load_node.jstree", $.proxy(function (e, data) {
						if(data.status) {
							if(data.node.id === $.jstree.root && !this._data.core.loaded) {
								this._data.core.loaded = true;
								if(this._firstChild(this.get_container_ul()[0])) {
									this.element.attr('aria-activedescendant',this._firstChild(this.get_container_ul()[0]).id);
								}
								/**
								 * triggered after the root node is loaded for the first time
								 * @event
								 * @name loaded.jstree
								 */
								this.trigger("loaded");
							}
							if(!this._data.core.ready) {
								setTimeout($.proxy(function() {
									if(this.element && !this.get_container_ul().find('.jstree-loading').length) {
										this._data.core.ready = true;
										if(this._data.core.selected.length) {
											if(this.settings.core.expand_selected_onload) {
												var tmp = [], i, j;
												for(i = 0, j = this._data.core.selected.length; i < j; i++) {
													tmp = tmp.concat(this._model.data[this._data.core.selected[i]].parents);
												}
												tmp = $.vakata.array_unique(tmp);
												for(i = 0, j = tmp.length; i < j; i++) {
													this.open_node(tmp[i], false, 0);
												}
											}
											this.trigger('changed', { 'action' : 'ready', 'selected' : this._data.core.selected });
										}
										/**
										 * triggered after all nodes are finished loading
										 * @event
										 * @name ready.jstree
										 */
										this.trigger("ready");
									}
								}, this), 0);
							}
						}
					}, this))
				// quick searching when the tree is focused
				.on('keypress.jstree', $.proxy(function (e) {
						if(e.target.tagName && e.target.tagName.toLowerCase() === "input") { return true; }
						if(tout) { clearTimeout(tout); }
						tout = setTimeout(function () {
							word = '';
						}, 500);

						var chr = String.fromCharCode(e.which).toLowerCase(),
							col = this.element.find('.jstree-anchor').filter(':visible'),
							ind = col.index(document.activeElement) || 0,
							end = false;
						word += chr;

						// match for whole word from current node down (including the current node)
						if(word.length > 1) {
							col.slice(ind).each($.proxy(function (i, v) {
								if($(v).text().toLowerCase().indexOf(word) === 0) {
									$(v).focus();
									end = true;
									return false;
								}
							}, this));
							if(end) { return; }

							// match for whole word from the beginning of the tree
							col.slice(0, ind).each($.proxy(function (i, v) {
								if($(v).text().toLowerCase().indexOf(word) === 0) {
									$(v).focus();
									end = true;
									return false;
								}
							}, this));
							if(end) { return; }
						}
						// list nodes that start with that letter (only if word consists of a single char)
						if(new RegExp('^' + chr.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&') + '+$').test(word)) {
							// search for the next node starting with that letter
							col.slice(ind + 1).each($.proxy(function (i, v) {
								if($(v).text().toLowerCase().charAt(0) === chr) {
									$(v).focus();
									end = true;
									return false;
								}
							}, this));
							if(end) { return; }

							// search from the beginning
							col.slice(0, ind + 1).each($.proxy(function (i, v) {
								if($(v).text().toLowerCase().charAt(0) === chr) {
									$(v).focus();
									end = true;
									return false;
								}
							}, this));
							if(end) { return; }
						}
					}, this))
				// THEME RELATED
				.on("init.jstree", $.proxy(function () {
						var s = this.settings.core.themes;
						this._data.core.themes.dots			= s.dots;
						this._data.core.themes.stripes		= s.stripes;
						this._data.core.themes.icons		= s.icons;
						this._data.core.themes.ellipsis		= s.ellipsis;
						this.set_theme(s.name || "default", s.url);
						this.set_theme_variant(s.variant);
					}, this))
				.on("loading.jstree", $.proxy(function () {
						this[ this._data.core.themes.dots ? "show_dots" : "hide_dots" ]();
						this[ this._data.core.themes.icons ? "show_icons" : "hide_icons" ]();
						this[ this._data.core.themes.stripes ? "show_stripes" : "hide_stripes" ]();
						this[ this._data.core.themes.ellipsis ? "show_ellipsis" : "hide_ellipsis" ]();
					}, this))
				.on('blur.jstree', '.jstree-anchor', $.proxy(function (e) {
						this._data.core.focused = null;
						$(e.currentTarget).filter('.jstree-hovered').mouseleave();
						this.element.attr('tabindex', '0');
					}, this))
				.on('focus.jstree', '.jstree-anchor', $.proxy(function (e) {
						var tmp = this.get_node(e.currentTarget);
						if(tmp && tmp.id) {
							this._data.core.focused = tmp.id;
						}
						this.element.find('.jstree-hovered').not(e.currentTarget).mouseleave();
						$(e.currentTarget).mouseenter();
						this.element.attr('tabindex', '-1');
					}, this))
				.on('focus.jstree', $.proxy(function () {
						if(+(new Date()) - was_click > 500 && !this._data.core.focused) {
							was_click = 0;
							var act = this.get_node(this.element.attr('aria-activedescendant'), true);
							if(act) {
								act.find('> .jstree-anchor').focus();
							}
						}
					}, this))
				.on('mouseenter.jstree', '.jstree-anchor', $.proxy(function (e) {
						this.hover_node(e.currentTarget);
					}, this))
				.on('mouseleave.jstree', '.jstree-anchor', $.proxy(function (e) {
						this.dehover_node(e.currentTarget);
					}, this));
		},
		/**
		 * part of the destroying of an instance. Used internally.
		 * @private
		 * @name unbind()
		 */
		unbind : function () {
			this.element.off('.jstree');
			$(document).off('.jstree-' + this._id);
		},
		/**
		 * trigger an event. Used internally.
		 * @private
		 * @name trigger(ev [, data])
		 * @param  {String} ev the name of the event to trigger
		 * @param  {Object} data additional data to pass with the event
		 */
		trigger : function (ev, data) {
			if(!data) {
				data = {};
			}
			data.instance = this;
			this.element.triggerHandler(ev.replace('.jstree','') + '.jstree', data);
		},
		/**
		 * returns the jQuery extended instance container
		 * @name get_container()
		 * @return {jQuery}
		 */
		get_container : function () {
			return this.element;
		},
		/**
		 * returns the jQuery extended main UL node inside the instance container. Used internally.
		 * @private
		 * @name get_container_ul()
		 * @return {jQuery}
		 */
		get_container_ul : function () {
			return this.element.children(".jstree-children").first();
		},
		/**
		 * gets string replacements (localization). Used internally.
		 * @private
		 * @name get_string(key)
		 * @param  {String} key
		 * @return {String}
		 */
		get_string : function (key) {
			var a = this.settings.core.strings;
			if($.isFunction(a)) { return a.call(this, key); }
			if(a && a[key]) { return a[key]; }
			return key;
		},
		/**
		 * gets the first child of a DOM node. Used internally.
		 * @private
		 * @name _firstChild(dom)
		 * @param  {DOMElement} dom
		 * @return {DOMElement}
		 */
		_firstChild : function (dom) {
			dom = dom ? dom.firstChild : null;
			while(dom !== null && dom.nodeType !== 1) {
				dom = dom.nextSibling;
			}
			return dom;
		},
		/**
		 * gets the next sibling of a DOM node. Used internally.
		 * @private
		 * @name _nextSibling(dom)
		 * @param  {DOMElement} dom
		 * @return {DOMElement}
		 */
		_nextSibling : function (dom) {
			dom = dom ? dom.nextSibling : null;
			while(dom !== null && dom.nodeType !== 1) {
				dom = dom.nextSibling;
			}
			return dom;
		},
		/**
		 * gets the previous sibling of a DOM node. Used internally.
		 * @private
		 * @name _previousSibling(dom)
		 * @param  {DOMElement} dom
		 * @return {DOMElement}
		 */
		_previousSibling : function (dom) {
			dom = dom ? dom.previousSibling : null;
			while(dom !== null && dom.nodeType !== 1) {
				dom = dom.previousSibling;
			}
			return dom;
		},
		/**
		 * get the JSON representation of a node (or the actual jQuery extended DOM node) by using any input (child DOM element, ID string, selector, etc)
		 * @name get_node(obj [, as_dom])
		 * @param  {mixed} obj
		 * @param  {Boolean} as_dom
		 * @return {Object|jQuery}
		 */
		get_node : function (obj, as_dom) {
			if(obj && obj.id) {
				obj = obj.id;
			}
			var dom;
			try {
				if(this._model.data[obj]) {
					obj = this._model.data[obj];
				}
				else if(typeof obj === "string" && this._model.data[obj.replace(/^#/, '')]) {
					obj = this._model.data[obj.replace(/^#/, '')];
				}
				else if(typeof obj === "string" && (dom = $('#' + obj.replace($.jstree.idregex,'\\$&'), this.element)).length && this._model.data[dom.closest('.jstree-node').attr('id')]) {
					obj = this._model.data[dom.closest('.jstree-node').attr('id')];
				}
				else if((dom = $(obj, this.element)).length && this._model.data[dom.closest('.jstree-node').attr('id')]) {
					obj = this._model.data[dom.closest('.jstree-node').attr('id')];
				}
				else if((dom = $(obj, this.element)).length && dom.hasClass('jstree')) {
					obj = this._model.data[$.jstree.root];
				}
				else {
					return false;
				}

				if(as_dom) {
					obj = obj.id === $.jstree.root ? this.element : $('#' + obj.id.replace($.jstree.idregex,'\\$&'), this.element);
				}
				return obj;
			} catch (ex) { return false; }
		},
		/**
		 * get the path to a node, either consisting of node texts, or of node IDs, optionally glued together (otherwise an array)
		 * @name get_path(obj [, glue, ids])
		 * @param  {mixed} obj the node
		 * @param  {String} glue if you want the path as a string - pass the glue here (for example '/'), if a falsy value is supplied here, an array is returned
		 * @param  {Boolean} ids if set to true build the path using ID, otherwise node text is used
		 * @return {mixed}
		 */
		get_path : function (obj, glue, ids) {
			obj = obj.parents ? obj : this.get_node(obj);
			if(!obj || obj.id === $.jstree.root || !obj.parents) {
				return false;
			}
			var i, j, p = [];
			p.push(ids ? obj.id : obj.text);
			for(i = 0, j = obj.parents.length; i < j; i++) {
				p.push(ids ? obj.parents[i] : this.get_text(obj.parents[i]));
			}
			p = p.reverse().slice(1);
			return glue ? p.join(glue) : p;
		},
		/**
		 * get the next visible node that is below the `obj` node. If `strict` is set to `true` only sibling nodes are returned.
		 * @name get_next_dom(obj [, strict])
		 * @param  {mixed} obj
		 * @param  {Boolean} strict
		 * @return {jQuery}
		 */
		get_next_dom : function (obj, strict) {
			var tmp;
			obj = this.get_node(obj, true);
			if(obj[0] === this.element[0]) {
				tmp = this._firstChild(this.get_container_ul()[0]);
				while (tmp && tmp.offsetHeight === 0) {
					tmp = this._nextSibling(tmp);
				}
				return tmp ? $(tmp) : false;
			}
			if(!obj || !obj.length) {
				return false;
			}
			if(strict) {
				tmp = obj[0];
				do {
					tmp = this._nextSibling(tmp);
				} while (tmp && tmp.offsetHeight === 0);
				return tmp ? $(tmp) : false;
			}
			if(obj.hasClass("jstree-open")) {
				tmp = this._firstChild(obj.children('.jstree-children')[0]);
				while (tmp && tmp.offsetHeight === 0) {
					tmp = this._nextSibling(tmp);
				}
				if(tmp !== null) {
					return $(tmp);
				}
			}
			tmp = obj[0];
			do {
				tmp = this._nextSibling(tmp);
			} while (tmp && tmp.offsetHeight === 0);
			if(tmp !== null) {
				return $(tmp);
			}
			return obj.parentsUntil(".jstree",".jstree-node").nextAll(".jstree-node:visible").first();
		},
		/**
		 * get the previous visible node that is above the `obj` node. If `strict` is set to `true` only sibling nodes are returned.
		 * @name get_prev_dom(obj [, strict])
		 * @param  {mixed} obj
		 * @param  {Boolean} strict
		 * @return {jQuery}
		 */
		get_prev_dom : function (obj, strict) {
			var tmp;
			obj = this.get_node(obj, true);
			if(obj[0] === this.element[0]) {
				tmp = this.get_container_ul()[0].lastChild;
				while (tmp && tmp.offsetHeight === 0) {
					tmp = this._previousSibling(tmp);
				}
				return tmp ? $(tmp) : false;
			}
			if(!obj || !obj.length) {
				return false;
			}
			if(strict) {
				tmp = obj[0];
				do {
					tmp = this._previousSibling(tmp);
				} while (tmp && tmp.offsetHeight === 0);
				return tmp ? $(tmp) : false;
			}
			tmp = obj[0];
			do {
				tmp = this._previousSibling(tmp);
			} while (tmp && tmp.offsetHeight === 0);
			if(tmp !== null) {
				obj = $(tmp);
				while(obj.hasClass("jstree-open")) {
					obj = obj.children(".jstree-children").first().children(".jstree-node:visible:last");
				}
				return obj;
			}
			tmp = obj[0].parentNode.parentNode;
			return tmp && tmp.className && tmp.className.indexOf('jstree-node') !== -1 ? $(tmp) : false;
		},
		/**
		 * get the parent ID of a node
		 * @name get_parent(obj)
		 * @param  {mixed} obj
		 * @return {String}
		 */
		get_parent : function (obj) {
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			return obj.parent;
		},
		/**
		 * get a jQuery collection of all the children of a node (node must be rendered)
		 * @name get_children_dom(obj)
		 * @param  {mixed} obj
		 * @return {jQuery}
		 */
		get_children_dom : function (obj) {
			obj = this.get_node(obj, true);
			if(obj[0] === this.element[0]) {
				return this.get_container_ul().children(".jstree-node");
			}
			if(!obj || !obj.length) {
				return false;
			}
			return obj.children(".jstree-children").children(".jstree-node");
		},
		/**
		 * checks if a node has children
		 * @name is_parent(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_parent : function (obj) {
			obj = this.get_node(obj);
			return obj && (obj.state.loaded === false || obj.children.length > 0);
		},
		/**
		 * checks if a node is loaded (its children are available)
		 * @name is_loaded(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_loaded : function (obj) {
			obj = this.get_node(obj);
			return obj && obj.state.loaded;
		},
		/**
		 * check if a node is currently loading (fetching children)
		 * @name is_loading(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_loading : function (obj) {
			obj = this.get_node(obj);
			return obj && obj.state && obj.state.loading;
		},
		/**
		 * check if a node is opened
		 * @name is_open(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_open : function (obj) {
			obj = this.get_node(obj);
			return obj && obj.state.opened;
		},
		/**
		 * check if a node is in a closed state
		 * @name is_closed(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_closed : function (obj) {
			obj = this.get_node(obj);
			return obj && this.is_parent(obj) && !obj.state.opened;
		},
		/**
		 * check if a node has no children
		 * @name is_leaf(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_leaf : function (obj) {
			return !this.is_parent(obj);
		},
		/**
		 * loads a node (fetches its children using the `core.data` setting). Multiple nodes can be passed to by using an array.
		 * @name load_node(obj [, callback])
		 * @param  {mixed} obj
		 * @param  {function} callback a function to be executed once loading is complete, the function is executed in the instance's scope and receives two arguments - the node and a boolean status
		 * @return {Boolean}
		 * @trigger load_node.jstree
		 */
		load_node : function (obj, callback) {
			var k, l, i, j, c;
			if($.isArray(obj)) {
				this._load_nodes(obj.slice(), callback);
				return true;
			}
			obj = this.get_node(obj);
			if(!obj) {
				if(callback) { callback.call(this, obj, false); }
				return false;
			}
			// if(obj.state.loading) { } // the node is already loading - just wait for it to load and invoke callback? but if called implicitly it should be loaded again?
			if(obj.state.loaded) {
				obj.state.loaded = false;
				for(i = 0, j = obj.parents.length; i < j; i++) {
					this._model.data[obj.parents[i]].children_d = $.vakata.array_filter(this._model.data[obj.parents[i]].children_d, function (v) {
						return $.inArray(v, obj.children_d) === -1;
					});
				}
				for(k = 0, l = obj.children_d.length; k < l; k++) {
					if(this._model.data[obj.children_d[k]].state.selected) {
						c = true;
					}
					delete this._model.data[obj.children_d[k]];
				}
				if (c) {
					this._data.core.selected = $.vakata.array_filter(this._data.core.selected, function (v) {
						return $.inArray(v, obj.children_d) === -1;
					});
				}
				obj.children = [];
				obj.children_d = [];
				if(c) {
					this.trigger('changed', { 'action' : 'load_node', 'node' : obj, 'selected' : this._data.core.selected });
				}
			}
			obj.state.failed = false;
			obj.state.loading = true;
			this.get_node(obj, true).addClass("jstree-loading").attr('aria-busy',true);
			this._load_node(obj, $.proxy(function (status) {
				obj = this._model.data[obj.id];
				obj.state.loading = false;
				obj.state.loaded = status;
				obj.state.failed = !obj.state.loaded;
				var dom = this.get_node(obj, true), i = 0, j = 0, m = this._model.data, has_children = false;
				for(i = 0, j = obj.children.length; i < j; i++) {
					if(m[obj.children[i]] && !m[obj.children[i]].state.hidden) {
						has_children = true;
						break;
					}
				}
				if(obj.state.loaded && dom && dom.length) {
					dom.removeClass('jstree-closed jstree-open jstree-leaf');
					if (!has_children) {
						dom.addClass('jstree-leaf');
					}
					else {
						if (obj.id !== '#') {
							dom.addClass(obj.state.opened ? 'jstree-open' : 'jstree-closed');
						}
					}
				}
				dom.removeClass("jstree-loading").attr('aria-busy',false);
				/**
				 * triggered after a node is loaded
				 * @event
				 * @name load_node.jstree
				 * @param {Object} node the node that was loading
				 * @param {Boolean} status was the node loaded successfully
				 */
				this.trigger('load_node', { "node" : obj, "status" : status });
				if(callback) {
					callback.call(this, obj, status);
				}
			}, this));
			return true;
		},
		/**
		 * load an array of nodes (will also load unavailable nodes as soon as the appear in the structure). Used internally.
		 * @private
		 * @name _load_nodes(nodes [, callback])
		 * @param  {array} nodes
		 * @param  {function} callback a function to be executed once loading is complete, the function is executed in the instance's scope and receives one argument - the array passed to _load_nodes
		 */
		_load_nodes : function (nodes, callback, is_callback, force_reload) {
			var r = true,
				c = function () { this._load_nodes(nodes, callback, true); },
				m = this._model.data, i, j, tmp = [];
			for(i = 0, j = nodes.length; i < j; i++) {
				if(m[nodes[i]] && ( (!m[nodes[i]].state.loaded && !m[nodes[i]].state.failed) || (!is_callback && force_reload) )) {
					if(!this.is_loading(nodes[i])) {
						this.load_node(nodes[i], c);
					}
					r = false;
				}
			}
			if(r) {
				for(i = 0, j = nodes.length; i < j; i++) {
					if(m[nodes[i]] && m[nodes[i]].state.loaded) {
						tmp.push(nodes[i]);
					}
				}
				if(callback && !callback.done) {
					callback.call(this, tmp);
					callback.done = true;
				}
			}
		},
		/**
		 * loads all unloaded nodes
		 * @name load_all([obj, callback])
		 * @param {mixed} obj the node to load recursively, omit to load all nodes in the tree
		 * @param {function} callback a function to be executed once loading all the nodes is complete,
		 * @trigger load_all.jstree
		 */
		load_all : function (obj, callback) {
			if(!obj) { obj = $.jstree.root; }
			obj = this.get_node(obj);
			if(!obj) { return false; }
			var to_load = [],
				m = this._model.data,
				c = m[obj.id].children_d,
				i, j;
			if(obj.state && !obj.state.loaded) {
				to_load.push(obj.id);
			}
			for(i = 0, j = c.length; i < j; i++) {
				if(m[c[i]] && m[c[i]].state && !m[c[i]].state.loaded) {
					to_load.push(c[i]);
				}
			}
			if(to_load.length) {
				this._load_nodes(to_load, function () {
					this.load_all(obj, callback);
				});
			}
			else {
				/**
				 * triggered after a load_all call completes
				 * @event
				 * @name load_all.jstree
				 * @param {Object} node the recursively loaded node
				 */
				if(callback) { callback.call(this, obj); }
				this.trigger('load_all', { "node" : obj });
			}
		},
		/**
		 * handles the actual loading of a node. Used only internally.
		 * @private
		 * @name _load_node(obj [, callback])
		 * @param  {mixed} obj
		 * @param  {function} callback a function to be executed once loading is complete, the function is executed in the instance's scope and receives one argument - a boolean status
		 * @return {Boolean}
		 */
		_load_node : function (obj, callback) {
			var s = this.settings.core.data, t;
			var notTextOrCommentNode = function notTextOrCommentNode () {
				return this.nodeType !== 3 && this.nodeType !== 8;
			};
			// use original HTML
			if(!s) {
				if(obj.id === $.jstree.root) {
					return this._append_html_data(obj, this._data.core.original_container_html.clone(true), function (status) {
						callback.call(this, status);
					});
				}
				else {
					return callback.call(this, false);
				}
				// return callback.call(this, obj.id === $.jstree.root ? this._append_html_data(obj, this._data.core.original_container_html.clone(true)) : false);
			}
			if($.isFunction(s)) {
				return s.call(this, obj, $.proxy(function (d) {
					if(d === false) {
						callback.call(this, false);
					}
					else {
						this[typeof d === 'string' ? '_append_html_data' : '_append_json_data'](obj, typeof d === 'string' ? $($.parseHTML(d)).filter(notTextOrCommentNode) : d, function (status) {
							callback.call(this, status);
						});
					}
					// return d === false ? callback.call(this, false) : callback.call(this, this[typeof d === 'string' ? '_append_html_data' : '_append_json_data'](obj, typeof d === 'string' ? $(d) : d));
				}, this));
			}
			if(typeof s === 'object') {
				if(s.url) {
					s = $.extend(true, {}, s);
					if($.isFunction(s.url)) {
						s.url = s.url.call(this, obj);
					}
					if($.isFunction(s.data)) {
						s.data = s.data.call(this, obj);
					}
					return $.ajax(s)
						.done($.proxy(function (d,t,x) {
								var type = x.getResponseHeader('Content-Type');
								if((type && type.indexOf('json') !== -1) || typeof d === "object") {
									return this._append_json_data(obj, d, function (status) { callback.call(this, status); });
									//return callback.call(this, this._append_json_data(obj, d));
								}
								if((type && type.indexOf('html') !== -1) || typeof d === "string") {
									return this._append_html_data(obj, $($.parseHTML(d)).filter(notTextOrCommentNode), function (status) { callback.call(this, status); });
									// return callback.call(this, this._append_html_data(obj, $(d)));
								}
								this._data.core.last_error = { 'error' : 'ajax', 'plugin' : 'core', 'id' : 'core_04', 'reason' : 'Could not load node', 'data' : JSON.stringify({ 'id' : obj.id, 'xhr' : x }) };
								this.settings.core.error.call(this, this._data.core.last_error);
								return callback.call(this, false);
							}, this))
						.fail($.proxy(function (f) {
								callback.call(this, false);
								this._data.core.last_error = { 'error' : 'ajax', 'plugin' : 'core', 'id' : 'core_04', 'reason' : 'Could not load node', 'data' : JSON.stringify({ 'id' : obj.id, 'xhr' : f }) };
								this.settings.core.error.call(this, this._data.core.last_error);
							}, this));
				}
				t = ($.isArray(s) || $.isPlainObject(s)) ? JSON.parse(JSON.stringify(s)) : s;
				if(obj.id === $.jstree.root) {
					return this._append_json_data(obj, t, function (status) {
						callback.call(this, status);
					});
				}
				else {
					this._data.core.last_error = { 'error' : 'nodata', 'plugin' : 'core', 'id' : 'core_05', 'reason' : 'Could not load node', 'data' : JSON.stringify({ 'id' : obj.id }) };
					this.settings.core.error.call(this, this._data.core.last_error);
					return callback.call(this, false);
				}
				//return callback.call(this, (obj.id === $.jstree.root ? this._append_json_data(obj, t) : false) );
			}
			if(typeof s === 'string') {
				if(obj.id === $.jstree.root) {
					return this._append_html_data(obj, $($.parseHTML(s)).filter(notTextOrCommentNode), function (status) {
						callback.call(this, status);
					});
				}
				else {
					this._data.core.last_error = { 'error' : 'nodata', 'plugin' : 'core', 'id' : 'core_06', 'reason' : 'Could not load node', 'data' : JSON.stringify({ 'id' : obj.id }) };
					this.settings.core.error.call(this, this._data.core.last_error);
					return callback.call(this, false);
				}
				//return callback.call(this, (obj.id === $.jstree.root ? this._append_html_data(obj, $(s)) : false) );
			}
			return callback.call(this, false);
		},
		/**
		 * adds a node to the list of nodes to redraw. Used only internally.
		 * @private
		 * @name _node_changed(obj [, callback])
		 * @param  {mixed} obj
		 */
		_node_changed : function (obj) {
			obj = this.get_node(obj);
			if(obj) {
				this._model.changed.push(obj.id);
			}
		},
		/**
		 * appends HTML content to the tree. Used internally.
		 * @private
		 * @name _append_html_data(obj, data)
		 * @param  {mixed} obj the node to append to
		 * @param  {String} data the HTML string to parse and append
		 * @trigger model.jstree, changed.jstree
		 */
		_append_html_data : function (dom, data, cb) {
			dom = this.get_node(dom);
			dom.children = [];
			dom.children_d = [];
			var dat = data.is('ul') ? data.children() : data,
				par = dom.id,
				chd = [],
				dpc = [],
				m = this._model.data,
				p = m[par],
				s = this._data.core.selected.length,
				tmp, i, j;
			dat.each($.proxy(function (i, v) {
				tmp = this._parse_model_from_html($(v), par, p.parents.concat());
				if(tmp) {
					chd.push(tmp);
					dpc.push(tmp);
					if(m[tmp].children_d.length) {
						dpc = dpc.concat(m[tmp].children_d);
					}
				}
			}, this));
			p.children = chd;
			p.children_d = dpc;
			for(i = 0, j = p.parents.length; i < j; i++) {
				m[p.parents[i]].children_d = m[p.parents[i]].children_d.concat(dpc);
			}
			/**
			 * triggered when new data is inserted to the tree model
			 * @event
			 * @name model.jstree
			 * @param {Array} nodes an array of node IDs
			 * @param {String} parent the parent ID of the nodes
			 */
			this.trigger('model', { "nodes" : dpc, 'parent' : par });
			if(par !== $.jstree.root) {
				this._node_changed(par);
				this.redraw();
			}
			else {
				this.get_container_ul().children('.jstree-initial-node').remove();
				this.redraw(true);
			}
			if(this._data.core.selected.length !== s) {
				this.trigger('changed', { 'action' : 'model', 'selected' : this._data.core.selected });
			}
			cb.call(this, true);
		},
		/**
		 * appends JSON content to the tree. Used internally.
		 * @private
		 * @name _append_json_data(obj, data)
		 * @param  {mixed} obj the node to append to
		 * @param  {String} data the JSON object to parse and append
		 * @param  {Boolean} force_processing internal param - do not set
		 * @trigger model.jstree, changed.jstree
		 */
		_append_json_data : function (dom, data, cb, force_processing) {
			if(this.element === null) { return; }
			dom = this.get_node(dom);
			dom.children = [];
			dom.children_d = [];
			// *%$@!!!
			if(data.d) {
				data = data.d;
				if(typeof data === "string") {
					data = JSON.parse(data);
				}
			}
			if(!$.isArray(data)) { data = [data]; }
			var w = null,
				args = {
					'df'	: this._model.default_state,
					'dat'	: data,
					'par'	: dom.id,
					'm'		: this._model.data,
					't_id'	: this._id,
					't_cnt'	: this._cnt,
					'sel'	: this._data.core.selected
				},
				func = function (data, undefined) {
					if(data.data) { data = data.data; }
					var dat = data.dat,
						par = data.par,
						chd = [],
						dpc = [],
						add = [],
						df = data.df,
						t_id = data.t_id,
						t_cnt = data.t_cnt,
						m = data.m,
						p = m[par],
						sel = data.sel,
						tmp, i, j, rslt,
						parse_flat = function (d, p, ps) {
							if(!ps) { ps = []; }
							else { ps = ps.concat(); }
							if(p) { ps.unshift(p); }
							var tid = d.id.toString(),
								i, j, c, e,
								tmp = {
									id			: tid,
									text		: d.text || '',
									icon		: d.icon !== undefined ? d.icon : true,
									parent		: p,
									parents		: ps,
									children	: d.children || [],
									children_d	: d.children_d || [],
									data		: d.data,
									state		: { },
									li_attr		: { id : false },
									a_attr		: { href : '#' },
									original	: false
								};
							for(i in df) {
								if(df.hasOwnProperty(i)) {
									tmp.state[i] = df[i];
								}
							}
							if(d && d.data && d.data.jstree && d.data.jstree.icon) {
								tmp.icon = d.data.jstree.icon;
							}
							if(tmp.icon === undefined || tmp.icon === null || tmp.icon === "") {
								tmp.icon = true;
							}
							if(d && d.data) {
								tmp.data = d.data;
								if(d.data.jstree) {
									for(i in d.data.jstree) {
										if(d.data.jstree.hasOwnProperty(i)) {
											tmp.state[i] = d.data.jstree[i];
										}
									}
								}
							}
							if(d && typeof d.state === 'object') {
								for (i in d.state) {
									if(d.state.hasOwnProperty(i)) {
										tmp.state[i] = d.state[i];
									}
								}
							}
							if(d && typeof d.li_attr === 'object') {
								for (i in d.li_attr) {
									if(d.li_attr.hasOwnProperty(i)) {
										tmp.li_attr[i] = d.li_attr[i];
									}
								}
							}
							if(!tmp.li_attr.id) {
								tmp.li_attr.id = tid;
							}
							if(d && typeof d.a_attr === 'object') {
								for (i in d.a_attr) {
									if(d.a_attr.hasOwnProperty(i)) {
										tmp.a_attr[i] = d.a_attr[i];
									}
								}
							}
							if(d && d.children && d.children === true) {
								tmp.state.loaded = false;
								tmp.children = [];
								tmp.children_d = [];
							}
							m[tmp.id] = tmp;
							for(i = 0, j = tmp.children.length; i < j; i++) {
								c = parse_flat(m[tmp.children[i]], tmp.id, ps);
								e = m[c];
								tmp.children_d.push(c);
								if(e.children_d.length) {
									tmp.children_d = tmp.children_d.concat(e.children_d);
								}
							}
							delete d.data;
							delete d.children;
							m[tmp.id].original = d;
							if(tmp.state.selected) {
								add.push(tmp.id);
							}
							return tmp.id;
						},
						parse_nest = function (d, p, ps) {
							if(!ps) { ps = []; }
							else { ps = ps.concat(); }
							if(p) { ps.unshift(p); }
							var tid = false, i, j, c, e, tmp;
							do {
								tid = 'j' + t_id + '_' + (++t_cnt);
							} while(m[tid]);

							tmp = {
								id			: false,
								text		: typeof d === 'string' ? d : '',
								icon		: typeof d === 'object' && d.icon !== undefined ? d.icon : true,
								parent		: p,
								parents		: ps,
								children	: [],
								children_d	: [],
								data		: null,
								state		: { },
								li_attr		: { id : false },
								a_attr		: { href : '#' },
								original	: false
							};
							for(i in df) {
								if(df.hasOwnProperty(i)) {
									tmp.state[i] = df[i];
								}
							}
							if(d && d.id) { tmp.id = d.id.toString(); }
							if(d && d.text) { tmp.text = d.text; }
							if(d && d.data && d.data.jstree && d.data.jstree.icon) {
								tmp.icon = d.data.jstree.icon;
							}
							if(tmp.icon === undefined || tmp.icon === null || tmp.icon === "") {
								tmp.icon = true;
							}
							if(d && d.data) {
								tmp.data = d.data;
								if(d.data.jstree) {
									for(i in d.data.jstree) {
										if(d.data.jstree.hasOwnProperty(i)) {
											tmp.state[i] = d.data.jstree[i];
										}
									}
								}
							}
							if(d && typeof d.state === 'object') {
								for (i in d.state) {
									if(d.state.hasOwnProperty(i)) {
										tmp.state[i] = d.state[i];
									}
								}
							}
							if(d && typeof d.li_attr === 'object') {
								for (i in d.li_attr) {
									if(d.li_attr.hasOwnProperty(i)) {
										tmp.li_attr[i] = d.li_attr[i];
									}
								}
							}
							if(tmp.li_attr.id && !tmp.id) {
								tmp.id = tmp.li_attr.id.toString();
							}
							if(!tmp.id) {
								tmp.id = tid;
							}
							if(!tmp.li_attr.id) {
								tmp.li_attr.id = tmp.id;
							}
							if(d && typeof d.a_attr === 'object') {
								for (i in d.a_attr) {
									if(d.a_attr.hasOwnProperty(i)) {
										tmp.a_attr[i] = d.a_attr[i];
									}
								}
							}
							if(d && d.children && d.children.length) {
								for(i = 0, j = d.children.length; i < j; i++) {
									c = parse_nest(d.children[i], tmp.id, ps);
									e = m[c];
									tmp.children.push(c);
									if(e.children_d.length) {
										tmp.children_d = tmp.children_d.concat(e.children_d);
									}
								}
								tmp.children_d = tmp.children_d.concat(tmp.children);
							}
							if(d && d.children && d.children === true) {
								tmp.state.loaded = false;
								tmp.children = [];
								tmp.children_d = [];
							}
							delete d.data;
							delete d.children;
							tmp.original = d;
							m[tmp.id] = tmp;
							if(tmp.state.selected) {
								add.push(tmp.id);
							}
							return tmp.id;
						};

					if(dat.length && dat[0].id !== undefined && dat[0].parent !== undefined) {
						// Flat JSON support (for easy import from DB):
						// 1) convert to object (foreach)
						for(i = 0, j = dat.length; i < j; i++) {
							if(!dat[i].children) {
								dat[i].children = [];
							}
							m[dat[i].id.toString()] = dat[i];
						}
						// 2) populate children (foreach)
						for(i = 0, j = dat.length; i < j; i++) {
							m[dat[i].parent.toString()].children.push(dat[i].id.toString());
							// populate parent.children_d
							p.children_d.push(dat[i].id.toString());
						}
						// 3) normalize && populate parents and children_d with recursion
						for(i = 0, j = p.children.length; i < j; i++) {
							tmp = parse_flat(m[p.children[i]], par, p.parents.concat());
							dpc.push(tmp);
							if(m[tmp].children_d.length) {
								dpc = dpc.concat(m[tmp].children_d);
							}
						}
						for(i = 0, j = p.parents.length; i < j; i++) {
							m[p.parents[i]].children_d = m[p.parents[i]].children_d.concat(dpc);
						}
						// ?) three_state selection - p.state.selected && t - (if three_state foreach(dat => ch) -> foreach(parents) if(parent.selected) child.selected = true;
						rslt = {
							'cnt' : t_cnt,
							'mod' : m,
							'sel' : sel,
							'par' : par,
							'dpc' : dpc,
							'add' : add
						};
					}
					else {
						for(i = 0, j = dat.length; i < j; i++) {
							tmp = parse_nest(dat[i], par, p.parents.concat());
							if(tmp) {
								chd.push(tmp);
								dpc.push(tmp);
								if(m[tmp].children_d.length) {
									dpc = dpc.concat(m[tmp].children_d);
								}
							}
						}
						p.children = chd;
						p.children_d = dpc;
						for(i = 0, j = p.parents.length; i < j; i++) {
							m[p.parents[i]].children_d = m[p.parents[i]].children_d.concat(dpc);
						}
						rslt = {
							'cnt' : t_cnt,
							'mod' : m,
							'sel' : sel,
							'par' : par,
							'dpc' : dpc,
							'add' : add
						};
					}
					if(typeof window === 'undefined' || typeof window.document === 'undefined') {
						postMessage(rslt);
					}
					else {
						return rslt;
					}
				},
				rslt = function (rslt, worker) {
					if(this.element === null) { return; }
					this._cnt = rslt.cnt;
					var i, m = this._model.data;
					for (i in m) {
						if (m.hasOwnProperty(i) && m[i].state && m[i].state.loading && rslt.mod[i]) {
							rslt.mod[i].state.loading = true;
						}
					}
					this._model.data = rslt.mod; // breaks the reference in load_node - careful

					if(worker) {
						var j, a = rslt.add, r = rslt.sel, s = this._data.core.selected.slice();
						m = this._model.data;
						// if selection was changed while calculating in worker
						if(r.length !== s.length || $.vakata.array_unique(r.concat(s)).length !== r.length) {
							// deselect nodes that are no longer selected
							for(i = 0, j = r.length; i < j; i++) {
								if($.inArray(r[i], a) === -1 && $.inArray(r[i], s) === -1) {
									m[r[i]].state.selected = false;
								}
							}
							// select nodes that were selected in the mean time
							for(i = 0, j = s.length; i < j; i++) {
								if($.inArray(s[i], r) === -1) {
									m[s[i]].state.selected = true;
								}
							}
						}
					}
					if(rslt.add.length) {
						this._data.core.selected = this._data.core.selected.concat(rslt.add);
					}

					this.trigger('model', { "nodes" : rslt.dpc, 'parent' : rslt.par });

					if(rslt.par !== $.jstree.root) {
						this._node_changed(rslt.par);
						this.redraw();
					}
					else {
						// this.get_container_ul().children('.jstree-initial-node').remove();
						this.redraw(true);
					}
					if(rslt.add.length) {
						this.trigger('changed', { 'action' : 'model', 'selected' : this._data.core.selected });
					}
					cb.call(this, true);
				};
			if(this.settings.core.worker && window.Blob && window.URL && window.Worker) {
				try {
					if(this._wrk === null) {
						this._wrk = window.URL.createObjectURL(
							new window.Blob(
								['self.onmessage = ' + func.toString()],
								{type:"text/javascript"}
							)
						);
					}
					if(!this._data.core.working || force_processing) {
						this._data.core.working = true;
						w = new window.Worker(this._wrk);
						w.onmessage = $.proxy(function (e) {
							rslt.call(this, e.data, true);
							try { w.terminate(); w = null; } catch(ignore) { }
							if(this._data.core.worker_queue.length) {
								this._append_json_data.apply(this, this._data.core.worker_queue.shift());
							}
							else {
								this._data.core.working = false;
							}
						}, this);
						if(!args.par) {
							if(this._data.core.worker_queue.length) {
								this._append_json_data.apply(this, this._data.core.worker_queue.shift());
							}
							else {
								this._data.core.working = false;
							}
						}
						else {
							w.postMessage(args);
						}
					}
					else {
						this._data.core.worker_queue.push([dom, data, cb, true]);
					}
				}
				catch(e) {
					rslt.call(this, func(args), false);
					if(this._data.core.worker_queue.length) {
						this._append_json_data.apply(this, this._data.core.worker_queue.shift());
					}
					else {
						this._data.core.working = false;
					}
				}
			}
			else {
				rslt.call(this, func(args), false);
			}
		},
		/**
		 * parses a node from a jQuery object and appends them to the in memory tree model. Used internally.
		 * @private
		 * @name _parse_model_from_html(d [, p, ps])
		 * @param  {jQuery} d the jQuery object to parse
		 * @param  {String} p the parent ID
		 * @param  {Array} ps list of all parents
		 * @return {String} the ID of the object added to the model
		 */
		_parse_model_from_html : function (d, p, ps) {
			if(!ps) { ps = []; }
			else { ps = [].concat(ps); }
			if(p) { ps.unshift(p); }
			var c, e, m = this._model.data,
				data = {
					id			: false,
					text		: false,
					icon		: true,
					parent		: p,
					parents		: ps,
					children	: [],
					children_d	: [],
					data		: null,
					state		: { },
					li_attr		: { id : false },
					a_attr		: { href : '#' },
					original	: false
				}, i, tmp, tid;
			for(i in this._model.default_state) {
				if(this._model.default_state.hasOwnProperty(i)) {
					data.state[i] = this._model.default_state[i];
				}
			}
			tmp = $.vakata.attributes(d, true);
			$.each(tmp, function (i, v) {
				v = $.trim(v);
				if(!v.length) { return true; }
				data.li_attr[i] = v;
				if(i === 'id') {
					data.id = v.toString();
				}
			});
			tmp = d.children('a').first();
			if(tmp.length) {
				tmp = $.vakata.attributes(tmp, true);
				$.each(tmp, function (i, v) {
					v = $.trim(v);
					if(v.length) {
						data.a_attr[i] = v;
					}
				});
			}
			tmp = d.children("a").first().length ? d.children("a").first().clone() : d.clone();
			tmp.children("ins, i, ul").remove();
			tmp = tmp.html();
			tmp = $('<div />').html(tmp);
			data.text = this.settings.core.force_text ? tmp.text() : tmp.html();
			tmp = d.data();
			data.data = tmp ? $.extend(true, {}, tmp) : null;
			data.state.opened = d.hasClass('jstree-open');
			data.state.selected = d.children('a').hasClass('jstree-clicked');
			data.state.disabled = d.children('a').hasClass('jstree-disabled');
			if(data.data && data.data.jstree) {
				for(i in data.data.jstree) {
					if(data.data.jstree.hasOwnProperty(i)) {
						data.state[i] = data.data.jstree[i];
					}
				}
			}
			tmp = d.children("a").children(".jstree-themeicon");
			if(tmp.length) {
				data.icon = tmp.hasClass('jstree-themeicon-hidden') ? false : tmp.attr('rel');
			}
			if(data.state.icon !== undefined) {
				data.icon = data.state.icon;
			}
			if(data.icon === undefined || data.icon === null || data.icon === "") {
				data.icon = true;
			}
			tmp = d.children("ul").children("li");
			do {
				tid = 'j' + this._id + '_' + (++this._cnt);
			} while(m[tid]);
			data.id = data.li_attr.id ? data.li_attr.id.toString() : tid;
			if(tmp.length) {
				tmp.each($.proxy(function (i, v) {
					c = this._parse_model_from_html($(v), data.id, ps);
					e = this._model.data[c];
					data.children.push(c);
					if(e.children_d.length) {
						data.children_d = data.children_d.concat(e.children_d);
					}
				}, this));
				data.children_d = data.children_d.concat(data.children);
			}
			else {
				if(d.hasClass('jstree-closed')) {
					data.state.loaded = false;
				}
			}
			if(data.li_attr['class']) {
				data.li_attr['class'] = data.li_attr['class'].replace('jstree-closed','').replace('jstree-open','');
			}
			if(data.a_attr['class']) {
				data.a_attr['class'] = data.a_attr['class'].replace('jstree-clicked','').replace('jstree-disabled','');
			}
			m[data.id] = data;
			if(data.state.selected) {
				this._data.core.selected.push(data.id);
			}
			return data.id;
		},
		/**
		 * parses a node from a JSON object (used when dealing with flat data, which has no nesting of children, but has id and parent properties) and appends it to the in memory tree model. Used internally.
		 * @private
		 * @name _parse_model_from_flat_json(d [, p, ps])
		 * @param  {Object} d the JSON object to parse
		 * @param  {String} p the parent ID
		 * @param  {Array} ps list of all parents
		 * @return {String} the ID of the object added to the model
		 */
		_parse_model_from_flat_json : function (d, p, ps) {
			if(!ps) { ps = []; }
			else { ps = ps.concat(); }
			if(p) { ps.unshift(p); }
			var tid = d.id.toString(),
				m = this._model.data,
				df = this._model.default_state,
				i, j, c, e,
				tmp = {
					id			: tid,
					text		: d.text || '',
					icon		: d.icon !== undefined ? d.icon : true,
					parent		: p,
					parents		: ps,
					children	: d.children || [],
					children_d	: d.children_d || [],
					data		: d.data,
					state		: { },
					li_attr		: { id : false },
					a_attr		: { href : '#' },
					original	: false
				};
			for(i in df) {
				if(df.hasOwnProperty(i)) {
					tmp.state[i] = df[i];
				}
			}
			if(d && d.data && d.data.jstree && d.data.jstree.icon) {
				tmp.icon = d.data.jstree.icon;
			}
			if(tmp.icon === undefined || tmp.icon === null || tmp.icon === "") {
				tmp.icon = true;
			}
			if(d && d.data) {
				tmp.data = d.data;
				if(d.data.jstree) {
					for(i in d.data.jstree) {
						if(d.data.jstree.hasOwnProperty(i)) {
							tmp.state[i] = d.data.jstree[i];
						}
					}
				}
			}
			if(d && typeof d.state === 'object') {
				for (i in d.state) {
					if(d.state.hasOwnProperty(i)) {
						tmp.state[i] = d.state[i];
					}
				}
			}
			if(d && typeof d.li_attr === 'object') {
				for (i in d.li_attr) {
					if(d.li_attr.hasOwnProperty(i)) {
						tmp.li_attr[i] = d.li_attr[i];
					}
				}
			}
			if(!tmp.li_attr.id) {
				tmp.li_attr.id = tid;
			}
			if(d && typeof d.a_attr === 'object') {
				for (i in d.a_attr) {
					if(d.a_attr.hasOwnProperty(i)) {
						tmp.a_attr[i] = d.a_attr[i];
					}
				}
			}
			if(d && d.children && d.children === true) {
				tmp.state.loaded = false;
				tmp.children = [];
				tmp.children_d = [];
			}
			m[tmp.id] = tmp;
			for(i = 0, j = tmp.children.length; i < j; i++) {
				c = this._parse_model_from_flat_json(m[tmp.children[i]], tmp.id, ps);
				e = m[c];
				tmp.children_d.push(c);
				if(e.children_d.length) {
					tmp.children_d = tmp.children_d.concat(e.children_d);
				}
			}
			delete d.data;
			delete d.children;
			m[tmp.id].original = d;
			if(tmp.state.selected) {
				this._data.core.selected.push(tmp.id);
			}
			return tmp.id;
		},
		/**
		 * parses a node from a JSON object and appends it to the in memory tree model. Used internally.
		 * @private
		 * @name _parse_model_from_json(d [, p, ps])
		 * @param  {Object} d the JSON object to parse
		 * @param  {String} p the parent ID
		 * @param  {Array} ps list of all parents
		 * @return {String} the ID of the object added to the model
		 */
		_parse_model_from_json : function (d, p, ps) {
			if(!ps) { ps = []; }
			else { ps = ps.concat(); }
			if(p) { ps.unshift(p); }
			var tid = false, i, j, c, e, m = this._model.data, df = this._model.default_state, tmp;
			do {
				tid = 'j' + this._id + '_' + (++this._cnt);
			} while(m[tid]);

			tmp = {
				id			: false,
				text		: typeof d === 'string' ? d : '',
				icon		: typeof d === 'object' && d.icon !== undefined ? d.icon : true,
				parent		: p,
				parents		: ps,
				children	: [],
				children_d	: [],
				data		: null,
				state		: { },
				li_attr		: { id : false },
				a_attr		: { href : '#' },
				original	: false
			};
			for(i in df) {
				if(df.hasOwnProperty(i)) {
					tmp.state[i] = df[i];
				}
			}
			if(d && d.id) { tmp.id = d.id.toString(); }
			if(d && d.text) { tmp.text = d.text; }
			if(d && d.data && d.data.jstree && d.data.jstree.icon) {
				tmp.icon = d.data.jstree.icon;
			}
			if(tmp.icon === undefined || tmp.icon === null || tmp.icon === "") {
				tmp.icon = true;
			}
			if(d && d.data) {
				tmp.data = d.data;
				if(d.data.jstree) {
					for(i in d.data.jstree) {
						if(d.data.jstree.hasOwnProperty(i)) {
							tmp.state[i] = d.data.jstree[i];
						}
					}
				}
			}
			if(d && typeof d.state === 'object') {
				for (i in d.state) {
					if(d.state.hasOwnProperty(i)) {
						tmp.state[i] = d.state[i];
					}
				}
			}
			if(d && typeof d.li_attr === 'object') {
				for (i in d.li_attr) {
					if(d.li_attr.hasOwnProperty(i)) {
						tmp.li_attr[i] = d.li_attr[i];
					}
				}
			}
			if(tmp.li_attr.id && !tmp.id) {
				tmp.id = tmp.li_attr.id.toString();
			}
			if(!tmp.id) {
				tmp.id = tid;
			}
			if(!tmp.li_attr.id) {
				tmp.li_attr.id = tmp.id;
			}
			if(d && typeof d.a_attr === 'object') {
				for (i in d.a_attr) {
					if(d.a_attr.hasOwnProperty(i)) {
						tmp.a_attr[i] = d.a_attr[i];
					}
				}
			}
			if(d && d.children && d.children.length) {
				for(i = 0, j = d.children.length; i < j; i++) {
					c = this._parse_model_from_json(d.children[i], tmp.id, ps);
					e = m[c];
					tmp.children.push(c);
					if(e.children_d.length) {
						tmp.children_d = tmp.children_d.concat(e.children_d);
					}
				}
				tmp.children_d = tmp.children_d.concat(tmp.children);
			}
			if(d && d.children && d.children === true) {
				tmp.state.loaded = false;
				tmp.children = [];
				tmp.children_d = [];
			}
			delete d.data;
			delete d.children;
			tmp.original = d;
			m[tmp.id] = tmp;
			if(tmp.state.selected) {
				this._data.core.selected.push(tmp.id);
			}
			return tmp.id;
		},
		/**
		 * redraws all nodes that need to be redrawn. Used internally.
		 * @private
		 * @name _redraw()
		 * @trigger redraw.jstree
		 */
		_redraw : function () {
			var nodes = this._model.force_full_redraw ? this._model.data[$.jstree.root].children.concat([]) : this._model.changed.concat([]),
				f = document.createElement('UL'), tmp, i, j, fe = this._data.core.focused;
			for(i = 0, j = nodes.length; i < j; i++) {
				tmp = this.redraw_node(nodes[i], true, this._model.force_full_redraw);
				if(tmp && this._model.force_full_redraw) {
					f.appendChild(tmp);
				}
			}
			if(this._model.force_full_redraw) {
				f.className = this.get_container_ul()[0].className;
				f.setAttribute('role','group');
				this.element.empty().append(f);
				//this.get_container_ul()[0].appendChild(f);
			}
			if(fe !== null) {
				tmp = this.get_node(fe, true);
				if(tmp && tmp.length && tmp.children('.jstree-anchor')[0] !== document.activeElement) {
					tmp.children('.jstree-anchor').focus();
				}
				else {
					this._data.core.focused = null;
				}
			}
			this._model.force_full_redraw = false;
			this._model.changed = [];
			/**
			 * triggered after nodes are redrawn
			 * @event
			 * @name redraw.jstree
			 * @param {array} nodes the redrawn nodes
			 */
			this.trigger('redraw', { "nodes" : nodes });
		},
		/**
		 * redraws all nodes that need to be redrawn or optionally - the whole tree
		 * @name redraw([full])
		 * @param {Boolean} full if set to `true` all nodes are redrawn.
		 */
		redraw : function (full) {
			if(full) {
				this._model.force_full_redraw = true;
			}
			//if(this._model.redraw_timeout) {
			//	clearTimeout(this._model.redraw_timeout);
			//}
			//this._model.redraw_timeout = setTimeout($.proxy(this._redraw, this),0);
			this._redraw();
		},
		/**
		 * redraws a single node's children. Used internally.
		 * @private
		 * @name draw_children(node)
		 * @param {mixed} node the node whose children will be redrawn
		 */
		draw_children : function (node) {
			var obj = this.get_node(node),
				i = false,
				j = false,
				k = false,
				d = document;
			if(!obj) { return false; }
			if(obj.id === $.jstree.root) { return this.redraw(true); }
			node = this.get_node(node, true);
			if(!node || !node.length) { return false; } // TODO: quick toggle

			node.children('.jstree-children').remove();
			node = node[0];
			if(obj.children.length && obj.state.loaded) {
				k = d.createElement('UL');
				k.setAttribute('role', 'group');
				k.className = 'jstree-children';
				for(i = 0, j = obj.children.length; i < j; i++) {
					k.appendChild(this.redraw_node(obj.children[i], true, true));
				}
				node.appendChild(k);
			}
		},
		/**
		 * redraws a single node. Used internally.
		 * @private
		 * @name redraw_node(node, deep, is_callback, force_render)
		 * @param {mixed} node the node to redraw
		 * @param {Boolean} deep should child nodes be redrawn too
		 * @param {Boolean} is_callback is this a recursion call
		 * @param {Boolean} force_render should children of closed parents be drawn anyway
		 */
		redraw_node : function (node, deep, is_callback, force_render) {
			var obj = this.get_node(node),
				par = false,
				ind = false,
				old = false,
				i = false,
				j = false,
				k = false,
				c = '',
				d = document,
				m = this._model.data,
				f = false,
				s = false,
				tmp = null,
				t = 0,
				l = 0,
				has_children = false,
				last_sibling = false;
			if(!obj) { return false; }
			if(obj.id === $.jstree.root) {  return this.redraw(true); }
			deep = deep || obj.children.length === 0;
			node = !document.querySelector ? document.getElementById(obj.id) : this.element[0].querySelector('#' + ("0123456789".indexOf(obj.id[0]) !== -1 ? '\\3' + obj.id[0] + ' ' + obj.id.substr(1).replace($.jstree.idregex,'\\$&') : obj.id.replace($.jstree.idregex,'\\$&')) ); //, this.element);
			if(!node) {
				deep = true;
				//node = d.createElement('LI');
				if(!is_callback) {
					par = obj.parent !== $.jstree.root ? $('#' + obj.parent.replace($.jstree.idregex,'\\$&'), this.element)[0] : null;
					if(par !== null && (!par || !m[obj.parent].state.opened)) {
						return false;
					}
					ind = $.inArray(obj.id, par === null ? m[$.jstree.root].children : m[obj.parent].children);
				}
			}
			else {
				node = $(node);
				if(!is_callback) {
					par = node.parent().parent()[0];
					if(par === this.element[0]) {
						par = null;
					}
					ind = node.index();
				}
				// m[obj.id].data = node.data(); // use only node's data, no need to touch jquery storage
				if(!deep && obj.children.length && !node.children('.jstree-children').length) {
					deep = true;
				}
				if(!deep) {
					old = node.children('.jstree-children')[0];
				}
				f = node.children('.jstree-anchor')[0] === document.activeElement;
				node.remove();
				//node = d.createElement('LI');
				//node = node[0];
			}
			node = this._data.core.node.cloneNode(true);
			// node is DOM, deep is boolean

			c = 'jstree-node ';
			for(i in obj.li_attr) {
				if(obj.li_attr.hasOwnProperty(i)) {
					if(i === 'id') { continue; }
					if(i !== 'class') {
						node.setAttribute(i, obj.li_attr[i]);
					}
					else {
						c += obj.li_attr[i];
					}
				}
			}
			if(!obj.a_attr.id) {
				obj.a_attr.id = obj.id + '_anchor';
			}
			node.setAttribute('aria-selected', !!obj.state.selected);
			node.setAttribute('aria-level', obj.parents.length);
			node.setAttribute('aria-labelledby', obj.a_attr.id);
			if(obj.state.disabled) {
				node.setAttribute('aria-disabled', true);
			}

			for(i = 0, j = obj.children.length; i < j; i++) {
				if(!m[obj.children[i]].state.hidden) {
					has_children = true;
					break;
				}
			}
			if(obj.parent !== null && m[obj.parent] && !obj.state.hidden) {
				i = $.inArray(obj.id, m[obj.parent].children);
				last_sibling = obj.id;
				if(i !== -1) {
					i++;
					for(j = m[obj.parent].children.length; i < j; i++) {
						if(!m[m[obj.parent].children[i]].state.hidden) {
							last_sibling = m[obj.parent].children[i];
						}
						if(last_sibling !== obj.id) {
							break;
						}
					}
				}
			}

			if(obj.state.hidden) {
				c += ' jstree-hidden';
			}
			if(obj.state.loaded && !has_children) {
				c += ' jstree-leaf';
			}
			else {
				c += obj.state.opened && obj.state.loaded ? ' jstree-open' : ' jstree-closed';
				node.setAttribute('aria-expanded', (obj.state.opened && obj.state.loaded) );
			}
			if(last_sibling === obj.id) {
				c += ' jstree-last';
			}
			node.id = obj.id;
			node.className = c;
			c = ( obj.state.selected ? ' jstree-clicked' : '') + ( obj.state.disabled ? ' jstree-disabled' : '');
			for(j in obj.a_attr) {
				if(obj.a_attr.hasOwnProperty(j)) {
					if(j === 'href' && obj.a_attr[j] === '#') { continue; }
					if(j !== 'class') {
						node.childNodes[1].setAttribute(j, obj.a_attr[j]);
					}
					else {
						c += ' ' + obj.a_attr[j];
					}
				}
			}
			if(c.length) {
				node.childNodes[1].className = 'jstree-anchor ' + c;
			}
			if((obj.icon && obj.icon !== true) || obj.icon === false) {
				if(obj.icon === false) {
					node.childNodes[1].childNodes[0].className += ' jstree-themeicon-hidden';
				}
				else if(obj.icon.indexOf('/') === -1 && obj.icon.indexOf('.') === -1) {
					node.childNodes[1].childNodes[0].className += ' ' + obj.icon + ' jstree-themeicon-custom';
				}
				else {
					node.childNodes[1].childNodes[0].style.backgroundImage = 'url("'+obj.icon+'")';
					node.childNodes[1].childNodes[0].style.backgroundPosition = 'center center';
					node.childNodes[1].childNodes[0].style.backgroundSize = 'auto';
					node.childNodes[1].childNodes[0].className += ' jstree-themeicon-custom';
				}
			}

			if(this.settings.core.force_text) {
				node.childNodes[1].appendChild(d.createTextNode(obj.text));
			}
			else {
				node.childNodes[1].innerHTML += obj.text;
			}


			if(deep && obj.children.length && (obj.state.opened || force_render) && obj.state.loaded) {
				k = d.createElement('UL');
				k.setAttribute('role', 'group');
				k.className = 'jstree-children';
				for(i = 0, j = obj.children.length; i < j; i++) {
					k.appendChild(this.redraw_node(obj.children[i], deep, true));
				}
				node.appendChild(k);
			}
			if(old) {
				node.appendChild(old);
			}
			if(!is_callback) {
				// append back using par / ind
				if(!par) {
					par = this.element[0];
				}
				for(i = 0, j = par.childNodes.length; i < j; i++) {
					if(par.childNodes[i] && par.childNodes[i].className && par.childNodes[i].className.indexOf('jstree-children') !== -1) {
						tmp = par.childNodes[i];
						break;
					}
				}
				if(!tmp) {
					tmp = d.createElement('UL');
					tmp.setAttribute('role', 'group');
					tmp.className = 'jstree-children';
					par.appendChild(tmp);
				}
				par = tmp;

				if(ind < par.childNodes.length) {
					par.insertBefore(node, par.childNodes[ind]);
				}
				else {
					par.appendChild(node);
				}
				if(f) {
					t = this.element[0].scrollTop;
					l = this.element[0].scrollLeft;
					node.childNodes[1].focus();
					this.element[0].scrollTop = t;
					this.element[0].scrollLeft = l;
				}
			}
			if(obj.state.opened && !obj.state.loaded) {
				obj.state.opened = false;
				setTimeout($.proxy(function () {
					this.open_node(obj.id, false, 0);
				}, this), 0);
			}
			return node;
		},
		/**
		 * opens a node, revaling its children. If the node is not loaded it will be loaded and opened once ready.
		 * @name open_node(obj [, callback, animation])
		 * @param {mixed} obj the node to open
		 * @param {Function} callback a function to execute once the node is opened
		 * @param {Number} animation the animation duration in milliseconds when opening the node (overrides the `core.animation` setting). Use `false` for no animation.
		 * @trigger open_node.jstree, after_open.jstree, before_open.jstree
		 */
		open_node : function (obj, callback, animation) {
			var t1, t2, d, t;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.open_node(obj[t1], callback, animation);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			animation = animation === undefined ? this.settings.core.animation : animation;
			if(!this.is_closed(obj)) {
				if(callback) {
					callback.call(this, obj, false);
				}
				return false;
			}
			if(!this.is_loaded(obj)) {
				if(this.is_loading(obj)) {
					return setTimeout($.proxy(function () {
						this.open_node(obj, callback, animation);
					}, this), 500);
				}
				this.load_node(obj, function (o, ok) {
					return ok ? this.open_node(o, callback, animation) : (callback ? callback.call(this, o, false) : false);
				});
			}
			else {
				d = this.get_node(obj, true);
				t = this;
				if(d.length) {
					if(animation && d.children(".jstree-children").length) {
						d.children(".jstree-children").stop(true, true);
					}
					if(obj.children.length && !this._firstChild(d.children('.jstree-children')[0])) {
						this.draw_children(obj);
						//d = this.get_node(obj, true);
					}
					if(!animation) {
						this.trigger('before_open', { "node" : obj });
						d[0].className = d[0].className.replace('jstree-closed', 'jstree-open');
						d[0].setAttribute("aria-expanded", true);
					}
					else {
						this.trigger('before_open', { "node" : obj });
						d
							.children(".jstree-children").css("display","none").end()
							.removeClass("jstree-closed").addClass("jstree-open").attr("aria-expanded", true)
							.children(".jstree-children").stop(true, true)
								.slideDown(animation, function () {
									this.style.display = "";
									if (t.element) {
										t.trigger("after_open", { "node" : obj });
									}
								});
					}
				}
				obj.state.opened = true;
				if(callback) {
					callback.call(this, obj, true);
				}
				if(!d.length) {
					/**
					 * triggered when a node is about to be opened (if the node is supposed to be in the DOM, it will be, but it won't be visible yet)
					 * @event
					 * @name before_open.jstree
					 * @param {Object} node the opened node
					 */
					this.trigger('before_open', { "node" : obj });
				}
				/**
				 * triggered when a node is opened (if there is an animation it will not be completed yet)
				 * @event
				 * @name open_node.jstree
				 * @param {Object} node the opened node
				 */
				this.trigger('open_node', { "node" : obj });
				if(!animation || !d.length) {
					/**
					 * triggered when a node is opened and the animation is complete
					 * @event
					 * @name after_open.jstree
					 * @param {Object} node the opened node
					 */
					this.trigger("after_open", { "node" : obj });
				}
				return true;
			}
		},
		/**
		 * opens every parent of a node (node should be loaded)
		 * @name _open_to(obj)
		 * @param {mixed} obj the node to reveal
		 * @private
		 */
		_open_to : function (obj) {
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			var i, j, p = obj.parents;
			for(i = 0, j = p.length; i < j; i+=1) {
				if(i !== $.jstree.root) {
					this.open_node(p[i], false, 0);
				}
			}
			return $('#' + obj.id.replace($.jstree.idregex,'\\$&'), this.element);
		},
		/**
		 * closes a node, hiding its children
		 * @name close_node(obj [, animation])
		 * @param {mixed} obj the node to close
		 * @param {Number} animation the animation duration in milliseconds when closing the node (overrides the `core.animation` setting). Use `false` for no animation.
		 * @trigger close_node.jstree, after_close.jstree
		 */
		close_node : function (obj, animation) {
			var t1, t2, t, d;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.close_node(obj[t1], animation);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			if(this.is_closed(obj)) {
				return false;
			}
			animation = animation === undefined ? this.settings.core.animation : animation;
			t = this;
			d = this.get_node(obj, true);

			obj.state.opened = false;
			/**
			 * triggered when a node is closed (if there is an animation it will not be complete yet)
			 * @event
			 * @name close_node.jstree
			 * @param {Object} node the closed node
			 */
			this.trigger('close_node',{ "node" : obj });
			if(!d.length) {
				/**
				 * triggered when a node is closed and the animation is complete
				 * @event
				 * @name after_close.jstree
				 * @param {Object} node the closed node
				 */
				this.trigger("after_close", { "node" : obj });
			}
			else {
				if(!animation) {
					d[0].className = d[0].className.replace('jstree-open', 'jstree-closed');
					d.attr("aria-expanded", false).children('.jstree-children').remove();
					this.trigger("after_close", { "node" : obj });
				}
				else {
					d
						.children(".jstree-children").attr("style","display:block !important").end()
						.removeClass("jstree-open").addClass("jstree-closed").attr("aria-expanded", false)
						.children(".jstree-children").stop(true, true).slideUp(animation, function () {
							this.style.display = "";
							d.children('.jstree-children').remove();
							if (t.element) {
								t.trigger("after_close", { "node" : obj });
							}
						});
				}
			}
		},
		/**
		 * toggles a node - closing it if it is open, opening it if it is closed
		 * @name toggle_node(obj)
		 * @param {mixed} obj the node to toggle
		 */
		toggle_node : function (obj) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.toggle_node(obj[t1]);
				}
				return true;
			}
			if(this.is_closed(obj)) {
				return this.open_node(obj);
			}
			if(this.is_open(obj)) {
				return this.close_node(obj);
			}
		},
		/**
		 * opens all nodes within a node (or the tree), revaling their children. If the node is not loaded it will be loaded and opened once ready.
		 * @name open_all([obj, animation, original_obj])
		 * @param {mixed} obj the node to open recursively, omit to open all nodes in the tree
		 * @param {Number} animation the animation duration in milliseconds when opening the nodes, the default is no animation
		 * @param {jQuery} reference to the node that started the process (internal use)
		 * @trigger open_all.jstree
		 */
		open_all : function (obj, animation, original_obj) {
			if(!obj) { obj = $.jstree.root; }
			obj = this.get_node(obj);
			if(!obj) { return false; }
			var dom = obj.id === $.jstree.root ? this.get_container_ul() : this.get_node(obj, true), i, j, _this;
			if(!dom.length) {
				for(i = 0, j = obj.children_d.length; i < j; i++) {
					if(this.is_closed(this._model.data[obj.children_d[i]])) {
						this._model.data[obj.children_d[i]].state.opened = true;
					}
				}
				return this.trigger('open_all', { "node" : obj });
			}
			original_obj = original_obj || dom;
			_this = this;
			dom = this.is_closed(obj) ? dom.find('.jstree-closed').addBack() : dom.find('.jstree-closed');
			dom.each(function () {
				_this.open_node(
					this,
					function(node, status) { if(status && this.is_parent(node)) { this.open_all(node, animation, original_obj); } },
					animation || 0
				);
			});
			if(original_obj.find('.jstree-closed').length === 0) {
				/**
				 * triggered when an `open_all` call completes
				 * @event
				 * @name open_all.jstree
				 * @param {Object} node the opened node
				 */
				this.trigger('open_all', { "node" : this.get_node(original_obj) });
			}
		},
		/**
		 * closes all nodes within a node (or the tree), revaling their children
		 * @name close_all([obj, animation])
		 * @param {mixed} obj the node to close recursively, omit to close all nodes in the tree
		 * @param {Number} animation the animation duration in milliseconds when closing the nodes, the default is no animation
		 * @trigger close_all.jstree
		 */
		close_all : function (obj, animation) {
			if(!obj) { obj = $.jstree.root; }
			obj = this.get_node(obj);
			if(!obj) { return false; }
			var dom = obj.id === $.jstree.root ? this.get_container_ul() : this.get_node(obj, true),
				_this = this, i, j;
			if(dom.length) {
				dom = this.is_open(obj) ? dom.find('.jstree-open').addBack() : dom.find('.jstree-open');
				$(dom.get().reverse()).each(function () { _this.close_node(this, animation || 0); });
			}
			for(i = 0, j = obj.children_d.length; i < j; i++) {
				this._model.data[obj.children_d[i]].state.opened = false;
			}
			/**
			 * triggered when an `close_all` call completes
			 * @event
			 * @name close_all.jstree
			 * @param {Object} node the closed node
			 */
			this.trigger('close_all', { "node" : obj });
		},
		/**
		 * checks if a node is disabled (not selectable)
		 * @name is_disabled(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		is_disabled : function (obj) {
			obj = this.get_node(obj);
			return obj && obj.state && obj.state.disabled;
		},
		/**
		 * enables a node - so that it can be selected
		 * @name enable_node(obj)
		 * @param {mixed} obj the node to enable
		 * @trigger enable_node.jstree
		 */
		enable_node : function (obj) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.enable_node(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			obj.state.disabled = false;
			this.get_node(obj,true).children('.jstree-anchor').removeClass('jstree-disabled').attr('aria-disabled', false);
			/**
			 * triggered when an node is enabled
			 * @event
			 * @name enable_node.jstree
			 * @param {Object} node the enabled node
			 */
			this.trigger('enable_node', { 'node' : obj });
		},
		/**
		 * disables a node - so that it can not be selected
		 * @name disable_node(obj)
		 * @param {mixed} obj the node to disable
		 * @trigger disable_node.jstree
		 */
		disable_node : function (obj) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.disable_node(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			obj.state.disabled = true;
			this.get_node(obj,true).children('.jstree-anchor').addClass('jstree-disabled').attr('aria-disabled', true);
			/**
			 * triggered when an node is disabled
			 * @event
			 * @name disable_node.jstree
			 * @param {Object} node the disabled node
			 */
			this.trigger('disable_node', { 'node' : obj });
		},
		/**
		 * determines if a node is hidden
		 * @name is_hidden(obj)
		 * @param {mixed} obj the node
		 */
		is_hidden : function (obj) {
			obj = this.get_node(obj);
			return obj.state.hidden === true;
		},
		/**
		 * hides a node - it is still in the structure but will not be visible
		 * @name hide_node(obj)
		 * @param {mixed} obj the node to hide
		 * @param {Boolean} skip_redraw internal parameter controlling if redraw is called
		 * @trigger hide_node.jstree
		 */
		hide_node : function (obj, skip_redraw) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.hide_node(obj[t1], true);
				}
				if (!skip_redraw) {
					this.redraw();
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			if(!obj.state.hidden) {
				obj.state.hidden = true;
				this._node_changed(obj.parent);
				if(!skip_redraw) {
					this.redraw();
				}
				/**
				 * triggered when an node is hidden
				 * @event
				 * @name hide_node.jstree
				 * @param {Object} node the hidden node
				 */
				this.trigger('hide_node', { 'node' : obj });
			}
		},
		/**
		 * shows a node
		 * @name show_node(obj)
		 * @param {mixed} obj the node to show
		 * @param {Boolean} skip_redraw internal parameter controlling if redraw is called
		 * @trigger show_node.jstree
		 */
		show_node : function (obj, skip_redraw) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.show_node(obj[t1], true);
				}
				if (!skip_redraw) {
					this.redraw();
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			if(obj.state.hidden) {
				obj.state.hidden = false;
				this._node_changed(obj.parent);
				if(!skip_redraw) {
					this.redraw();
				}
				/**
				 * triggered when an node is shown
				 * @event
				 * @name show_node.jstree
				 * @param {Object} node the shown node
				 */
				this.trigger('show_node', { 'node' : obj });
			}
		},
		/**
		 * hides all nodes
		 * @name hide_all()
		 * @trigger hide_all.jstree
		 */
		hide_all : function (skip_redraw) {
			var i, m = this._model.data, ids = [];
			for(i in m) {
				if(m.hasOwnProperty(i) && i !== $.jstree.root && !m[i].state.hidden) {
					m[i].state.hidden = true;
					ids.push(i);
				}
			}
			this._model.force_full_redraw = true;
			if(!skip_redraw) {
				this.redraw();
			}
			/**
			 * triggered when all nodes are hidden
			 * @event
			 * @name hide_all.jstree
			 * @param {Array} nodes the IDs of all hidden nodes
			 */
			this.trigger('hide_all', { 'nodes' : ids });
			return ids;
		},
		/**
		 * shows all nodes
		 * @name show_all()
		 * @trigger show_all.jstree
		 */
		show_all : function (skip_redraw) {
			var i, m = this._model.data, ids = [];
			for(i in m) {
				if(m.hasOwnProperty(i) && i !== $.jstree.root && m[i].state.hidden) {
					m[i].state.hidden = false;
					ids.push(i);
				}
			}
			this._model.force_full_redraw = true;
			if(!skip_redraw) {
				this.redraw();
			}
			/**
			 * triggered when all nodes are shown
			 * @event
			 * @name show_all.jstree
			 * @param {Array} nodes the IDs of all shown nodes
			 */
			this.trigger('show_all', { 'nodes' : ids });
			return ids;
		},
		/**
		 * called when a node is selected by the user. Used internally.
		 * @private
		 * @name activate_node(obj, e)
		 * @param {mixed} obj the node
		 * @param {Object} e the related event
		 * @trigger activate_node.jstree, changed.jstree
		 */
		activate_node : function (obj, e) {
			if(this.is_disabled(obj)) {
				return false;
			}
			if(!e || typeof e !== 'object') {
				e = {};
			}

			// ensure last_clicked is still in the DOM, make it fresh (maybe it was moved?) and make sure it is still selected, if not - make last_clicked the last selected node
			this._data.core.last_clicked = this._data.core.last_clicked && this._data.core.last_clicked.id !== undefined ? this.get_node(this._data.core.last_clicked.id) : null;
			if(this._data.core.last_clicked && !this._data.core.last_clicked.state.selected) { this._data.core.last_clicked = null; }
			if(!this._data.core.last_clicked && this._data.core.selected.length) { this._data.core.last_clicked = this.get_node(this._data.core.selected[this._data.core.selected.length - 1]); }

			if(!this.settings.core.multiple || (!e.metaKey && !e.ctrlKey && !e.shiftKey) || (e.shiftKey && (!this._data.core.last_clicked || !this.get_parent(obj) || this.get_parent(obj) !== this._data.core.last_clicked.parent ) )) {
				if(!this.settings.core.multiple && (e.metaKey || e.ctrlKey || e.shiftKey) && this.is_selected(obj)) {
					this.deselect_node(obj, false, e);
				}
				else {
					this.deselect_all(true);
					this.select_node(obj, false, false, e);
					this._data.core.last_clicked = this.get_node(obj);
				}
			}
			else {
				if(e.shiftKey) {
					var o = this.get_node(obj).id,
						l = this._data.core.last_clicked.id,
						p = this.get_node(this._data.core.last_clicked.parent).children,
						c = false,
						i, j;
					for(i = 0, j = p.length; i < j; i += 1) {
						// separate IFs work whem o and l are the same
						if(p[i] === o) {
							c = !c;
						}
						if(p[i] === l) {
							c = !c;
						}
						if(!this.is_disabled(p[i]) && (c || p[i] === o || p[i] === l)) {
							if (!this.is_hidden(p[i])) {
								this.select_node(p[i], true, false, e);
							}
						}
						else {
							this.deselect_node(p[i], true, e);
						}
					}
					this.trigger('changed', { 'action' : 'select_node', 'node' : this.get_node(obj), 'selected' : this._data.core.selected, 'event' : e });
				}
				else {
					if(!this.is_selected(obj)) {
						this.select_node(obj, false, false, e);
					}
					else {
						this.deselect_node(obj, false, e);
					}
				}
			}
			/**
			 * triggered when an node is clicked or intercated with by the user
			 * @event
			 * @name activate_node.jstree
			 * @param {Object} node
			 * @param {Object} event the ooriginal event (if any) which triggered the call (may be an empty object)
			 */
			this.trigger('activate_node', { 'node' : this.get_node(obj), 'event' : e });
		},
		/**
		 * applies the hover state on a node, called when a node is hovered by the user. Used internally.
		 * @private
		 * @name hover_node(obj)
		 * @param {mixed} obj
		 * @trigger hover_node.jstree
		 */
		hover_node : function (obj) {
			obj = this.get_node(obj, true);
			if(!obj || !obj.length || obj.children('.jstree-hovered').length) {
				return false;
			}
			var o = this.element.find('.jstree-hovered'), t = this.element;
			if(o && o.length) { this.dehover_node(o); }

			obj.children('.jstree-anchor').addClass('jstree-hovered');
			/**
			 * triggered when an node is hovered
			 * @event
			 * @name hover_node.jstree
			 * @param {Object} node
			 */
			this.trigger('hover_node', { 'node' : this.get_node(obj) });
			setTimeout(function () { t.attr('aria-activedescendant', obj[0].id); }, 0);
		},
		/**
		 * removes the hover state from a nodecalled when a node is no longer hovered by the user. Used internally.
		 * @private
		 * @name dehover_node(obj)
		 * @param {mixed} obj
		 * @trigger dehover_node.jstree
		 */
		dehover_node : function (obj) {
			obj = this.get_node(obj, true);
			if(!obj || !obj.length || !obj.children('.jstree-hovered').length) {
				return false;
			}
			obj.children('.jstree-anchor').removeClass('jstree-hovered');
			/**
			 * triggered when an node is no longer hovered
			 * @event
			 * @name dehover_node.jstree
			 * @param {Object} node
			 */
			this.trigger('dehover_node', { 'node' : this.get_node(obj) });
		},
		/**
		 * select a node
		 * @name select_node(obj [, supress_event, prevent_open])
		 * @param {mixed} obj an array can be used to select multiple nodes
		 * @param {Boolean} supress_event if set to `true` the `changed.jstree` event won't be triggered
		 * @param {Boolean} prevent_open if set to `true` parents of the selected node won't be opened
		 * @trigger select_node.jstree, changed.jstree
		 */
		select_node : function (obj, supress_event, prevent_open, e) {
			var dom, t1, t2, th;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.select_node(obj[t1], supress_event, prevent_open, e);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			dom = this.get_node(obj, true);
			if(!obj.state.selected) {
				obj.state.selected = true;
				this._data.core.selected.push(obj.id);
				if(!prevent_open) {
					dom = this._open_to(obj);
				}
				if(dom && dom.length) {
					dom.attr('aria-selected', true).children('.jstree-anchor').addClass('jstree-clicked');
				}
				/**
				 * triggered when an node is selected
				 * @event
				 * @name select_node.jstree
				 * @param {Object} node
				 * @param {Array} selected the current selection
				 * @param {Object} event the event (if any) that triggered this select_node
				 */
				this.trigger('select_node', { 'node' : obj, 'selected' : this._data.core.selected, 'event' : e });
				if(!supress_event) {
					/**
					 * triggered when selection changes
					 * @event
					 * @name changed.jstree
					 * @param {Object} node
					 * @param {Object} action the action that caused the selection to change
					 * @param {Array} selected the current selection
					 * @param {Object} event the event (if any) that triggered this changed event
					 */
					this.trigger('changed', { 'action' : 'select_node', 'node' : obj, 'selected' : this._data.core.selected, 'event' : e });
				}
			}
		},
		/**
		 * deselect a node
		 * @name deselect_node(obj [, supress_event])
		 * @param {mixed} obj an array can be used to deselect multiple nodes
		 * @param {Boolean} supress_event if set to `true` the `changed.jstree` event won't be triggered
		 * @trigger deselect_node.jstree, changed.jstree
		 */
		deselect_node : function (obj, supress_event, e) {
			var t1, t2, dom;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.deselect_node(obj[t1], supress_event, e);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			dom = this.get_node(obj, true);
			if(obj.state.selected) {
				obj.state.selected = false;
				this._data.core.selected = $.vakata.array_remove_item(this._data.core.selected, obj.id);
				if(dom.length) {
					dom.attr('aria-selected', false).children('.jstree-anchor').removeClass('jstree-clicked');
				}
				/**
				 * triggered when an node is deselected
				 * @event
				 * @name deselect_node.jstree
				 * @param {Object} node
				 * @param {Array} selected the current selection
				 * @param {Object} event the event (if any) that triggered this deselect_node
				 */
				this.trigger('deselect_node', { 'node' : obj, 'selected' : this._data.core.selected, 'event' : e });
				if(!supress_event) {
					this.trigger('changed', { 'action' : 'deselect_node', 'node' : obj, 'selected' : this._data.core.selected, 'event' : e });
				}
			}
		},
		/**
		 * select all nodes in the tree
		 * @name select_all([supress_event])
		 * @param {Boolean} supress_event if set to `true` the `changed.jstree` event won't be triggered
		 * @trigger select_all.jstree, changed.jstree
		 */
		select_all : function (supress_event) {
			var tmp = this._data.core.selected.concat([]), i, j;
			this._data.core.selected = this._model.data[$.jstree.root].children_d.concat();
			for(i = 0, j = this._data.core.selected.length; i < j; i++) {
				if(this._model.data[this._data.core.selected[i]]) {
					this._model.data[this._data.core.selected[i]].state.selected = true;
				}
			}
			this.redraw(true);
			/**
			 * triggered when all nodes are selected
			 * @event
			 * @name select_all.jstree
			 * @param {Array} selected the current selection
			 */
			this.trigger('select_all', { 'selected' : this._data.core.selected });
			if(!supress_event) {
				this.trigger('changed', { 'action' : 'select_all', 'selected' : this._data.core.selected, 'old_selection' : tmp });
			}
		},
		/**
		 * deselect all selected nodes
		 * @name deselect_all([supress_event])
		 * @param {Boolean} supress_event if set to `true` the `changed.jstree` event won't be triggered
		 * @trigger deselect_all.jstree, changed.jstree
		 */
		deselect_all : function (supress_event) {
			var tmp = this._data.core.selected.concat([]), i, j;
			for(i = 0, j = this._data.core.selected.length; i < j; i++) {
				if(this._model.data[this._data.core.selected[i]]) {
					this._model.data[this._data.core.selected[i]].state.selected = false;
				}
			}
			this._data.core.selected = [];
			this.element.find('.jstree-clicked').removeClass('jstree-clicked').parent().attr('aria-selected', false);
			/**
			 * triggered when all nodes are deselected
			 * @event
			 * @name deselect_all.jstree
			 * @param {Object} node the previous selection
			 * @param {Array} selected the current selection
			 */
			this.trigger('deselect_all', { 'selected' : this._data.core.selected, 'node' : tmp });
			if(!supress_event) {
				this.trigger('changed', { 'action' : 'deselect_all', 'selected' : this._data.core.selected, 'old_selection' : tmp });
			}
		},
		/**
		 * checks if a node is selected
		 * @name is_selected(obj)
		 * @param  {mixed}  obj
		 * @return {Boolean}
		 */
		is_selected : function (obj) {
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			return obj.state.selected;
		},
		/**
		 * get an array of all selected nodes
		 * @name get_selected([full])
		 * @param  {mixed}  full if set to `true` the returned array will consist of the full node objects, otherwise - only IDs will be returned
		 * @return {Array}
		 */
		get_selected : function (full) {
			return full ? $.map(this._data.core.selected, $.proxy(function (i) { return this.get_node(i); }, this)) : this._data.core.selected.slice();
		},
		/**
		 * get an array of all top level selected nodes (ignoring children of selected nodes)
		 * @name get_top_selected([full])
		 * @param  {mixed}  full if set to `true` the returned array will consist of the full node objects, otherwise - only IDs will be returned
		 * @return {Array}
		 */
		get_top_selected : function (full) {
			var tmp = this.get_selected(true),
				obj = {}, i, j, k, l;
			for(i = 0, j = tmp.length; i < j; i++) {
				obj[tmp[i].id] = tmp[i];
			}
			for(i = 0, j = tmp.length; i < j; i++) {
				for(k = 0, l = tmp[i].children_d.length; k < l; k++) {
					if(obj[tmp[i].children_d[k]]) {
						delete obj[tmp[i].children_d[k]];
					}
				}
			}
			tmp = [];
			for(i in obj) {
				if(obj.hasOwnProperty(i)) {
					tmp.push(i);
				}
			}
			return full ? $.map(tmp, $.proxy(function (i) { return this.get_node(i); }, this)) : tmp;
		},
		/**
		 * get an array of all bottom level selected nodes (ignoring selected parents)
		 * @name get_bottom_selected([full])
		 * @param  {mixed}  full if set to `true` the returned array will consist of the full node objects, otherwise - only IDs will be returned
		 * @return {Array}
		 */
		get_bottom_selected : function (full) {
			var tmp = this.get_selected(true),
				obj = [], i, j;
			for(i = 0, j = tmp.length; i < j; i++) {
				if(!tmp[i].children.length) {
					obj.push(tmp[i].id);
				}
			}
			return full ? $.map(obj, $.proxy(function (i) { return this.get_node(i); }, this)) : obj;
		},
		/**
		 * gets the current state of the tree so that it can be restored later with `set_state(state)`. Used internally.
		 * @name get_state()
		 * @private
		 * @return {Object}
		 */
		get_state : function () {
			var state	= {
				'core' : {
					'open' : [],
					'scroll' : {
						'left' : this.element.scrollLeft(),
						'top' : this.element.scrollTop()
					},
					/*!
					'themes' : {
						'name' : this.get_theme(),
						'icons' : this._data.core.themes.icons,
						'dots' : this._data.core.themes.dots
					},
					*/
					'selected' : []
				}
			}, i;
			for(i in this._model.data) {
				if(this._model.data.hasOwnProperty(i)) {
					if(i !== $.jstree.root) {
						if(this._model.data[i].state.opened) {
							state.core.open.push(i);
						}
						if(this._model.data[i].state.selected) {
							state.core.selected.push(i);
						}
					}
				}
			}
			return state;
		},
		/**
		 * sets the state of the tree. Used internally.
		 * @name set_state(state [, callback])
		 * @private
		 * @param {Object} state the state to restore. Keep in mind this object is passed by reference and jstree will modify it.
		 * @param {Function} callback an optional function to execute once the state is restored.
		 * @trigger set_state.jstree
		 */
		set_state : function (state, callback) {
			if(state) {
				if(state.core) {
					var res, n, t, _this, i;
					if(state.core.open) {
						if(!$.isArray(state.core.open) || !state.core.open.length) {
							delete state.core.open;
							this.set_state(state, callback);
						}
						else {
							this._load_nodes(state.core.open, function (nodes) {
								this.open_node(nodes, false, 0);
								delete state.core.open;
								this.set_state(state, callback);
							});
						}
						return false;
					}
					if(state.core.scroll) {
						if(state.core.scroll && state.core.scroll.left !== undefined) {
							this.element.scrollLeft(state.core.scroll.left);
						}
						if(state.core.scroll && state.core.scroll.top !== undefined) {
							this.element.scrollTop(state.core.scroll.top);
						}
						delete state.core.scroll;
						this.set_state(state, callback);
						return false;
					}
					if(state.core.selected) {
						_this = this;
						this.deselect_all();
						$.each(state.core.selected, function (i, v) {
							_this.select_node(v, false, true);
						});
						delete state.core.selected;
						this.set_state(state, callback);
						return false;
					}
					for(i in state) {
						if(state.hasOwnProperty(i) && i !== "core" && $.inArray(i, this.settings.plugins) === -1) {
							delete state[i];
						}
					}
					if($.isEmptyObject(state.core)) {
						delete state.core;
						this.set_state(state, callback);
						return false;
					}
				}
				if($.isEmptyObject(state)) {
					state = null;
					if(callback) { callback.call(this); }
					/**
					 * triggered when a `set_state` call completes
					 * @event
					 * @name set_state.jstree
					 */
					this.trigger('set_state');
					return false;
				}
				return true;
			}
			return false;
		},
		/**
		 * refreshes the tree - all nodes are reloaded with calls to `load_node`.
		 * @name refresh()
		 * @param {Boolean} skip_loading an option to skip showing the loading indicator
		 * @param {Mixed} forget_state if set to `true` state will not be reapplied, if set to a function (receiving the current state as argument) the result of that function will be used as state
		 * @trigger refresh.jstree
		 */
		refresh : function (skip_loading, forget_state) {
			this._data.core.state = forget_state === true ? {} : this.get_state();
			if(forget_state && $.isFunction(forget_state)) { this._data.core.state = forget_state.call(this, this._data.core.state); }
			this._cnt = 0;
			this._model.data = {};
			this._model.data[$.jstree.root] = {
				id : $.jstree.root,
				parent : null,
				parents : [],
				children : [],
				children_d : [],
				state : { loaded : false }
			};
			this._data.core.selected = [];
			this._data.core.last_clicked = null;
			this._data.core.focused = null;

			var c = this.get_container_ul()[0].className;
			if(!skip_loading) {
				this.element.html("<"+"ul class='"+c+"' role='group'><"+"li class='jstree-initial-node jstree-loading jstree-leaf jstree-last' role='treeitem' id='j"+this._id+"_loading'><i class='jstree-icon jstree-ocl'></i><"+"a class='jstree-anchor' href='#'><i class='jstree-icon jstree-themeicon-hidden'></i>" + this.get_string("Loading ...") + "</a></li></ul>");
				this.element.attr('aria-activedescendant','j'+this._id+'_loading');
			}
			this.load_node($.jstree.root, function (o, s) {
				if(s) {
					this.get_container_ul()[0].className = c;
					if(this._firstChild(this.get_container_ul()[0])) {
						this.element.attr('aria-activedescendant',this._firstChild(this.get_container_ul()[0]).id);
					}
					this.set_state($.extend(true, {}, this._data.core.state), function () {
						/**
						 * triggered when a `refresh` call completes
						 * @event
						 * @name refresh.jstree
						 */
						this.trigger('refresh');
					});
				}
				this._data.core.state = null;
			});
		},
		/**
		 * refreshes a node in the tree (reload its children) all opened nodes inside that node are reloaded with calls to `load_node`.
		 * @name refresh_node(obj)
		 * @param  {mixed} obj the node
		 * @trigger refresh_node.jstree
		 */
		refresh_node : function (obj) {
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			var opened = [], to_load = [], s = this._data.core.selected.concat([]);
			to_load.push(obj.id);
			if(obj.state.opened === true) { opened.push(obj.id); }
			this.get_node(obj, true).find('.jstree-open').each(function() { to_load.push(this.id); opened.push(this.id); });
			this._load_nodes(to_load, $.proxy(function (nodes) {
				this.open_node(opened, false, 0);
				this.select_node(s);
				/**
				 * triggered when a node is refreshed
				 * @event
				 * @name refresh_node.jstree
				 * @param {Object} node - the refreshed node
				 * @param {Array} nodes - an array of the IDs of the nodes that were reloaded
				 */
				this.trigger('refresh_node', { 'node' : obj, 'nodes' : nodes });
			}, this), false, true);
		},
		/**
		 * set (change) the ID of a node
		 * @name set_id(obj, id)
		 * @param  {mixed} obj the node
		 * @param  {String} id the new ID
		 * @return {Boolean}
		 * @trigger set_id.jstree
		 */
		set_id : function (obj, id) {
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			var i, j, m = this._model.data, old = obj.id;
			id = id.toString();
			// update parents (replace current ID with new one in children and children_d)
			m[obj.parent].children[$.inArray(obj.id, m[obj.parent].children)] = id;
			for(i = 0, j = obj.parents.length; i < j; i++) {
				m[obj.parents[i]].children_d[$.inArray(obj.id, m[obj.parents[i]].children_d)] = id;
			}
			// update children (replace current ID with new one in parent and parents)
			for(i = 0, j = obj.children.length; i < j; i++) {
				m[obj.children[i]].parent = id;
			}
			for(i = 0, j = obj.children_d.length; i < j; i++) {
				m[obj.children_d[i]].parents[$.inArray(obj.id, m[obj.children_d[i]].parents)] = id;
			}
			i = $.inArray(obj.id, this._data.core.selected);
			if(i !== -1) { this._data.core.selected[i] = id; }
			// update model and obj itself (obj.id, this._model.data[KEY])
			i = this.get_node(obj.id, true);
			if(i) {
				i.attr('id', id); //.children('.jstree-anchor').attr('id', id + '_anchor').end().attr('aria-labelledby', id + '_anchor');
				if(this.element.attr('aria-activedescendant') === obj.id) {
					this.element.attr('aria-activedescendant', id);
				}
			}
			delete m[obj.id];
			obj.id = id;
			obj.li_attr.id = id;
			m[id] = obj;
			/**
			 * triggered when a node id value is changed
			 * @event
			 * @name set_id.jstree
			 * @param {Object} node
			 * @param {String} old the old id
			 */
			this.trigger('set_id',{ "node" : obj, "new" : obj.id, "old" : old });
			return true;
		},
		/**
		 * get the text value of a node
		 * @name get_text(obj)
		 * @param  {mixed} obj the node
		 * @return {String}
		 */
		get_text : function (obj) {
			obj = this.get_node(obj);
			return (!obj || obj.id === $.jstree.root) ? false : obj.text;
		},
		/**
		 * set the text value of a node. Used internally, please use `rename_node(obj, val)`.
		 * @private
		 * @name set_text(obj, val)
		 * @param  {mixed} obj the node, you can pass an array to set the text on multiple nodes
		 * @param  {String} val the new text value
		 * @return {Boolean}
		 * @trigger set_text.jstree
		 */
		set_text : function (obj, val) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.set_text(obj[t1], val);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			obj.text = val;
			if(this.get_node(obj, true).length) {
				this.redraw_node(obj.id);
			}
			/**
			 * triggered when a node text value is changed
			 * @event
			 * @name set_text.jstree
			 * @param {Object} obj
			 * @param {String} text the new value
			 */
			this.trigger('set_text',{ "obj" : obj, "text" : val });
			return true;
		},
		/**
		 * gets a JSON representation of a node (or the whole tree)
		 * @name get_json([obj, options])
		 * @param  {mixed} obj
		 * @param  {Object} options
		 * @param  {Boolean} options.no_state do not return state information
		 * @param  {Boolean} options.no_id do not return ID
		 * @param  {Boolean} options.no_children do not include children
		 * @param  {Boolean} options.no_data do not include node data
		 * @param  {Boolean} options.no_li_attr do not include LI attributes
		 * @param  {Boolean} options.no_a_attr do not include A attributes
		 * @param  {Boolean} options.flat return flat JSON instead of nested
		 * @return {Object}
		 */
		get_json : function (obj, options, flat) {
			obj = this.get_node(obj || $.jstree.root);
			if(!obj) { return false; }
			if(options && options.flat && !flat) { flat = []; }
			var tmp = {
				'id' : obj.id,
				'text' : obj.text,
				'icon' : this.get_icon(obj),
				'li_attr' : $.extend(true, {}, obj.li_attr),
				'a_attr' : $.extend(true, {}, obj.a_attr),
				'state' : {},
				'data' : options && options.no_data ? false : $.extend(true, {}, obj.data)
				//( this.get_node(obj, true).length ? this.get_node(obj, true).data() : obj.data ),
			}, i, j;
			if(options && options.flat) {
				tmp.parent = obj.parent;
			}
			else {
				tmp.children = [];
			}
			if(!options || !options.no_state) {
				for(i in obj.state) {
					if(obj.state.hasOwnProperty(i)) {
						tmp.state[i] = obj.state[i];
					}
				}
			} else {
				delete tmp.state;
			}
			if(options && options.no_li_attr) {
				delete tmp.li_attr;
			}
			if(options && options.no_a_attr) {
				delete tmp.a_attr;
			}
			if(options && options.no_id) {
				delete tmp.id;
				if(tmp.li_attr && tmp.li_attr.id) {
					delete tmp.li_attr.id;
				}
				if(tmp.a_attr && tmp.a_attr.id) {
					delete tmp.a_attr.id;
				}
			}
			if(options && options.flat && obj.id !== $.jstree.root) {
				flat.push(tmp);
			}
			if(!options || !options.no_children) {
				for(i = 0, j = obj.children.length; i < j; i++) {
					if(options && options.flat) {
						this.get_json(obj.children[i], options, flat);
					}
					else {
						tmp.children.push(this.get_json(obj.children[i], options));
					}
				}
			}
			return options && options.flat ? flat : (obj.id === $.jstree.root ? tmp.children : tmp);
		},
		/**
		 * create a new node (do not confuse with load_node)
		 * @name create_node([par, node, pos, callback, is_loaded])
		 * @param  {mixed}   par       the parent node (to create a root node use either "#" (string) or `null`)
		 * @param  {mixed}   node      the data for the new node (a valid JSON object, or a simple string with the name)
		 * @param  {mixed}   pos       the index at which to insert the node, "first" and "last" are also supported, default is "last"
		 * @param  {Function} callback a function to be called once the node is created
		 * @param  {Boolean} is_loaded internal argument indicating if the parent node was succesfully loaded
		 * @return {String}            the ID of the newly create node
		 * @trigger model.jstree, create_node.jstree
		 */
		create_node : function (par, node, pos, callback, is_loaded) {
			if(par === null) { par = $.jstree.root; }
			par = this.get_node(par);
			if(!par) { return false; }
			pos = pos === undefined ? "last" : pos;
			if(!pos.toString().match(/^(before|after)$/) && !is_loaded && !this.is_loaded(par)) {
				return this.load_node(par, function () { this.create_node(par, node, pos, callback, true); });
			}
			if(!node) { node = { "text" : this.get_string('New node') }; }
			if(typeof node === "string") { node = { "text" : node }; }
			if(node.text === undefined) { node.text = this.get_string('New node'); }
			var tmp, dpc, i, j;

			if(par.id === $.jstree.root) {
				if(pos === "before") { pos = "first"; }
				if(pos === "after") { pos = "last"; }
			}
			switch(pos) {
				case "before":
					tmp = this.get_node(par.parent);
					pos = $.inArray(par.id, tmp.children);
					par = tmp;
					break;
				case "after" :
					tmp = this.get_node(par.parent);
					pos = $.inArray(par.id, tmp.children) + 1;
					par = tmp;
					break;
				case "inside":
				case "first":
					pos = 0;
					break;
				case "last":
					pos = par.children.length;
					break;
				default:
					if(!pos) { pos = 0; }
					break;
			}
			if(pos > par.children.length) { pos = par.children.length; }
			if(!node.id) { node.id = true; }
			if(!this.check("create_node", node, par, pos)) {
				this.settings.core.error.call(this, this._data.core.last_error);
				return false;
			}
			if(node.id === true) { delete node.id; }
			node = this._parse_model_from_json(node, par.id, par.parents.concat());
			if(!node) { return false; }
			tmp = this.get_node(node);
			dpc = [];
			dpc.push(node);
			dpc = dpc.concat(tmp.children_d);
			this.trigger('model', { "nodes" : dpc, "parent" : par.id });

			par.children_d = par.children_d.concat(dpc);
			for(i = 0, j = par.parents.length; i < j; i++) {
				this._model.data[par.parents[i]].children_d = this._model.data[par.parents[i]].children_d.concat(dpc);
			}
			node = tmp;
			tmp = [];
			for(i = 0, j = par.children.length; i < j; i++) {
				tmp[i >= pos ? i+1 : i] = par.children[i];
			}
			tmp[pos] = node.id;
			par.children = tmp;

			this.redraw_node(par, true);
			if(callback) { callback.call(this, this.get_node(node)); }
			/**
			 * triggered when a node is created
			 * @event
			 * @name create_node.jstree
			 * @param {Object} node
			 * @param {String} parent the parent's ID
			 * @param {Number} position the position of the new node among the parent's children
			 */
			this.trigger('create_node', { "node" : this.get_node(node), "parent" : par.id, "position" : pos });
			return node.id;
		},
		/**
		 * set the text value of a node
		 * @name rename_node(obj, val)
		 * @param  {mixed} obj the node, you can pass an array to rename multiple nodes to the same name
		 * @param  {String} val the new text value
		 * @return {Boolean}
		 * @trigger rename_node.jstree
		 */
		rename_node : function (obj, val) {
			var t1, t2, old;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.rename_node(obj[t1], val);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			old = obj.text;
			if(!this.check("rename_node", obj, this.get_parent(obj), val)) {
				this.settings.core.error.call(this, this._data.core.last_error);
				return false;
			}
			this.set_text(obj, val); // .apply(this, Array.prototype.slice.call(arguments))
			/**
			 * triggered when a node is renamed
			 * @event
			 * @name rename_node.jstree
			 * @param {Object} node
			 * @param {String} text the new value
			 * @param {String} old the old value
			 */
			this.trigger('rename_node', { "node" : obj, "text" : val, "old" : old });
			return true;
		},
		/**
		 * remove a node
		 * @name delete_node(obj)
		 * @param  {mixed} obj the node, you can pass an array to delete multiple nodes
		 * @return {Boolean}
		 * @trigger delete_node.jstree, changed.jstree
		 */
		delete_node : function (obj) {
			var t1, t2, par, pos, tmp, i, j, k, l, c, top, lft;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.delete_node(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			par = this.get_node(obj.parent);
			pos = $.inArray(obj.id, par.children);
			c = false;
			if(!this.check("delete_node", obj, par, pos)) {
				this.settings.core.error.call(this, this._data.core.last_error);
				return false;
			}
			if(pos !== -1) {
				par.children = $.vakata.array_remove(par.children, pos);
			}
			tmp = obj.children_d.concat([]);
			tmp.push(obj.id);
			for(i = 0, j = obj.parents.length; i < j; i++) {
				this._model.data[obj.parents[i]].children_d = $.vakata.array_filter(this._model.data[obj.parents[i]].children_d, function (v) {
					return $.inArray(v, tmp) === -1;
				});
			}
			for(k = 0, l = tmp.length; k < l; k++) {
				if(this._model.data[tmp[k]].state.selected) {
					c = true;
					break;
				}
			}
			if (c) {
				this._data.core.selected = $.vakata.array_filter(this._data.core.selected, function (v) {
					return $.inArray(v, tmp) === -1;
				});
			}
			/**
			 * triggered when a node is deleted
			 * @event
			 * @name delete_node.jstree
			 * @param {Object} node
			 * @param {String} parent the parent's ID
			 */
			this.trigger('delete_node', { "node" : obj, "parent" : par.id });
			if(c) {
				this.trigger('changed', { 'action' : 'delete_node', 'node' : obj, 'selected' : this._data.core.selected, 'parent' : par.id });
			}
			for(k = 0, l = tmp.length; k < l; k++) {
				delete this._model.data[tmp[k]];
			}
			if($.inArray(this._data.core.focused, tmp) !== -1) {
				this._data.core.focused = null;
				top = this.element[0].scrollTop;
				lft = this.element[0].scrollLeft;
				if(par.id === $.jstree.root) {
					if (this._model.data[$.jstree.root].children[0]) {
						this.get_node(this._model.data[$.jstree.root].children[0], true).children('.jstree-anchor').focus();
					}
				}
				else {
					this.get_node(par, true).children('.jstree-anchor').focus();
				}
				this.element[0].scrollTop  = top;
				this.element[0].scrollLeft = lft;
			}
			this.redraw_node(par, true);
			return true;
		},
		/**
		 * check if an operation is premitted on the tree. Used internally.
		 * @private
		 * @name check(chk, obj, par, pos)
		 * @param  {String} chk the operation to check, can be "create_node", "rename_node", "delete_node", "copy_node" or "move_node"
		 * @param  {mixed} obj the node
		 * @param  {mixed} par the parent
		 * @param  {mixed} pos the position to insert at, or if "rename_node" - the new name
		 * @param  {mixed} more some various additional information, for example if a "move_node" operations is triggered by DND this will be the hovered node
		 * @return {Boolean}
		 */
		check : function (chk, obj, par, pos, more) {
			obj = obj && obj.id ? obj : this.get_node(obj);
			par = par && par.id ? par : this.get_node(par);
			var tmp = chk.match(/^move_node|copy_node|create_node$/i) ? par : obj,
				chc = this.settings.core.check_callback;
			if(chk === "move_node" || chk === "copy_node") {
				if((!more || !more.is_multi) && (obj.id === par.id || (chk === "move_node" && $.inArray(obj.id, par.children) === pos) || $.inArray(par.id, obj.children_d) !== -1)) {
					this._data.core.last_error = { 'error' : 'check', 'plugin' : 'core', 'id' : 'core_01', 'reason' : 'Moving parent inside child', 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
					return false;
				}
			}
			if(tmp && tmp.data) { tmp = tmp.data; }
			if(tmp && tmp.functions && (tmp.functions[chk] === false || tmp.functions[chk] === true)) {
				if(tmp.functions[chk] === false) {
					this._data.core.last_error = { 'error' : 'check', 'plugin' : 'core', 'id' : 'core_02', 'reason' : 'Node data prevents function: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
				}
				return tmp.functions[chk];
			}
			if(chc === false || ($.isFunction(chc) && chc.call(this, chk, obj, par, pos, more) === false) || (chc && chc[chk] === false)) {
				this._data.core.last_error = { 'error' : 'check', 'plugin' : 'core', 'id' : 'core_03', 'reason' : 'User config for core.check_callback prevents function: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
				return false;
			}
			return true;
		},
		/**
		 * get the last error
		 * @name last_error()
		 * @return {Object}
		 */
		last_error : function () {
			return this._data.core.last_error;
		},
		/**
		 * move a node to a new parent
		 * @name move_node(obj, par [, pos, callback, is_loaded])
		 * @param  {mixed} obj the node to move, pass an array to move multiple nodes
		 * @param  {mixed} par the new parent
		 * @param  {mixed} pos the position to insert at (besides integer values, "first" and "last" are supported, as well as "before" and "after"), defaults to integer `0`
		 * @param  {function} callback a function to call once the move is completed, receives 3 arguments - the node, the new parent and the position
		 * @param  {Boolean} is_loaded internal parameter indicating if the parent node has been loaded
		 * @param  {Boolean} skip_redraw internal parameter indicating if the tree should be redrawn
		 * @param  {Boolean} instance internal parameter indicating if the node comes from another instance
		 * @trigger move_node.jstree
		 */
		move_node : function (obj, par, pos, callback, is_loaded, skip_redraw, origin) {
			var t1, t2, old_par, old_pos, new_par, old_ins, is_multi, dpc, tmp, i, j, k, l, p;

			par = this.get_node(par);
			pos = pos === undefined ? 0 : pos;
			if(!par) { return false; }
			if(!pos.toString().match(/^(before|after)$/) && !is_loaded && !this.is_loaded(par)) {
				return this.load_node(par, function () { this.move_node(obj, par, pos, callback, true, false, origin); });
			}

			if($.isArray(obj)) {
				if(obj.length === 1) {
					obj = obj[0];
				}
				else {
					//obj = obj.slice();
					for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
						if((tmp = this.move_node(obj[t1], par, pos, callback, is_loaded, false, origin))) {
							par = tmp;
							pos = "after";
						}
					}
					this.redraw();
					return true;
				}
			}
			obj = obj && obj.id ? obj : this.get_node(obj);

			if(!obj || obj.id === $.jstree.root) { return false; }

			old_par = (obj.parent || $.jstree.root).toString();
			new_par = (!pos.toString().match(/^(before|after)$/) || par.id === $.jstree.root) ? par : this.get_node(par.parent);
			old_ins = origin ? origin : (this._model.data[obj.id] ? this : $.jstree.reference(obj.id));
			is_multi = !old_ins || !old_ins._id || (this._id !== old_ins._id);
			old_pos = old_ins && old_ins._id && old_par && old_ins._model.data[old_par] && old_ins._model.data[old_par].children ? $.inArray(obj.id, old_ins._model.data[old_par].children) : -1;
			if(old_ins && old_ins._id) {
				obj = old_ins._model.data[obj.id];
			}

			if(is_multi) {
				if((tmp = this.copy_node(obj, par, pos, callback, is_loaded, false, origin))) {
					if(old_ins) { old_ins.delete_node(obj); }
					return tmp;
				}
				return false;
			}
			//var m = this._model.data;
			if(par.id === $.jstree.root) {
				if(pos === "before") { pos = "first"; }
				if(pos === "after") { pos = "last"; }
			}
			switch(pos) {
				case "before":
					pos = $.inArray(par.id, new_par.children);
					break;
				case "after" :
					pos = $.inArray(par.id, new_par.children) + 1;
					break;
				case "inside":
				case "first":
					pos = 0;
					break;
				case "last":
					pos = new_par.children.length;
					break;
				default:
					if(!pos) { pos = 0; }
					break;
			}
			if(pos > new_par.children.length) { pos = new_par.children.length; }
			if(!this.check("move_node", obj, new_par, pos, { 'core' : true, 'origin' : origin, 'is_multi' : (old_ins && old_ins._id && old_ins._id !== this._id), 'is_foreign' : (!old_ins || !old_ins._id) })) {
				this.settings.core.error.call(this, this._data.core.last_error);
				return false;
			}
			if(obj.parent === new_par.id) {
				dpc = new_par.children.concat();
				tmp = $.inArray(obj.id, dpc);
				if(tmp !== -1) {
					dpc = $.vakata.array_remove(dpc, tmp);
					if(pos > tmp) { pos--; }
				}
				tmp = [];
				for(i = 0, j = dpc.length; i < j; i++) {
					tmp[i >= pos ? i+1 : i] = dpc[i];
				}
				tmp[pos] = obj.id;
				new_par.children = tmp;
				this._node_changed(new_par.id);
				this.redraw(new_par.id === $.jstree.root);
			}
			else {
				// clean old parent and up
				tmp = obj.children_d.concat();
				tmp.push(obj.id);
				for(i = 0, j = obj.parents.length; i < j; i++) {
					dpc = [];
					p = old_ins._model.data[obj.parents[i]].children_d;
					for(k = 0, l = p.length; k < l; k++) {
						if($.inArray(p[k], tmp) === -1) {
							dpc.push(p[k]);
						}
					}
					old_ins._model.data[obj.parents[i]].children_d = dpc;
				}
				old_ins._model.data[old_par].children = $.vakata.array_remove_item(old_ins._model.data[old_par].children, obj.id);

				// insert into new parent and up
				for(i = 0, j = new_par.parents.length; i < j; i++) {
					this._model.data[new_par.parents[i]].children_d = this._model.data[new_par.parents[i]].children_d.concat(tmp);
				}
				dpc = [];
				for(i = 0, j = new_par.children.length; i < j; i++) {
					dpc[i >= pos ? i+1 : i] = new_par.children[i];
				}
				dpc[pos] = obj.id;
				new_par.children = dpc;
				new_par.children_d.push(obj.id);
				new_par.children_d = new_par.children_d.concat(obj.children_d);

				// update object
				obj.parent = new_par.id;
				tmp = new_par.parents.concat();
				tmp.unshift(new_par.id);
				p = obj.parents.length;
				obj.parents = tmp;

				// update object children
				tmp = tmp.concat();
				for(i = 0, j = obj.children_d.length; i < j; i++) {
					this._model.data[obj.children_d[i]].parents = this._model.data[obj.children_d[i]].parents.slice(0,p*-1);
					Array.prototype.push.apply(this._model.data[obj.children_d[i]].parents, tmp);
				}

				if(old_par === $.jstree.root || new_par.id === $.jstree.root) {
					this._model.force_full_redraw = true;
				}
				if(!this._model.force_full_redraw) {
					this._node_changed(old_par);
					this._node_changed(new_par.id);
				}
				if(!skip_redraw) {
					this.redraw();
				}
			}
			if(callback) { callback.call(this, obj, new_par, pos); }
			/**
			 * triggered when a node is moved
			 * @event
			 * @name move_node.jstree
			 * @param {Object} node
			 * @param {String} parent the parent's ID
			 * @param {Number} position the position of the node among the parent's children
			 * @param {String} old_parent the old parent of the node
			 * @param {Number} old_position the old position of the node
			 * @param {Boolean} is_multi do the node and new parent belong to different instances
			 * @param {jsTree} old_instance the instance the node came from
			 * @param {jsTree} new_instance the instance of the new parent
			 */
			this.trigger('move_node', { "node" : obj, "parent" : new_par.id, "position" : pos, "old_parent" : old_par, "old_position" : old_pos, 'is_multi' : (old_ins && old_ins._id && old_ins._id !== this._id), 'is_foreign' : (!old_ins || !old_ins._id), 'old_instance' : old_ins, 'new_instance' : this });
			return obj.id;
		},
		/**
		 * copy a node to a new parent
		 * @name copy_node(obj, par [, pos, callback, is_loaded])
		 * @param  {mixed} obj the node to copy, pass an array to copy multiple nodes
		 * @param  {mixed} par the new parent
		 * @param  {mixed} pos the position to insert at (besides integer values, "first" and "last" are supported, as well as "before" and "after"), defaults to integer `0`
		 * @param  {function} callback a function to call once the move is completed, receives 3 arguments - the node, the new parent and the position
		 * @param  {Boolean} is_loaded internal parameter indicating if the parent node has been loaded
		 * @param  {Boolean} skip_redraw internal parameter indicating if the tree should be redrawn
		 * @param  {Boolean} instance internal parameter indicating if the node comes from another instance
		 * @trigger model.jstree copy_node.jstree
		 */
		copy_node : function (obj, par, pos, callback, is_loaded, skip_redraw, origin) {
			var t1, t2, dpc, tmp, i, j, node, old_par, new_par, old_ins, is_multi;

			par = this.get_node(par);
			pos = pos === undefined ? 0 : pos;
			if(!par) { return false; }
			if(!pos.toString().match(/^(before|after)$/) && !is_loaded && !this.is_loaded(par)) {
				return this.load_node(par, function () { this.copy_node(obj, par, pos, callback, true, false, origin); });
			}

			if($.isArray(obj)) {
				if(obj.length === 1) {
					obj = obj[0];
				}
				else {
					//obj = obj.slice();
					for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
						if((tmp = this.copy_node(obj[t1], par, pos, callback, is_loaded, true, origin))) {
							par = tmp;
							pos = "after";
						}
					}
					this.redraw();
					return true;
				}
			}
			obj = obj && obj.id ? obj : this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }

			old_par = (obj.parent || $.jstree.root).toString();
			new_par = (!pos.toString().match(/^(before|after)$/) || par.id === $.jstree.root) ? par : this.get_node(par.parent);
			old_ins = origin ? origin : (this._model.data[obj.id] ? this : $.jstree.reference(obj.id));
			is_multi = !old_ins || !old_ins._id || (this._id !== old_ins._id);

			if(old_ins && old_ins._id) {
				obj = old_ins._model.data[obj.id];
			}

			if(par.id === $.jstree.root) {
				if(pos === "before") { pos = "first"; }
				if(pos === "after") { pos = "last"; }
			}
			switch(pos) {
				case "before":
					pos = $.inArray(par.id, new_par.children);
					break;
				case "after" :
					pos = $.inArray(par.id, new_par.children) + 1;
					break;
				case "inside":
				case "first":
					pos = 0;
					break;
				case "last":
					pos = new_par.children.length;
					break;
				default:
					if(!pos) { pos = 0; }
					break;
			}
			if(pos > new_par.children.length) { pos = new_par.children.length; }
			if(!this.check("copy_node", obj, new_par, pos, { 'core' : true, 'origin' : origin, 'is_multi' : (old_ins && old_ins._id && old_ins._id !== this._id), 'is_foreign' : (!old_ins || !old_ins._id) })) {
				this.settings.core.error.call(this, this._data.core.last_error);
				return false;
			}
			node = old_ins ? old_ins.get_json(obj, { no_id : true, no_data : true, no_state : true }) : obj;
			if(!node) { return false; }
			if(node.id === true) { delete node.id; }
			node = this._parse_model_from_json(node, new_par.id, new_par.parents.concat());
			if(!node) { return false; }
			tmp = this.get_node(node);
			if(obj && obj.state && obj.state.loaded === false) { tmp.state.loaded = false; }
			dpc = [];
			dpc.push(node);
			dpc = dpc.concat(tmp.children_d);
			this.trigger('model', { "nodes" : dpc, "parent" : new_par.id });

			// insert into new parent and up
			for(i = 0, j = new_par.parents.length; i < j; i++) {
				this._model.data[new_par.parents[i]].children_d = this._model.data[new_par.parents[i]].children_d.concat(dpc);
			}
			dpc = [];
			for(i = 0, j = new_par.children.length; i < j; i++) {
				dpc[i >= pos ? i+1 : i] = new_par.children[i];
			}
			dpc[pos] = tmp.id;
			new_par.children = dpc;
			new_par.children_d.push(tmp.id);
			new_par.children_d = new_par.children_d.concat(tmp.children_d);

			if(new_par.id === $.jstree.root) {
				this._model.force_full_redraw = true;
			}
			if(!this._model.force_full_redraw) {
				this._node_changed(new_par.id);
			}
			if(!skip_redraw) {
				this.redraw(new_par.id === $.jstree.root);
			}
			if(callback) { callback.call(this, tmp, new_par, pos); }
			/**
			 * triggered when a node is copied
			 * @event
			 * @name copy_node.jstree
			 * @param {Object} node the copied node
			 * @param {Object} original the original node
			 * @param {String} parent the parent's ID
			 * @param {Number} position the position of the node among the parent's children
			 * @param {String} old_parent the old parent of the node
			 * @param {Number} old_position the position of the original node
			 * @param {Boolean} is_multi do the node and new parent belong to different instances
			 * @param {jsTree} old_instance the instance the node came from
			 * @param {jsTree} new_instance the instance of the new parent
			 */
			this.trigger('copy_node', { "node" : tmp, "original" : obj, "parent" : new_par.id, "position" : pos, "old_parent" : old_par, "old_position" : old_ins && old_ins._id && old_par && old_ins._model.data[old_par] && old_ins._model.data[old_par].children ? $.inArray(obj.id, old_ins._model.data[old_par].children) : -1,'is_multi' : (old_ins && old_ins._id && old_ins._id !== this._id), 'is_foreign' : (!old_ins || !old_ins._id), 'old_instance' : old_ins, 'new_instance' : this });
			return tmp.id;
		},
		/**
		 * cut a node (a later call to `paste(obj)` would move the node)
		 * @name cut(obj)
		 * @param  {mixed} obj multiple objects can be passed using an array
		 * @trigger cut.jstree
		 */
		cut : function (obj) {
			if(!obj) { obj = this._data.core.selected.concat(); }
			if(!$.isArray(obj)) { obj = [obj]; }
			if(!obj.length) { return false; }
			var tmp = [], o, t1, t2;
			for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
				o = this.get_node(obj[t1]);
				if(o && o.id && o.id !== $.jstree.root) { tmp.push(o); }
			}
			if(!tmp.length) { return false; }
			ccp_node = tmp;
			ccp_inst = this;
			ccp_mode = 'move_node';
			/**
			 * triggered when nodes are added to the buffer for moving
			 * @event
			 * @name cut.jstree
			 * @param {Array} node
			 */
			this.trigger('cut', { "node" : obj });
		},
		/**
		 * copy a node (a later call to `paste(obj)` would copy the node)
		 * @name copy(obj)
		 * @param  {mixed} obj multiple objects can be passed using an array
		 * @trigger copy.jstree
		 */
		copy : function (obj) {
			if(!obj) { obj = this._data.core.selected.concat(); }
			if(!$.isArray(obj)) { obj = [obj]; }
			if(!obj.length) { return false; }
			var tmp = [], o, t1, t2;
			for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
				o = this.get_node(obj[t1]);
				if(o && o.id && o.id !== $.jstree.root) { tmp.push(o); }
			}
			if(!tmp.length) { return false; }
			ccp_node = tmp;
			ccp_inst = this;
			ccp_mode = 'copy_node';
			/**
			 * triggered when nodes are added to the buffer for copying
			 * @event
			 * @name copy.jstree
			 * @param {Array} node
			 */
			this.trigger('copy', { "node" : obj });
		},
		/**
		 * get the current buffer (any nodes that are waiting for a paste operation)
		 * @name get_buffer()
		 * @return {Object} an object consisting of `mode` ("copy_node" or "move_node"), `node` (an array of objects) and `inst` (the instance)
		 */
		get_buffer : function () {
			return { 'mode' : ccp_mode, 'node' : ccp_node, 'inst' : ccp_inst };
		},
		/**
		 * check if there is something in the buffer to paste
		 * @name can_paste()
		 * @return {Boolean}
		 */
		can_paste : function () {
			return ccp_mode !== false && ccp_node !== false; // && ccp_inst._model.data[ccp_node];
		},
		/**
		 * copy or move the previously cut or copied nodes to a new parent
		 * @name paste(obj [, pos])
		 * @param  {mixed} obj the new parent
		 * @param  {mixed} pos the position to insert at (besides integer, "first" and "last" are supported), defaults to integer `0`
		 * @trigger paste.jstree
		 */
		paste : function (obj, pos) {
			obj = this.get_node(obj);
			if(!obj || !ccp_mode || !ccp_mode.match(/^(copy_node|move_node)$/) || !ccp_node) { return false; }
			if(this[ccp_mode](ccp_node, obj, pos, false, false, false, ccp_inst)) {
				/**
				 * triggered when paste is invoked
				 * @event
				 * @name paste.jstree
				 * @param {String} parent the ID of the receiving node
				 * @param {Array} node the nodes in the buffer
				 * @param {String} mode the performed operation - "copy_node" or "move_node"
				 */
				this.trigger('paste', { "parent" : obj.id, "node" : ccp_node, "mode" : ccp_mode });
			}
			ccp_node = false;
			ccp_mode = false;
			ccp_inst = false;
		},
		/**
		 * clear the buffer of previously copied or cut nodes
		 * @name clear_buffer()
		 * @trigger clear_buffer.jstree
		 */
		clear_buffer : function () {
			ccp_node = false;
			ccp_mode = false;
			ccp_inst = false;
			/**
			 * triggered when the copy / cut buffer is cleared
			 * @event
			 * @name clear_buffer.jstree
			 */
			this.trigger('clear_buffer');
		},
		/**
		 * put a node in edit mode (input field to rename the node)
		 * @name edit(obj [, default_text, callback])
		 * @param  {mixed} obj
		 * @param  {String} default_text the text to populate the input with (if omitted or set to a non-string value the node's text value is used)
		 * @param  {Function} callback a function to be called once the text box is blurred, it is called in the instance's scope and receives the node, a status parameter (true if the rename is successful, false otherwise) and a boolean indicating if the user cancelled the edit. You can access the node's title using .text
		 */
		edit : function (obj, default_text, callback) {
			var rtl, w, a, s, t, h1, h2, fn, tmp, cancel = false;
			obj = this.get_node(obj);
			if(!obj) { return false; }
			if(this.settings.core.check_callback === false) {
				this._data.core.last_error = { 'error' : 'check', 'plugin' : 'core', 'id' : 'core_07', 'reason' : 'Could not edit node because of check_callback' };
				this.settings.core.error.call(this, this._data.core.last_error);
				return false;
			}
			tmp = obj;
			default_text = typeof default_text === 'string' ? default_text : obj.text;
			this.set_text(obj, "");
			obj = this._open_to(obj);
			tmp.text = default_text;

			rtl = this._data.core.rtl;
			w  = this.element.width();
			this._data.core.focused = tmp.id;
			a  = obj.children('.jstree-anchor').focus();
			s  = $('<span>');
			/*!
			oi = obj.children("i:visible"),
			ai = a.children("i:visible"),
			w1 = oi.width() * oi.length,
			w2 = ai.width() * ai.length,
			*/
			t  = default_text;
			h1 = $("<"+"div />", { css : { "position" : "absolute", "top" : "-200px", "left" : (rtl ? "0px" : "-1000px"), "visibility" : "hidden" } }).appendTo("body");
			h2 = $("<"+"input />", {
						"value" : t,
						"class" : "jstree-rename-input",
						// "size" : t.length,
						"css" : {
							"padding" : "0",
							"border" : "1px solid silver",
							"box-sizing" : "border-box",
							"display" : "inline-block",
							"height" : (this._data.core.li_height) + "px",
							"lineHeight" : (this._data.core.li_height) + "px",
							"width" : "150px" // will be set a bit further down
						},
						"blur" : $.proxy(function (e) {
							e.stopImmediatePropagation();
							e.preventDefault();
							var i = s.children(".jstree-rename-input"),
								v = i.val(),
								f = this.settings.core.force_text,
								nv;
							if(v === "") { v = t; }
							h1.remove();
							s.replaceWith(a);
							s.remove();
							t = f ? t : $('<div></div>').append($.parseHTML(t)).html();
							this.set_text(obj, t);
							nv = !!this.rename_node(obj, f ? $('<div></div>').text(v).text() : $('<div></div>').append($.parseHTML(v)).html());
							if(!nv) {
								this.set_text(obj, t); // move this up? and fix #483
							}
							this._data.core.focused = tmp.id;
							setTimeout($.proxy(function () {
								var node = this.get_node(tmp.id, true);
								if(node.length) {
									this._data.core.focused = tmp.id;
									node.children('.jstree-anchor').focus();
								}
							}, this), 0);
							if(callback) {
								callback.call(this, tmp, nv, cancel);
							}
							h2 = null;
						}, this),
						"keydown" : function (e) {
							var key = e.which;
							if(key === 27) {
								cancel = true;
								this.value = t;
							}
							if(key === 27 || key === 13 || key === 37 || key === 38 || key === 39 || key === 40 || key === 32) {
								e.stopImmediatePropagation();
							}
							if(key === 27 || key === 13) {
								e.preventDefault();
								this.blur();
							}
						},
						"click" : function (e) { e.stopImmediatePropagation(); },
						"mousedown" : function (e) { e.stopImmediatePropagation(); },
						"keyup" : function (e) {
							h2.width(Math.min(h1.text("pW" + this.value).width(),w));
						},
						"keypress" : function(e) {
							if(e.which === 13) { return false; }
						}
					});
				fn = {
						fontFamily		: a.css('fontFamily')		|| '',
						fontSize		: a.css('fontSize')			|| '',
						fontWeight		: a.css('fontWeight')		|| '',
						fontStyle		: a.css('fontStyle')		|| '',
						fontStretch		: a.css('fontStretch')		|| '',
						fontVariant		: a.css('fontVariant')		|| '',
						letterSpacing	: a.css('letterSpacing')	|| '',
						wordSpacing		: a.css('wordSpacing')		|| ''
				};
			s.attr('class', a.attr('class')).append(a.contents().clone()).append(h2);
			a.replaceWith(s);
			h1.css(fn);
			h2.css(fn).width(Math.min(h1.text("pW" + h2[0].value).width(),w))[0].select();
			$(document).one('mousedown.jstree touchstart.jstree dnd_start.vakata', function (e) {
				if (h2 && e.target !== h2) {
					$(h2).blur();
				}
			});
		},


		/**
		 * changes the theme
		 * @name set_theme(theme_name [, theme_url])
		 * @param {String} theme_name the name of the new theme to apply
		 * @param {mixed} theme_url  the location of the CSS file for this theme. Omit or set to `false` if you manually included the file. Set to `true` to autoload from the `core.themes.dir` directory.
		 * @trigger set_theme.jstree
		 */
		set_theme : function (theme_name, theme_url) {
			if(!theme_name) { return false; }
			if(theme_url === true) {
				var dir = this.settings.core.themes.dir;
				if(!dir) { dir = $.jstree.path + '/themes'; }
				theme_url = dir + '/' + theme_name + '/style.css';
			}
			if(theme_url && $.inArray(theme_url, themes_loaded) === -1) {
				$('head').append('<'+'link rel="stylesheet" href="' + theme_url + '" type="text/css" />');
				themes_loaded.push(theme_url);
			}
			if(this._data.core.themes.name) {
				this.element.removeClass('jstree-' + this._data.core.themes.name);
			}
			this._data.core.themes.name = theme_name;
			this.element.addClass('jstree-' + theme_name);
			this.element[this.settings.core.themes.responsive ? 'addClass' : 'removeClass' ]('jstree-' + theme_name + '-responsive');
			/**
			 * triggered when a theme is set
			 * @event
			 * @name set_theme.jstree
			 * @param {String} theme the new theme
			 */
			this.trigger('set_theme', { 'theme' : theme_name });
		},
		/**
		 * gets the name of the currently applied theme name
		 * @name get_theme()
		 * @return {String}
		 */
		get_theme : function () { return this._data.core.themes.name; },
		/**
		 * changes the theme variant (if the theme has variants)
		 * @name set_theme_variant(variant_name)
		 * @param {String|Boolean} variant_name the variant to apply (if `false` is used the current variant is removed)
		 */
		set_theme_variant : function (variant_name) {
			if(this._data.core.themes.variant) {
				this.element.removeClass('jstree-' + this._data.core.themes.name + '-' + this._data.core.themes.variant);
			}
			this._data.core.themes.variant = variant_name;
			if(variant_name) {
				this.element.addClass('jstree-' + this._data.core.themes.name + '-' + this._data.core.themes.variant);
			}
		},
		/**
		 * gets the name of the currently applied theme variant
		 * @name get_theme()
		 * @return {String}
		 */
		get_theme_variant : function () { return this._data.core.themes.variant; },
		/**
		 * shows a striped background on the container (if the theme supports it)
		 * @name show_stripes()
		 */
		show_stripes : function () {
			this._data.core.themes.stripes = true;
			this.get_container_ul().addClass("jstree-striped");
			/**
			 * triggered when stripes are shown
			 * @event
			 * @name show_stripes.jstree
			 */
			this.trigger('show_stripes');
		},
		/**
		 * hides the striped background on the container
		 * @name hide_stripes()
		 */
		hide_stripes : function () {
			this._data.core.themes.stripes = false;
			this.get_container_ul().removeClass("jstree-striped");
			/**
			 * triggered when stripes are hidden
			 * @event
			 * @name hide_stripes.jstree
			 */
			this.trigger('hide_stripes');
		},
		/**
		 * toggles the striped background on the container
		 * @name toggle_stripes()
		 */
		toggle_stripes : function () { if(this._data.core.themes.stripes) { this.hide_stripes(); } else { this.show_stripes(); } },
		/**
		 * shows the connecting dots (if the theme supports it)
		 * @name show_dots()
		 */
		show_dots : function () {
			this._data.core.themes.dots = true;
			this.get_container_ul().removeClass("jstree-no-dots");
			/**
			 * triggered when dots are shown
			 * @event
			 * @name show_dots.jstree
			 */
			this.trigger('show_dots');
		},
		/**
		 * hides the connecting dots
		 * @name hide_dots()
		 */
		hide_dots : function () {
			this._data.core.themes.dots = false;
			this.get_container_ul().addClass("jstree-no-dots");
			/**
			 * triggered when dots are hidden
			 * @event
			 * @name hide_dots.jstree
			 */
			this.trigger('hide_dots');
		},
		/**
		 * toggles the connecting dots
		 * @name toggle_dots()
		 */
		toggle_dots : function () { if(this._data.core.themes.dots) { this.hide_dots(); } else { this.show_dots(); } },
		/**
		 * show the node icons
		 * @name show_icons()
		 */
		show_icons : function () {
			this._data.core.themes.icons = true;
			this.get_container_ul().removeClass("jstree-no-icons");
			/**
			 * triggered when icons are shown
			 * @event
			 * @name show_icons.jstree
			 */
			this.trigger('show_icons');
		},
		/**
		 * hide the node icons
		 * @name hide_icons()
		 */
		hide_icons : function () {
			this._data.core.themes.icons = false;
			this.get_container_ul().addClass("jstree-no-icons");
			/**
			 * triggered when icons are hidden
			 * @event
			 * @name hide_icons.jstree
			 */
			this.trigger('hide_icons');
		},
		/**
		 * toggle the node icons
		 * @name toggle_icons()
		 */
		toggle_icons : function () { if(this._data.core.themes.icons) { this.hide_icons(); } else { this.show_icons(); } },
		/**
		 * show the node ellipsis
		 * @name show_icons()
		 */
		show_ellipsis : function () {
			this._data.core.themes.ellipsis = true;
			this.get_container_ul().addClass("jstree-ellipsis");
			/**
			 * triggered when ellisis is shown
			 * @event
			 * @name show_ellipsis.jstree
			 */
			this.trigger('show_ellipsis');
		},
		/**
		 * hide the node ellipsis
		 * @name hide_ellipsis()
		 */
		hide_ellipsis : function () {
			this._data.core.themes.ellipsis = false;
			this.get_container_ul().removeClass("jstree-ellipsis");
			/**
			 * triggered when ellisis is hidden
			 * @event
			 * @name hide_ellipsis.jstree
			 */
			this.trigger('hide_ellipsis');
		},
		/**
		 * toggle the node ellipsis
		 * @name toggle_icons()
		 */
		toggle_ellipsis : function () { if(this._data.core.themes.ellipsis) { this.hide_ellipsis(); } else { this.show_ellipsis(); } },
		/**
		 * set the node icon for a node
		 * @name set_icon(obj, icon)
		 * @param {mixed} obj
		 * @param {String} icon the new icon - can be a path to an icon or a className, if using an image that is in the current directory use a `./` prefix, otherwise it will be detected as a class
		 */
		set_icon : function (obj, icon) {
			var t1, t2, dom, old;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.set_icon(obj[t1], icon);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			old = obj.icon;
			obj.icon = icon === true || icon === null || icon === undefined || icon === '' ? true : icon;
			dom = this.get_node(obj, true).children(".jstree-anchor").children(".jstree-themeicon");
			if(icon === false) {
				this.hide_icon(obj);
			}
			else if(icon === true || icon === null || icon === undefined || icon === '') {
				dom.removeClass('jstree-themeicon-custom ' + old).css("background","").removeAttr("rel");
				if(old === false) { this.show_icon(obj); }
			}
			else if(icon.indexOf("/") === -1 && icon.indexOf(".") === -1) {
				dom.removeClass(old).css("background","");
				dom.addClass(icon + ' jstree-themeicon-custom').attr("rel",icon);
				if(old === false) { this.show_icon(obj); }
			}
			else {
				dom.removeClass(old).css("background","");
				dom.addClass('jstree-themeicon-custom').css("background", "url('" + icon + "') center center no-repeat").attr("rel",icon);
				if(old === false) { this.show_icon(obj); }
			}
			return true;
		},
		/**
		 * get the node icon for a node
		 * @name get_icon(obj)
		 * @param {mixed} obj
		 * @return {String}
		 */
		get_icon : function (obj) {
			obj = this.get_node(obj);
			return (!obj || obj.id === $.jstree.root) ? false : obj.icon;
		},
		/**
		 * hide the icon on an individual node
		 * @name hide_icon(obj)
		 * @param {mixed} obj
		 */
		hide_icon : function (obj) {
			var t1, t2;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.hide_icon(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj === $.jstree.root) { return false; }
			obj.icon = false;
			this.get_node(obj, true).children(".jstree-anchor").children(".jstree-themeicon").addClass('jstree-themeicon-hidden');
			return true;
		},
		/**
		 * show the icon on an individual node
		 * @name show_icon(obj)
		 * @param {mixed} obj
		 */
		show_icon : function (obj) {
			var t1, t2, dom;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.show_icon(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj === $.jstree.root) { return false; }
			dom = this.get_node(obj, true);
			obj.icon = dom.length ? dom.children(".jstree-anchor").children(".jstree-themeicon").attr('rel') : true;
			if(!obj.icon) { obj.icon = true; }
			dom.children(".jstree-anchor").children(".jstree-themeicon").removeClass('jstree-themeicon-hidden');
			return true;
		}
	};

	// helpers
	$.vakata = {};
	// collect attributes
	$.vakata.attributes = function(node, with_values) {
		node = $(node)[0];
		var attr = with_values ? {} : [];
		if(node && node.attributes) {
			$.each(node.attributes, function (i, v) {
				if($.inArray(v.name.toLowerCase(),['style','contenteditable','hasfocus','tabindex']) !== -1) { return; }
				if(v.value !== null && $.trim(v.value) !== '') {
					if(with_values) { attr[v.name] = v.value; }
					else { attr.push(v.name); }
				}
			});
		}
		return attr;
	};
	$.vakata.array_unique = function(array) {
		var a = [], i, j, l, o = {};
		for(i = 0, l = array.length; i < l; i++) {
			if(o[array[i]] === undefined) {
				a.push(array[i]);
				o[array[i]] = true;
			}
		}
		return a;
	};
	// remove item from array
	$.vakata.array_remove = function(array, from) {
		array.splice(from, 1);
		return array;
		//var rest = array.slice((to || from) + 1 || array.length);
		//array.length = from < 0 ? array.length + from : from;
		//array.push.apply(array, rest);
		//return array;
	};
	// remove item from array
	$.vakata.array_remove_item = function(array, item) {
		var tmp = $.inArray(item, array);
		return tmp !== -1 ? $.vakata.array_remove(array, tmp) : array;
	};
	$.vakata.array_filter = function(c,a,b,d,e) {
		if (c.filter) {
			return c.filter(a, b);
		}
		d=[];
		for (e in c) {
			if (~~e+''===e+'' && e>=0 && a.call(b,c[e],+e,c)) {
				d.push(c[e]);
			}
		}
		return d;
	};


/**
 * ### Changed plugin
 *
 * This plugin adds more information to the `changed.jstree` event. The new data is contained in the `changed` event data property, and contains a lists of `selected` and `deselected` nodes.
 */

	$.jstree.plugins.changed = function (options, parent) {
		var last = [];
		this.trigger = function (ev, data) {
			var i, j;
			if(!data) {
				data = {};
			}
			if(ev.replace('.jstree','') === 'changed') {
				data.changed = { selected : [], deselected : [] };
				var tmp = {};
				for(i = 0, j = last.length; i < j; i++) {
					tmp[last[i]] = 1;
				}
				for(i = 0, j = data.selected.length; i < j; i++) {
					if(!tmp[data.selected[i]]) {
						data.changed.selected.push(data.selected[i]);
					}
					else {
						tmp[data.selected[i]] = 2;
					}
				}
				for(i = 0, j = last.length; i < j; i++) {
					if(tmp[last[i]] === 1) {
						data.changed.deselected.push(last[i]);
					}
				}
				last = data.selected.slice();
			}
			/**
			 * triggered when selection changes (the "changed" plugin enhances the original event with more data)
			 * @event
			 * @name changed.jstree
			 * @param {Object} node
			 * @param {Object} action the action that caused the selection to change
			 * @param {Array} selected the current selection
			 * @param {Object} changed an object containing two properties `selected` and `deselected` - both arrays of node IDs, which were selected or deselected since the last changed event
			 * @param {Object} event the event (if any) that triggered this changed event
			 * @plugin changed
			 */
			parent.trigger.call(this, ev, data);
		};
		this.refresh = function (skip_loading, forget_state) {
			last = [];
			return parent.refresh.apply(this, arguments);
		};
	};

/**
 * ### Checkbox plugin
 *
 * This plugin renders checkbox icons in front of each node, making multiple selection much easier.
 * It also supports tri-state behavior, meaning that if a node has a few of its children checked it will be rendered as undetermined, and state will be propagated up.
 */

	var _i = document.createElement('I');
	_i.className = 'jstree-icon jstree-checkbox';
	_i.setAttribute('role', 'presentation');
	/**
	 * stores all defaults for the checkbox plugin
	 * @name $.jstree.defaults.checkbox
	 * @plugin checkbox
	 */
	$.jstree.defaults.checkbox = {
		/**
		 * a boolean indicating if checkboxes should be visible (can be changed at a later time using `show_checkboxes()` and `hide_checkboxes`). Defaults to `true`.
		 * @name $.jstree.defaults.checkbox.visible
		 * @plugin checkbox
		 */
		visible				: true,
		/**
		 * a boolean indicating if checkboxes should cascade down and have an undetermined state. Defaults to `true`.
		 * @name $.jstree.defaults.checkbox.three_state
		 * @plugin checkbox
		 */
		three_state			: true,
		/**
		 * a boolean indicating if clicking anywhere on the node should act as clicking on the checkbox. Defaults to `true`.
		 * @name $.jstree.defaults.checkbox.whole_node
		 * @plugin checkbox
		 */
		whole_node			: true,
		/**
		 * a boolean indicating if the selected style of a node should be kept, or removed. Defaults to `true`.
		 * @name $.jstree.defaults.checkbox.keep_selected_style
		 * @plugin checkbox
		 */
		keep_selected_style	: true,
		/**
		 * This setting controls how cascading and undetermined nodes are applied.
		 * If 'up' is in the string - cascading up is enabled, if 'down' is in the string - cascading down is enabled, if 'undetermined' is in the string - undetermined nodes will be used.
		 * If `three_state` is set to `true` this setting is automatically set to 'up+down+undetermined'. Defaults to ''.
		 * @name $.jstree.defaults.checkbox.cascade
		 * @plugin checkbox
		 */
		cascade				: '',
		/**
		 * This setting controls if checkbox are bound to the general tree selection or to an internal array maintained by the checkbox plugin. Defaults to `true`, only set to `false` if you know exactly what you are doing.
		 * @name $.jstree.defaults.checkbox.tie_selection
		 * @plugin checkbox
		 */
		tie_selection		: true
	};
	$.jstree.plugins.checkbox = function (options, parent) {
		this.bind = function () {
			parent.bind.call(this);
			this._data.checkbox.uto = false;
			this._data.checkbox.selected = [];
			if(this.settings.checkbox.three_state) {
				this.settings.checkbox.cascade = 'up+down+undetermined';
			}
			this.element
				.on("init.jstree", $.proxy(function () {
						this._data.checkbox.visible = this.settings.checkbox.visible;
						if(!this.settings.checkbox.keep_selected_style) {
							this.element.addClass('jstree-checkbox-no-clicked');
						}
						if(this.settings.checkbox.tie_selection) {
							this.element.addClass('jstree-checkbox-selection');
						}
					}, this))
				.on("loading.jstree", $.proxy(function () {
						this[ this._data.checkbox.visible ? 'show_checkboxes' : 'hide_checkboxes' ]();
					}, this));
			if(this.settings.checkbox.cascade.indexOf('undetermined') !== -1) {
				this.element
					.on('changed.jstree uncheck_node.jstree check_node.jstree uncheck_all.jstree check_all.jstree move_node.jstree copy_node.jstree redraw.jstree open_node.jstree', $.proxy(function () {
							// only if undetermined is in setting
							if(this._data.checkbox.uto) { clearTimeout(this._data.checkbox.uto); }
							this._data.checkbox.uto = setTimeout($.proxy(this._undetermined, this), 50);
						}, this));
			}
			if(!this.settings.checkbox.tie_selection) {
				this.element
					.on('model.jstree', $.proxy(function (e, data) {
						var m = this._model.data,
							p = m[data.parent],
							dpc = data.nodes,
							i, j;
						for(i = 0, j = dpc.length; i < j; i++) {
							m[dpc[i]].state.checked = m[dpc[i]].state.checked || (m[dpc[i]].original && m[dpc[i]].original.state && m[dpc[i]].original.state.checked);
							if(m[dpc[i]].state.checked) {
								this._data.checkbox.selected.push(dpc[i]);
							}
						}
					}, this));
			}
			if(this.settings.checkbox.cascade.indexOf('up') !== -1 || this.settings.checkbox.cascade.indexOf('down') !== -1) {
				this.element
					.on('model.jstree', $.proxy(function (e, data) {
							var m = this._model.data,
								p = m[data.parent],
								dpc = data.nodes,
								chd = [],
								c, i, j, k, l, tmp, s = this.settings.checkbox.cascade, t = this.settings.checkbox.tie_selection;

							if(s.indexOf('down') !== -1) {
								// apply down
								if(p.state[ t ? 'selected' : 'checked' ]) {
									for(i = 0, j = dpc.length; i < j; i++) {
										m[dpc[i]].state[ t ? 'selected' : 'checked' ] = true;
									}
									this._data[ t ? 'core' : 'checkbox' ].selected = this._data[ t ? 'core' : 'checkbox' ].selected.concat(dpc);
								}
								else {
									for(i = 0, j = dpc.length; i < j; i++) {
										if(m[dpc[i]].state[ t ? 'selected' : 'checked' ]) {
											for(k = 0, l = m[dpc[i]].children_d.length; k < l; k++) {
												m[m[dpc[i]].children_d[k]].state[ t ? 'selected' : 'checked' ] = true;
											}
											this._data[ t ? 'core' : 'checkbox' ].selected = this._data[ t ? 'core' : 'checkbox' ].selected.concat(m[dpc[i]].children_d);
										}
									}
								}
							}

							if(s.indexOf('up') !== -1) {
								// apply up
								for(i = 0, j = p.children_d.length; i < j; i++) {
									if(!m[p.children_d[i]].children.length) {
										chd.push(m[p.children_d[i]].parent);
									}
								}
								chd = $.vakata.array_unique(chd);
								for(k = 0, l = chd.length; k < l; k++) {
									p = m[chd[k]];
									while(p && p.id !== $.jstree.root) {
										c = 0;
										for(i = 0, j = p.children.length; i < j; i++) {
											c += m[p.children[i]].state[ t ? 'selected' : 'checked' ];
										}
										if(c === j) {
											p.state[ t ? 'selected' : 'checked' ] = true;
											this._data[ t ? 'core' : 'checkbox' ].selected.push(p.id);
											tmp = this.get_node(p, true);
											if(tmp && tmp.length) {
												tmp.attr('aria-selected', true).children('.jstree-anchor').addClass( t ? 'jstree-clicked' : 'jstree-checked');
											}
										}
										else {
											break;
										}
										p = this.get_node(p.parent);
									}
								}
							}

							this._data[ t ? 'core' : 'checkbox' ].selected = $.vakata.array_unique(this._data[ t ? 'core' : 'checkbox' ].selected);
						}, this))
					.on(this.settings.checkbox.tie_selection ? 'select_node.jstree' : 'check_node.jstree', $.proxy(function (e, data) {
							var obj = data.node,
								m = this._model.data,
								par = this.get_node(obj.parent),
								dom = this.get_node(obj, true),
								i, j, c, tmp, s = this.settings.checkbox.cascade, t = this.settings.checkbox.tie_selection,
								sel = {}, cur = this._data[ t ? 'core' : 'checkbox' ].selected;

							for (i = 0, j = cur.length; i < j; i++) {
								sel[cur[i]] = true;
							}
							// apply down
							if(s.indexOf('down') !== -1) {
								//this._data[ t ? 'core' : 'checkbox' ].selected = $.vakata.array_unique(this._data[ t ? 'core' : 'checkbox' ].selected.concat(obj.children_d));
								for(i = 0, j = obj.children_d.length; i < j; i++) {
									sel[obj.children_d[i]] = true;
									tmp = m[obj.children_d[i]];
									tmp.state[ t ? 'selected' : 'checked' ] = true;
									if(tmp && tmp.original && tmp.original.state && tmp.original.state.undetermined) {
										tmp.original.state.undetermined = false;
									}
								}
							}

							// apply up
							if(s.indexOf('up') !== -1) {
								while(par && par.id !== $.jstree.root) {
									c = 0;
									for(i = 0, j = par.children.length; i < j; i++) {
										c += m[par.children[i]].state[ t ? 'selected' : 'checked' ];
									}
									if(c === j) {
										par.state[ t ? 'selected' : 'checked' ] = true;
										sel[par.id] = true;
										//this._data[ t ? 'core' : 'checkbox' ].selected.push(par.id);
										tmp = this.get_node(par, true);
										if(tmp && tmp.length) {
											tmp.attr('aria-selected', true).children('.jstree-anchor').addClass(t ? 'jstree-clicked' : 'jstree-checked');
										}
									}
									else {
										break;
									}
									par = this.get_node(par.parent);
								}
							}

							cur = [];
							for (i in sel) {
								if (sel.hasOwnProperty(i)) {
									cur.push(i);
								}
							}
							this._data[ t ? 'core' : 'checkbox' ].selected = cur;

							// apply down (process .children separately?)
							if(s.indexOf('down') !== -1 && dom.length) {
								dom.find('.jstree-anchor').addClass(t ? 'jstree-clicked' : 'jstree-checked').parent().attr('aria-selected', true);
							}
						}, this))
					.on(this.settings.checkbox.tie_selection ? 'deselect_all.jstree' : 'uncheck_all.jstree', $.proxy(function (e, data) {
							var obj = this.get_node($.jstree.root),
								m = this._model.data,
								i, j, tmp;
							for(i = 0, j = obj.children_d.length; i < j; i++) {
								tmp = m[obj.children_d[i]];
								if(tmp && tmp.original && tmp.original.state && tmp.original.state.undetermined) {
									tmp.original.state.undetermined = false;
								}
							}
						}, this))
					.on(this.settings.checkbox.tie_selection ? 'deselect_node.jstree' : 'uncheck_node.jstree', $.proxy(function (e, data) {
							var obj = data.node,
								dom = this.get_node(obj, true),
								i, j, tmp, s = this.settings.checkbox.cascade, t = this.settings.checkbox.tie_selection,
								cur = this._data[ t ? 'core' : 'checkbox' ].selected, sel = {};
							if(obj && obj.original && obj.original.state && obj.original.state.undetermined) {
								obj.original.state.undetermined = false;
							}

							// apply down
							if(s.indexOf('down') !== -1) {
								for(i = 0, j = obj.children_d.length; i < j; i++) {
									tmp = this._model.data[obj.children_d[i]];
									tmp.state[ t ? 'selected' : 'checked' ] = false;
									if(tmp && tmp.original && tmp.original.state && tmp.original.state.undetermined) {
										tmp.original.state.undetermined = false;
									}
								}
							}

							// apply up
							if(s.indexOf('up') !== -1) {
								for(i = 0, j = obj.parents.length; i < j; i++) {
									tmp = this._model.data[obj.parents[i]];
									tmp.state[ t ? 'selected' : 'checked' ] = false;
									if(tmp && tmp.original && tmp.original.state && tmp.original.state.undetermined) {
										tmp.original.state.undetermined = false;
									}
									tmp = this.get_node(obj.parents[i], true);
									if(tmp && tmp.length) {
										tmp.attr('aria-selected', false).children('.jstree-anchor').removeClass(t ? 'jstree-clicked' : 'jstree-checked');
									}
								}
							}
							sel = {};
							for(i = 0, j = cur.length; i < j; i++) {
								// apply down + apply up
								if(
									(s.indexOf('down') === -1 || $.inArray(cur[i], obj.children_d) === -1) &&
									(s.indexOf('up') === -1 || $.inArray(cur[i], obj.parents) === -1)
								) {
									sel[cur[i]] = true;
								}
							}
							cur = [];
							for (i in sel) {
								if (sel.hasOwnProperty(i)) {
									cur.push(i);
								}
							}
							this._data[ t ? 'core' : 'checkbox' ].selected = cur;
							
							// apply down (process .children separately?)
							if(s.indexOf('down') !== -1 && dom.length) {
								dom.find('.jstree-anchor').removeClass(t ? 'jstree-clicked' : 'jstree-checked').parent().attr('aria-selected', false);
							}
						}, this));
			}
			if(this.settings.checkbox.cascade.indexOf('up') !== -1) {
				this.element
					.on('delete_node.jstree', $.proxy(function (e, data) {
							// apply up (whole handler)
							var p = this.get_node(data.parent),
								m = this._model.data,
								i, j, c, tmp, t = this.settings.checkbox.tie_selection;
							while(p && p.id !== $.jstree.root && !p.state[ t ? 'selected' : 'checked' ]) {
								c = 0;
								for(i = 0, j = p.children.length; i < j; i++) {
									c += m[p.children[i]].state[ t ? 'selected' : 'checked' ];
								}
								if(j > 0 && c === j) {
									p.state[ t ? 'selected' : 'checked' ] = true;
									this._data[ t ? 'core' : 'checkbox' ].selected.push(p.id);
									tmp = this.get_node(p, true);
									if(tmp && tmp.length) {
										tmp.attr('aria-selected', true).children('.jstree-anchor').addClass(t ? 'jstree-clicked' : 'jstree-checked');
									}
								}
								else {
									break;
								}
								p = this.get_node(p.parent);
							}
						}, this))
					.on('move_node.jstree', $.proxy(function (e, data) {
							// apply up (whole handler)
							var is_multi = data.is_multi,
								old_par = data.old_parent,
								new_par = this.get_node(data.parent),
								m = this._model.data,
								p, c, i, j, tmp, t = this.settings.checkbox.tie_selection;
							if(!is_multi) {
								p = this.get_node(old_par);
								while(p && p.id !== $.jstree.root && !p.state[ t ? 'selected' : 'checked' ]) {
									c = 0;
									for(i = 0, j = p.children.length; i < j; i++) {
										c += m[p.children[i]].state[ t ? 'selected' : 'checked' ];
									}
									if(j > 0 && c === j) {
										p.state[ t ? 'selected' : 'checked' ] = true;
										this._data[ t ? 'core' : 'checkbox' ].selected.push(p.id);
										tmp = this.get_node(p, true);
										if(tmp && tmp.length) {
											tmp.attr('aria-selected', true).children('.jstree-anchor').addClass(t ? 'jstree-clicked' : 'jstree-checked');
										}
									}
									else {
										break;
									}
									p = this.get_node(p.parent);
								}
							}
							p = new_par;
							while(p && p.id !== $.jstree.root) {
								c = 0;
								for(i = 0, j = p.children.length; i < j; i++) {
									c += m[p.children[i]].state[ t ? 'selected' : 'checked' ];
								}
								if(c === j) {
									if(!p.state[ t ? 'selected' : 'checked' ]) {
										p.state[ t ? 'selected' : 'checked' ] = true;
										this._data[ t ? 'core' : 'checkbox' ].selected.push(p.id);
										tmp = this.get_node(p, true);
										if(tmp && tmp.length) {
											tmp.attr('aria-selected', true).children('.jstree-anchor').addClass(t ? 'jstree-clicked' : 'jstree-checked');
										}
									}
								}
								else {
									if(p.state[ t ? 'selected' : 'checked' ]) {
										p.state[ t ? 'selected' : 'checked' ] = false;
										this._data[ t ? 'core' : 'checkbox' ].selected = $.vakata.array_remove_item(this._data[ t ? 'core' : 'checkbox' ].selected, p.id);
										tmp = this.get_node(p, true);
										if(tmp && tmp.length) {
											tmp.attr('aria-selected', false).children('.jstree-anchor').removeClass(t ? 'jstree-clicked' : 'jstree-checked');
										}
									}
									else {
										break;
									}
								}
								p = this.get_node(p.parent);
							}
						}, this));
			}
		};
		/**
		 * set the undetermined state where and if necessary. Used internally.
		 * @private
		 * @name _undetermined()
		 * @plugin checkbox
		 */
		this._undetermined = function () {
			if(this.element === null) { return; }
			var i, j, k, l, o = {}, m = this._model.data, t = this.settings.checkbox.tie_selection, s = this._data[ t ? 'core' : 'checkbox' ].selected, p = [], tt = this;
			for(i = 0, j = s.length; i < j; i++) {
				if(m[s[i]] && m[s[i]].parents) {
					for(k = 0, l = m[s[i]].parents.length; k < l; k++) {
						if(o[m[s[i]].parents[k]] !== undefined) {
							break;
						}
						if(m[s[i]].parents[k] !== $.jstree.root) {
							o[m[s[i]].parents[k]] = true;
							p.push(m[s[i]].parents[k]);
						}
					}
				}
			}
			// attempt for server side undetermined state
			this.element.find('.jstree-closed').not(':has(.jstree-children)')
				.each(function () {
					var tmp = tt.get_node(this), tmp2;
					if(!tmp.state.loaded) {
						if(tmp.original && tmp.original.state && tmp.original.state.undetermined && tmp.original.state.undetermined === true) {
							if(o[tmp.id] === undefined && tmp.id !== $.jstree.root) {
								o[tmp.id] = true;
								p.push(tmp.id);
							}
							for(k = 0, l = tmp.parents.length; k < l; k++) {
								if(o[tmp.parents[k]] === undefined && tmp.parents[k] !== $.jstree.root) {
									o[tmp.parents[k]] = true;
									p.push(tmp.parents[k]);
								}
							}
						}
					}
					else {
						for(i = 0, j = tmp.children_d.length; i < j; i++) {
							tmp2 = m[tmp.children_d[i]];
							if(!tmp2.state.loaded && tmp2.original && tmp2.original.state && tmp2.original.state.undetermined && tmp2.original.state.undetermined === true) {
								if(o[tmp2.id] === undefined && tmp2.id !== $.jstree.root) {
									o[tmp2.id] = true;
									p.push(tmp2.id);
								}
								for(k = 0, l = tmp2.parents.length; k < l; k++) {
									if(o[tmp2.parents[k]] === undefined && tmp2.parents[k] !== $.jstree.root) {
										o[tmp2.parents[k]] = true;
										p.push(tmp2.parents[k]);
									}
								}
							}
						}
					}
				});

			this.element.find('.jstree-undetermined').removeClass('jstree-undetermined');
			for(i = 0, j = p.length; i < j; i++) {
				if(!m[p[i]].state[ t ? 'selected' : 'checked' ]) {
					s = this.get_node(p[i], true);
					if(s && s.length) {
						s.children('.jstree-anchor').children('.jstree-checkbox').addClass('jstree-undetermined');
					}
				}
			}
		};
		this.redraw_node = function(obj, deep, is_callback, force_render) {
			obj = parent.redraw_node.apply(this, arguments);
			if(obj) {
				var i, j, tmp = null, icon = null;
				for(i = 0, j = obj.childNodes.length; i < j; i++) {
					if(obj.childNodes[i] && obj.childNodes[i].className && obj.childNodes[i].className.indexOf("jstree-anchor") !== -1) {
						tmp = obj.childNodes[i];
						break;
					}
				}
				if(tmp) {
					if(!this.settings.checkbox.tie_selection && this._model.data[obj.id].state.checked) { tmp.className += ' jstree-checked'; }
					icon = _i.cloneNode(false);
					if(this._model.data[obj.id].state.checkbox_disabled) { icon.className += ' jstree-checkbox-disabled'; }
					tmp.insertBefore(icon, tmp.childNodes[0]);
				}
			}
			if(!is_callback && this.settings.checkbox.cascade.indexOf('undetermined') !== -1) {
				if(this._data.checkbox.uto) { clearTimeout(this._data.checkbox.uto); }
				this._data.checkbox.uto = setTimeout($.proxy(this._undetermined, this), 50);
			}
			return obj;
		};
		/**
		 * show the node checkbox icons
		 * @name show_checkboxes()
		 * @plugin checkbox
		 */
		this.show_checkboxes = function () { this._data.core.themes.checkboxes = true; this.get_container_ul().removeClass("jstree-no-checkboxes"); };
		/**
		 * hide the node checkbox icons
		 * @name hide_checkboxes()
		 * @plugin checkbox
		 */
		this.hide_checkboxes = function () { this._data.core.themes.checkboxes = false; this.get_container_ul().addClass("jstree-no-checkboxes"); };
		/**
		 * toggle the node icons
		 * @name toggle_checkboxes()
		 * @plugin checkbox
		 */
		this.toggle_checkboxes = function () { if(this._data.core.themes.checkboxes) { this.hide_checkboxes(); } else { this.show_checkboxes(); } };
		/**
		 * checks if a node is in an undetermined state
		 * @name is_undetermined(obj)
		 * @param  {mixed} obj
		 * @return {Boolean}
		 */
		this.is_undetermined = function (obj) {
			obj = this.get_node(obj);
			var s = this.settings.checkbox.cascade, i, j, t = this.settings.checkbox.tie_selection, d = this._data[ t ? 'core' : 'checkbox' ].selected, m = this._model.data;
			if(!obj || obj.state[ t ? 'selected' : 'checked' ] === true || s.indexOf('undetermined') === -1 || (s.indexOf('down') === -1 && s.indexOf('up') === -1)) {
				return false;
			}
			if(!obj.state.loaded && obj.original.state.undetermined === true) {
				return true;
			}
			for(i = 0, j = obj.children_d.length; i < j; i++) {
				if($.inArray(obj.children_d[i], d) !== -1 || (!m[obj.children_d[i]].state.loaded && m[obj.children_d[i]].original.state.undetermined)) {
					return true;
				}
			}
			return false;
		};
		/**
		 * disable a node's checkbox
		 * @name disable_checkbox(obj)
		 * @param {mixed} obj an array can be used too
		 * @trigger disable_checkbox.jstree
		 * @plugin checkbox
		 */
		this.disable_checkbox = function (obj) {
			var t1, t2, dom;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.disable_checkbox(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			dom = this.get_node(obj, true);
			if(!obj.state.checkbox_disabled) {
				obj.state.checkbox_disabled = true;
				if(dom && dom.length) {
					dom.children('.jstree-anchor').children('.jstree-checkbox').addClass('jstree-checkbox-disabled');
				}
				/**
				 * triggered when an node's checkbox is disabled
				 * @event
				 * @name disable_checkbox.jstree
				 * @param {Object} node
				 * @plugin checkbox
				 */
				this.trigger('disable_checkbox', { 'node' : obj });
			}
		};
		/**
		 * enable a node's checkbox
		 * @name disable_checkbox(obj)
		 * @param {mixed} obj an array can be used too
		 * @trigger enable_checkbox.jstree
		 * @plugin checkbox
		 */
		this.enable_checkbox = function (obj) {
			var t1, t2, dom;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.enable_checkbox(obj[t1]);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			dom = this.get_node(obj, true);
			if(obj.state.checkbox_disabled) {
				obj.state.checkbox_disabled = false;
				if(dom && dom.length) {
					dom.children('.jstree-anchor').children('.jstree-checkbox').removeClass('jstree-checkbox-disabled');
				}
				/**
				 * triggered when an node's checkbox is enabled
				 * @event
				 * @name enable_checkbox.jstree
				 * @param {Object} node
				 * @plugin checkbox
				 */
				this.trigger('enable_checkbox', { 'node' : obj });
			}
		};

		this.activate_node = function (obj, e) {
			if($(e.target).hasClass('jstree-checkbox-disabled')) {
				return false;
			}
			if(this.settings.checkbox.tie_selection && (this.settings.checkbox.whole_node || $(e.target).hasClass('jstree-checkbox'))) {
				e.ctrlKey = true;
			}
			if(this.settings.checkbox.tie_selection || (!this.settings.checkbox.whole_node && !$(e.target).hasClass('jstree-checkbox'))) {
				return parent.activate_node.call(this, obj, e);
			}
			if(this.is_disabled(obj)) {
				return false;
			}
			if(this.is_checked(obj)) {
				this.uncheck_node(obj, e);
			}
			else {
				this.check_node(obj, e);
			}
			this.trigger('activate_node', { 'node' : this.get_node(obj) });
		};

		/**
		 * check a node (only if tie_selection in checkbox settings is false, otherwise select_node will be called internally)
		 * @name check_node(obj)
		 * @param {mixed} obj an array can be used to check multiple nodes
		 * @trigger check_node.jstree
		 * @plugin checkbox
		 */
		this.check_node = function (obj, e) {
			if(this.settings.checkbox.tie_selection) { return this.select_node(obj, false, true, e); }
			var dom, t1, t2, th;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.check_node(obj[t1], e);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			dom = this.get_node(obj, true);
			if(!obj.state.checked) {
				obj.state.checked = true;
				this._data.checkbox.selected.push(obj.id);
				if(dom && dom.length) {
					dom.children('.jstree-anchor').addClass('jstree-checked');
				}
				/**
				 * triggered when an node is checked (only if tie_selection in checkbox settings is false)
				 * @event
				 * @name check_node.jstree
				 * @param {Object} node
				 * @param {Array} selected the current selection
				 * @param {Object} event the event (if any) that triggered this check_node
				 * @plugin checkbox
				 */
				this.trigger('check_node', { 'node' : obj, 'selected' : this._data.checkbox.selected, 'event' : e });
			}
		};
		/**
		 * uncheck a node (only if tie_selection in checkbox settings is false, otherwise deselect_node will be called internally)
		 * @name uncheck_node(obj)
		 * @param {mixed} obj an array can be used to uncheck multiple nodes
		 * @trigger uncheck_node.jstree
		 * @plugin checkbox
		 */
		this.uncheck_node = function (obj, e) {
			if(this.settings.checkbox.tie_selection) { return this.deselect_node(obj, false, e); }
			var t1, t2, dom;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.uncheck_node(obj[t1], e);
				}
				return true;
			}
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) {
				return false;
			}
			dom = this.get_node(obj, true);
			if(obj.state.checked) {
				obj.state.checked = false;
				this._data.checkbox.selected = $.vakata.array_remove_item(this._data.checkbox.selected, obj.id);
				if(dom.length) {
					dom.children('.jstree-anchor').removeClass('jstree-checked');
				}
				/**
				 * triggered when an node is unchecked (only if tie_selection in checkbox settings is false)
				 * @event
				 * @name uncheck_node.jstree
				 * @param {Object} node
				 * @param {Array} selected the current selection
				 * @param {Object} event the event (if any) that triggered this uncheck_node
				 * @plugin checkbox
				 */
				this.trigger('uncheck_node', { 'node' : obj, 'selected' : this._data.checkbox.selected, 'event' : e });
			}
		};
		/**
		 * checks all nodes in the tree (only if tie_selection in checkbox settings is false, otherwise select_all will be called internally)
		 * @name check_all()
		 * @trigger check_all.jstree, changed.jstree
		 * @plugin checkbox
		 */
		this.check_all = function () {
			if(this.settings.checkbox.tie_selection) { return this.select_all(); }
			var tmp = this._data.checkbox.selected.concat([]), i, j;
			this._data.checkbox.selected = this._model.data[$.jstree.root].children_d.concat();
			for(i = 0, j = this._data.checkbox.selected.length; i < j; i++) {
				if(this._model.data[this._data.checkbox.selected[i]]) {
					this._model.data[this._data.checkbox.selected[i]].state.checked = true;
				}
			}
			this.redraw(true);
			/**
			 * triggered when all nodes are checked (only if tie_selection in checkbox settings is false)
			 * @event
			 * @name check_all.jstree
			 * @param {Array} selected the current selection
			 * @plugin checkbox
			 */
			this.trigger('check_all', { 'selected' : this._data.checkbox.selected });
		};
		/**
		 * uncheck all checked nodes (only if tie_selection in checkbox settings is false, otherwise deselect_all will be called internally)
		 * @name uncheck_all()
		 * @trigger uncheck_all.jstree
		 * @plugin checkbox
		 */
		this.uncheck_all = function () {
			if(this.settings.checkbox.tie_selection) { return this.deselect_all(); }
			var tmp = this._data.checkbox.selected.concat([]), i, j;
			for(i = 0, j = this._data.checkbox.selected.length; i < j; i++) {
				if(this._model.data[this._data.checkbox.selected[i]]) {
					this._model.data[this._data.checkbox.selected[i]].state.checked = false;
				}
			}
			this._data.checkbox.selected = [];
			this.element.find('.jstree-checked').removeClass('jstree-checked');
			/**
			 * triggered when all nodes are unchecked (only if tie_selection in checkbox settings is false)
			 * @event
			 * @name uncheck_all.jstree
			 * @param {Object} node the previous selection
			 * @param {Array} selected the current selection
			 * @plugin checkbox
			 */
			this.trigger('uncheck_all', { 'selected' : this._data.checkbox.selected, 'node' : tmp });
		};
		/**
		 * checks if a node is checked (if tie_selection is on in the settings this function will return the same as is_selected)
		 * @name is_checked(obj)
		 * @param  {mixed}  obj
		 * @return {Boolean}
		 * @plugin checkbox
		 */
		this.is_checked = function (obj) {
			if(this.settings.checkbox.tie_selection) { return this.is_selected(obj); }
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			return obj.state.checked;
		};
		/**
		 * get an array of all checked nodes (if tie_selection is on in the settings this function will return the same as get_selected)
		 * @name get_checked([full])
		 * @param  {mixed}  full if set to `true` the returned array will consist of the full node objects, otherwise - only IDs will be returned
		 * @return {Array}
		 * @plugin checkbox
		 */
		this.get_checked = function (full) {
			if(this.settings.checkbox.tie_selection) { return this.get_selected(full); }
			return full ? $.map(this._data.checkbox.selected, $.proxy(function (i) { return this.get_node(i); }, this)) : this._data.checkbox.selected;
		};
		/**
		 * get an array of all top level checked nodes (ignoring children of checked nodes) (if tie_selection is on in the settings this function will return the same as get_top_selected)
		 * @name get_top_checked([full])
		 * @param  {mixed}  full if set to `true` the returned array will consist of the full node objects, otherwise - only IDs will be returned
		 * @return {Array}
		 * @plugin checkbox
		 */
		this.get_top_checked = function (full) {
			if(this.settings.checkbox.tie_selection) { return this.get_top_selected(full); }
			var tmp = this.get_checked(true),
				obj = {}, i, j, k, l;
			for(i = 0, j = tmp.length; i < j; i++) {
				obj[tmp[i].id] = tmp[i];
			}
			for(i = 0, j = tmp.length; i < j; i++) {
				for(k = 0, l = tmp[i].children_d.length; k < l; k++) {
					if(obj[tmp[i].children_d[k]]) {
						delete obj[tmp[i].children_d[k]];
					}
				}
			}
			tmp = [];
			for(i in obj) {
				if(obj.hasOwnProperty(i)) {
					tmp.push(i);
				}
			}
			return full ? $.map(tmp, $.proxy(function (i) { return this.get_node(i); }, this)) : tmp;
		};
		/**
		 * get an array of all bottom level checked nodes (ignoring selected parents) (if tie_selection is on in the settings this function will return the same as get_bottom_selected)
		 * @name get_bottom_checked([full])
		 * @param  {mixed}  full if set to `true` the returned array will consist of the full node objects, otherwise - only IDs will be returned
		 * @return {Array}
		 * @plugin checkbox
		 */
		this.get_bottom_checked = function (full) {
			if(this.settings.checkbox.tie_selection) { return this.get_bottom_selected(full); }
			var tmp = this.get_checked(true),
				obj = [], i, j;
			for(i = 0, j = tmp.length; i < j; i++) {
				if(!tmp[i].children.length) {
					obj.push(tmp[i].id);
				}
			}
			return full ? $.map(obj, $.proxy(function (i) { return this.get_node(i); }, this)) : obj;
		};
		this.load_node = function (obj, callback) {
			var k, l, i, j, c, tmp;
			if(!$.isArray(obj) && !this.settings.checkbox.tie_selection) {
				tmp = this.get_node(obj);
				if(tmp && tmp.state.loaded) {
					for(k = 0, l = tmp.children_d.length; k < l; k++) {
						if(this._model.data[tmp.children_d[k]].state.checked) {
							c = true;
							this._data.checkbox.selected = $.vakata.array_remove_item(this._data.checkbox.selected, tmp.children_d[k]);
						}
					}
				}
			}
			return parent.load_node.apply(this, arguments);
		};
		this.get_state = function () {
			var state = parent.get_state.apply(this, arguments);
			if(this.settings.checkbox.tie_selection) { return state; }
			state.checkbox = this._data.checkbox.selected.slice();
			return state;
		};
		this.set_state = function (state, callback) {
			var res = parent.set_state.apply(this, arguments);
			if(res && state.checkbox) {
				if(!this.settings.checkbox.tie_selection) {
					this.uncheck_all();
					var _this = this;
					$.each(state.checkbox, function (i, v) {
						_this.check_node(v);
					});
				}
				delete state.checkbox;
				this.set_state(state, callback);
				return false;
			}
			return res;
		};
		this.refresh = function (skip_loading, forget_state) {
			if(!this.settings.checkbox.tie_selection) {
				this._data.checkbox.selected = [];
			}
			return parent.refresh.apply(this, arguments);
		};
	};

	// include the checkbox plugin by default
	// $.jstree.defaults.plugins.push("checkbox");

/**
 * ### Conditionalselect plugin
 *
 * This plugin allows defining a callback to allow or deny node selection by user input (activate node method).
 */

	/**
	 * a callback (function) which is invoked in the instance's scope and receives two arguments - the node and the event that triggered the `activate_node` call. Returning false prevents working with the node, returning true allows invoking activate_node. Defaults to returning `true`.
	 * @name $.jstree.defaults.checkbox.visible
	 * @plugin checkbox
	 */
	$.jstree.defaults.conditionalselect = function () { return true; };
	$.jstree.plugins.conditionalselect = function (options, parent) {
		// own function
		this.activate_node = function (obj, e) {
			if(this.settings.conditionalselect.call(this, this.get_node(obj), e)) {
				parent.activate_node.call(this, obj, e);
			}
		};
	};


/**
 * ### Contextmenu plugin
 *
 * Shows a context menu when a node is right-clicked.
 */

	/**
	 * stores all defaults for the contextmenu plugin
	 * @name $.jstree.defaults.contextmenu
	 * @plugin contextmenu
	 */
	$.jstree.defaults.contextmenu = {
		/**
		 * a boolean indicating if the node should be selected when the context menu is invoked on it. Defaults to `true`.
		 * @name $.jstree.defaults.contextmenu.select_node
		 * @plugin contextmenu
		 */
		select_node : true,
		/**
		 * a boolean indicating if the menu should be shown aligned with the node. Defaults to `true`, otherwise the mouse coordinates are used.
		 * @name $.jstree.defaults.contextmenu.show_at_node
		 * @plugin contextmenu
		 */
		show_at_node : true,
		/**
		 * an object of actions, or a function that accepts a node and a callback function and calls the callback function with an object of actions available for that node (you can also return the items too).
		 *
		 * Each action consists of a key (a unique name) and a value which is an object with the following properties (only label and action are required). Once a menu item is activated the `action` function will be invoked with an object containing the following keys: item - the contextmenu item definition as seen below, reference - the DOM node that was used (the tree node), element - the contextmenu DOM element, position - an object with x/y properties indicating the position of the menu.
		 *
		 * * `separator_before` - a boolean indicating if there should be a separator before this item
		 * * `separator_after` - a boolean indicating if there should be a separator after this item
		 * * `_disabled` - a boolean indicating if this action should be disabled
		 * * `label` - a string - the name of the action (could be a function returning a string)
		 * * `title` - a string - an optional tooltip for the item
		 * * `action` - a function to be executed if this item is chosen, the function will receive 
		 * * `icon` - a string, can be a path to an icon or a className, if using an image that is in the current directory use a `./` prefix, otherwise it will be detected as a class
		 * * `shortcut` - keyCode which will trigger the action if the menu is open (for example `113` for rename, which equals F2)
		 * * `shortcut_label` - shortcut label (like for example `F2` for rename)
		 * * `submenu` - an object with the same structure as $.jstree.defaults.contextmenu.items which can be used to create a submenu - each key will be rendered as a separate option in a submenu that will appear once the current item is hovered
		 *
		 * @name $.jstree.defaults.contextmenu.items
		 * @plugin contextmenu
		 */
		items : function (o, cb) { // Could be an object directly
			return {
				"create" : {
					"separator_before"	: false,
					"separator_after"	: true,
					"_disabled"			: false, //(this.check("create_node", data.reference, {}, "last")),
					"label"				: "Create",
					"action"			: function (data) {
						var inst = $.jstree.reference(data.reference),
							obj = inst.get_node(data.reference);
						inst.create_node(obj, {}, "last", function (new_node) {
							setTimeout(function () { inst.edit(new_node); },0);
						});
					}
				},
				"rename" : {
					"separator_before"	: false,
					"separator_after"	: false,
					"_disabled"			: false, //(this.check("rename_node", data.reference, this.get_parent(data.reference), "")),
					"label"				: "Rename",
					/*!
					"shortcut"			: 113,
					"shortcut_label"	: 'F2',
					"icon"				: "glyphicon glyphicon-leaf",
					*/
					"action"			: function (data) {
						var inst = $.jstree.reference(data.reference),
							obj = inst.get_node(data.reference);
						inst.edit(obj);
					}
				},
				"remove" : {
					"separator_before"	: false,
					"icon"				: false,
					"separator_after"	: false,
					"_disabled"			: false, //(this.check("delete_node", data.reference, this.get_parent(data.reference), "")),
					"label"				: "Delete",
					"action"			: function (data) {
						var inst = $.jstree.reference(data.reference),
							obj = inst.get_node(data.reference);
						if(inst.is_selected(obj)) {
							inst.delete_node(inst.get_selected());
						}
						else {
							inst.delete_node(obj);
						}
					}
				},
				"ccp" : {
					"separator_before"	: true,
					"icon"				: false,
					"separator_after"	: false,
					"label"				: "Edit",
					"action"			: false,
					"submenu" : {
						"cut" : {
							"separator_before"	: false,
							"separator_after"	: false,
							"label"				: "Cut",
							"action"			: function (data) {
								var inst = $.jstree.reference(data.reference),
									obj = inst.get_node(data.reference);
								if(inst.is_selected(obj)) {
									inst.cut(inst.get_top_selected());
								}
								else {
									inst.cut(obj);
								}
							}
						},
						"copy" : {
							"separator_before"	: false,
							"icon"				: false,
							"separator_after"	: false,
							"label"				: "Copy",
							"action"			: function (data) {
								var inst = $.jstree.reference(data.reference),
									obj = inst.get_node(data.reference);
								if(inst.is_selected(obj)) {
									inst.copy(inst.get_top_selected());
								}
								else {
									inst.copy(obj);
								}
							}
						},
						"paste" : {
							"separator_before"	: false,
							"icon"				: false,
							"_disabled"			: function (data) {
								return !$.jstree.reference(data.reference).can_paste();
							},
							"separator_after"	: false,
							"label"				: "Paste",
							"action"			: function (data) {
								var inst = $.jstree.reference(data.reference),
									obj = inst.get_node(data.reference);
								inst.paste(obj);
							}
						}
					}
				}
			};
		}
	};

	$.jstree.plugins.contextmenu = function (options, parent) {
		this.bind = function () {
			parent.bind.call(this);

			var last_ts = 0, cto = null, ex, ey;
			this.element
				.on("contextmenu.jstree", ".jstree-anchor", $.proxy(function (e, data) {
						if (e.target.tagName.toLowerCase() === 'input') {
							return;
						}
						e.preventDefault();
						last_ts = e.ctrlKey ? +new Date() : 0;
						if(data || cto) {
							last_ts = (+new Date()) + 10000;
						}
						if(cto) {
							clearTimeout(cto);
						}
						if(!this.is_loading(e.currentTarget)) {
							this.show_contextmenu(e.currentTarget, e.pageX, e.pageY, e);
						}
					}, this))
				.on("click.jstree", ".jstree-anchor", $.proxy(function (e) {
						if(this._data.contextmenu.visible && (!last_ts || (+new Date()) - last_ts > 250)) { // work around safari & macOS ctrl+click
							$.vakata.context.hide();
						}
						last_ts = 0;
					}, this))
				.on("touchstart.jstree", ".jstree-anchor", function (e) {
						if(!e.originalEvent || !e.originalEvent.changedTouches || !e.originalEvent.changedTouches[0]) {
							return;
						}
						ex = e.originalEvent.changedTouches[0].clientX;
						ey = e.originalEvent.changedTouches[0].clientY;
						cto = setTimeout(function () {
							$(e.currentTarget).trigger('contextmenu', true);
						}, 750);
					})
				.on('touchmove.vakata.jstree', function (e) {
						if(cto && e.originalEvent && e.originalEvent.changedTouches && e.originalEvent.changedTouches[0] && (Math.abs(ex - e.originalEvent.changedTouches[0].clientX) > 50 || Math.abs(ey - e.originalEvent.changedTouches[0].clientY) > 50)) {
							clearTimeout(cto);
						}
					})
				.on('touchend.vakata.jstree', function (e) {
						if(cto) {
							clearTimeout(cto);
						}
					});

			/*!
			if(!('oncontextmenu' in document.body) && ('ontouchstart' in document.body)) {
				var el = null, tm = null;
				this.element
					.on("touchstart", ".jstree-anchor", function (e) {
						el = e.currentTarget;
						tm = +new Date();
						$(document).one("touchend", function (e) {
							e.target = document.elementFromPoint(e.originalEvent.targetTouches[0].pageX - window.pageXOffset, e.originalEvent.targetTouches[0].pageY - window.pageYOffset);
							e.currentTarget = e.target;
							tm = ((+(new Date())) - tm);
							if(e.target === el && tm > 600 && tm < 1000) {
								e.preventDefault();
								$(el).trigger('contextmenu', e);
							}
							el = null;
							tm = null;
						});
					});
			}
			*/
			$(document).on("context_hide.vakata.jstree", $.proxy(function (e, data) {
				this._data.contextmenu.visible = false;
				$(data.reference).removeClass('jstree-context');
			}, this));
		};
		this.teardown = function () {
			if(this._data.contextmenu.visible) {
				$.vakata.context.hide();
			}
			parent.teardown.call(this);
		};

		/**
		 * prepare and show the context menu for a node
		 * @name show_contextmenu(obj [, x, y])
		 * @param {mixed} obj the node
		 * @param {Number} x the x-coordinate relative to the document to show the menu at
		 * @param {Number} y the y-coordinate relative to the document to show the menu at
		 * @param {Object} e the event if available that triggered the contextmenu
		 * @plugin contextmenu
		 * @trigger show_contextmenu.jstree
		 */
		this.show_contextmenu = function (obj, x, y, e) {
			obj = this.get_node(obj);
			if(!obj || obj.id === $.jstree.root) { return false; }
			var s = this.settings.contextmenu,
				d = this.get_node(obj, true),
				a = d.children(".jstree-anchor"),
				o = false,
				i = false;
			if(s.show_at_node || x === undefined || y === undefined) {
				o = a.offset();
				x = o.left;
				y = o.top + this._data.core.li_height;
			}
			if(this.settings.contextmenu.select_node && !this.is_selected(obj)) {
				this.activate_node(obj, e);
			}

			i = s.items;
			if($.isFunction(i)) {
				i = i.call(this, obj, $.proxy(function (i) {
					this._show_contextmenu(obj, x, y, i);
				}, this));
			}
			if($.isPlainObject(i)) {
				this._show_contextmenu(obj, x, y, i);
			}
		};
		/**
		 * show the prepared context menu for a node
		 * @name _show_contextmenu(obj, x, y, i)
		 * @param {mixed} obj the node
		 * @param {Number} x the x-coordinate relative to the document to show the menu at
		 * @param {Number} y the y-coordinate relative to the document to show the menu at
		 * @param {Number} i the object of items to show
		 * @plugin contextmenu
		 * @trigger show_contextmenu.jstree
		 * @private
		 */
		this._show_contextmenu = function (obj, x, y, i) {
			var d = this.get_node(obj, true),
				a = d.children(".jstree-anchor");
			$(document).one("context_show.vakata.jstree", $.proxy(function (e, data) {
				var cls = 'jstree-contextmenu jstree-' + this.get_theme() + '-contextmenu';
				$(data.element).addClass(cls);
				a.addClass('jstree-context');
			}, this));
			this._data.contextmenu.visible = true;
			$.vakata.context.show(a, { 'x' : x, 'y' : y }, i);
			/**
			 * triggered when the contextmenu is shown for a node
			 * @event
			 * @name show_contextmenu.jstree
			 * @param {Object} node the node
			 * @param {Number} x the x-coordinate of the menu relative to the document
			 * @param {Number} y the y-coordinate of the menu relative to the document
			 * @plugin contextmenu
			 */
			this.trigger('show_contextmenu', { "node" : obj, "x" : x, "y" : y });
		};
	};

	// contextmenu helper
	(function ($) {
		var right_to_left = false,
			vakata_context = {
				element		: false,
				reference	: false,
				position_x	: 0,
				position_y	: 0,
				items		: [],
				html		: "",
				is_visible	: false
			};

		$.vakata.context = {
			settings : {
				hide_onmouseleave	: 0,
				icons				: true
			},
			_trigger : function (event_name) {
				$(document).triggerHandler("context_" + event_name + ".vakata", {
					"reference"	: vakata_context.reference,
					"element"	: vakata_context.element,
					"position"	: {
						"x" : vakata_context.position_x,
						"y" : vakata_context.position_y
					}
				});
			},
			_execute : function (i) {
				i = vakata_context.items[i];
				return i && (!i._disabled || ($.isFunction(i._disabled) && !i._disabled({ "item" : i, "reference" : vakata_context.reference, "element" : vakata_context.element }))) && i.action ? i.action.call(null, {
							"item"		: i,
							"reference"	: vakata_context.reference,
							"element"	: vakata_context.element,
							"position"	: {
								"x" : vakata_context.position_x,
								"y" : vakata_context.position_y
							}
						}) : false;
			},
			_parse : function (o, is_callback) {
				if(!o) { return false; }
				if(!is_callback) {
					vakata_context.html		= "";
					vakata_context.items	= [];
				}
				var str = "",
					sep = false,
					tmp;

				if(is_callback) { str += "<"+"ul>"; }
				$.each(o, function (i, val) {
					if(!val) { return true; }
					vakata_context.items.push(val);
					if(!sep && val.separator_before) {
						str += "<"+"li class='vakata-context-separator'><"+"a href='#' " + ($.vakata.context.settings.icons ? '' : 'style="margin-left:0px;"') + ">&#160;<"+"/a><"+"/li>";
					}
					sep = false;
					str += "<"+"li class='" + (val._class || "") + (val._disabled === true || ($.isFunction(val._disabled) && val._disabled({ "item" : val, "reference" : vakata_context.reference, "element" : vakata_context.element })) ? " vakata-contextmenu-disabled " : "") + "' "+(val.shortcut?" data-shortcut='"+val.shortcut+"' ":'')+">";
					str += "<"+"a href='#' rel='" + (vakata_context.items.length - 1) + "' " + (val.title ? "title='" + val.title + "'" : "") + ">";
					if($.vakata.context.settings.icons) {
						str += "<"+"i ";
						if(val.icon) {
							if(val.icon.indexOf("/") !== -1 || val.icon.indexOf(".") !== -1) { str += " style='background:url(\"" + val.icon + "\") center center no-repeat' "; }
							else { str += " class='" + val.icon + "' "; }
						}
						str += "><"+"/i><"+"span class='vakata-contextmenu-sep'>&#160;<"+"/span>";
					}
					str += ($.isFunction(val.label) ? val.label({ "item" : i, "reference" : vakata_context.reference, "element" : vakata_context.element }) : val.label) + (val.shortcut?' <span class="vakata-contextmenu-shortcut vakata-contextmenu-shortcut-'+val.shortcut+'">'+ (val.shortcut_label || '') +'</span>':'') + "<"+"/a>";
					if(val.submenu) {
						tmp = $.vakata.context._parse(val.submenu, true);
						if(tmp) { str += tmp; }
					}
					str += "<"+"/li>";
					if(val.separator_after) {
						str += "<"+"li class='vakata-context-separator'><"+"a href='#' " + ($.vakata.context.settings.icons ? '' : 'style="margin-left:0px;"') + ">&#160;<"+"/a><"+"/li>";
						sep = true;
					}
				});
				str  = str.replace(/<li class\='vakata-context-separator'\><\/li\>$/,"");
				if(is_callback) { str += "</ul>"; }
				/**
				 * triggered on the document when the contextmenu is parsed (HTML is built)
				 * @event
				 * @plugin contextmenu
				 * @name context_parse.vakata
				 * @param {jQuery} reference the element that was right clicked
				 * @param {jQuery} element the DOM element of the menu itself
				 * @param {Object} position the x & y coordinates of the menu
				 */
				if(!is_callback) { vakata_context.html = str; $.vakata.context._trigger("parse"); }
				return str.length > 10 ? str : false;
			},
			_show_submenu : function (o) {
				o = $(o);
				if(!o.length || !o.children("ul").length) { return; }
				var e = o.children("ul"),
					xl = o.offset().left,
					x = xl + o.outerWidth(),
					y = o.offset().top,
					w = e.width(),
					h = e.height(),
					dw = $(window).width() + $(window).scrollLeft(),
					dh = $(window).height() + $(window).scrollTop();
				// може да се спести е една проверка - дали няма някой от класовете вече нагоре
				if(right_to_left) {
					o[x - (w + 10 + o.outerWidth()) < 0 ? "addClass" : "removeClass"]("vakata-context-left");
				}
				else {
					o[x + w > dw  && xl > dw - x ? "addClass" : "removeClass"]("vakata-context-right");
				}
				if(y + h + 10 > dh) {
					e.css("bottom","-1px");
				}

				//if does not fit - stick it to the side
				if (o.hasClass('vakata-context-right')) {
					if (xl < w) {
						e.css("margin-right", xl - w);
					}
				} else {
					if (dw - x < w) {
						e.css("margin-left", dw - x - w);
					}
				}

				e.show();
			},
			show : function (reference, position, data) {
				var o, e, x, y, w, h, dw, dh, cond = true;
				if(vakata_context.element && vakata_context.element.length) {
					vakata_context.element.width('');
				}
				switch(cond) {
					case (!position && !reference):
						return false;
					case (!!position && !!reference):
						vakata_context.reference	= reference;
						vakata_context.position_x	= position.x;
						vakata_context.position_y	= position.y;
						break;
					case (!position && !!reference):
						vakata_context.reference	= reference;
						o = reference.offset();
						vakata_context.position_x	= o.left + reference.outerHeight();
						vakata_context.position_y	= o.top;
						break;
					case (!!position && !reference):
						vakata_context.position_x	= position.x;
						vakata_context.position_y	= position.y;
						break;
				}
				if(!!reference && !data && $(reference).data('vakata_contextmenu')) {
					data = $(reference).data('vakata_contextmenu');
				}
				if($.vakata.context._parse(data)) {
					vakata_context.element.html(vakata_context.html);
				}
				if(vakata_context.items.length) {
					vakata_context.element.appendTo("body");
					e = vakata_context.element;
					x = vakata_context.position_x;
					y = vakata_context.position_y;
					w = e.width();
					h = e.height();
					dw = $(window).width() + $(window).scrollLeft();
					dh = $(window).height() + $(window).scrollTop();
					if(right_to_left) {
						x -= (e.outerWidth() - $(reference).outerWidth());
						if(x < $(window).scrollLeft() + 20) {
							x = $(window).scrollLeft() + 20;
						}
					}
					if(x + w + 20 > dw) {
						x = dw - (w + 20);
					}
					if(y + h + 20 > dh) {
						y = dh - (h + 20);
					}

					vakata_context.element
						.css({ "left" : x, "top" : y })
						.show()
						.find('a').first().focus().parent().addClass("vakata-context-hover");
					vakata_context.is_visible = true;
					/**
					 * triggered on the document when the contextmenu is shown
					 * @event
					 * @plugin contextmenu
					 * @name context_show.vakata
					 * @param {jQuery} reference the element that was right clicked
					 * @param {jQuery} element the DOM element of the menu itself
					 * @param {Object} position the x & y coordinates of the menu
					 */
					$.vakata.context._trigger("show");
				}
			},
			hide : function () {
				if(vakata_context.is_visible) {
					vakata_context.element.hide().find("ul").hide().end().find(':focus').blur().end().detach();
					vakata_context.is_visible = false;
					/**
					 * triggered on the document when the contextmenu is hidden
					 * @event
					 * @plugin contextmenu
					 * @name context_hide.vakata
					 * @param {jQuery} reference the element that was right clicked
					 * @param {jQuery} element the DOM element of the menu itself
					 * @param {Object} position the x & y coordinates of the menu
					 */
					$.vakata.context._trigger("hide");
				}
			}
		};
		$(function () {
			right_to_left = $("body").css("direction") === "rtl";
			var to = false;

			vakata_context.element = $("<ul class='vakata-context'></ul>");
			vakata_context.element
				.on("mouseenter", "li", function (e) {
					e.stopImmediatePropagation();

					if($.contains(this, e.relatedTarget)) {
						// премахнато заради delegate mouseleave по-долу
						// $(this).find(".vakata-context-hover").removeClass("vakata-context-hover");
						return;
					}

					if(to) { clearTimeout(to); }
					vakata_context.element.find(".vakata-context-hover").removeClass("vakata-context-hover").end();

					$(this)
						.siblings().find("ul").hide().end().end()
						.parentsUntil(".vakata-context", "li").addBack().addClass("vakata-context-hover");
					$.vakata.context._show_submenu(this);
				})
				// тестово - дали не натоварва?
				.on("mouseleave", "li", function (e) {
					if($.contains(this, e.relatedTarget)) { return; }
					$(this).find(".vakata-context-hover").addBack().removeClass("vakata-context-hover");
				})
				.on("mouseleave", function (e) {
					$(this).find(".vakata-context-hover").removeClass("vakata-context-hover");
					if($.vakata.context.settings.hide_onmouseleave) {
						to = setTimeout(
							(function (t) {
								return function () { $.vakata.context.hide(); };
							}(this)), $.vakata.context.settings.hide_onmouseleave);
					}
				})
				.on("click", "a", function (e) {
					e.preventDefault();
				//})
				//.on("mouseup", "a", function (e) {
					if(!$(this).blur().parent().hasClass("vakata-context-disabled") && $.vakata.context._execute($(this).attr("rel")) !== false) {
						$.vakata.context.hide();
					}
				})
				.on('keydown', 'a', function (e) {
						var o = null;
						switch(e.which) {
							case 13:
							case 32:
								e.type = "click";
								e.preventDefault();
								$(e.currentTarget).trigger(e);
								break;
							case 37:
								if(vakata_context.is_visible) {
									vakata_context.element.find(".vakata-context-hover").last().closest("li").first().find("ul").hide().find(".vakata-context-hover").removeClass("vakata-context-hover").end().end().children('a').focus();
									e.stopImmediatePropagation();
									e.preventDefault();
								}
								break;
							case 38:
								if(vakata_context.is_visible) {
									o = vakata_context.element.find("ul:visible").addBack().last().children(".vakata-context-hover").removeClass("vakata-context-hover").prevAll("li:not(.vakata-context-separator)").first();
									if(!o.length) { o = vakata_context.element.find("ul:visible").addBack().last().children("li:not(.vakata-context-separator)").last(); }
									o.addClass("vakata-context-hover").children('a').focus();
									e.stopImmediatePropagation();
									e.preventDefault();
								}
								break;
							case 39:
								if(vakata_context.is_visible) {
									vakata_context.element.find(".vakata-context-hover").last().children("ul").show().children("li:not(.vakata-context-separator)").removeClass("vakata-context-hover").first().addClass("vakata-context-hover").children('a').focus();
									e.stopImmediatePropagation();
									e.preventDefault();
								}
								break;
							case 40:
								if(vakata_context.is_visible) {
									o = vakata_context.element.find("ul:visible").addBack().last().children(".vakata-context-hover").removeClass("vakata-context-hover").nextAll("li:not(.vakata-context-separator)").first();
									if(!o.length) { o = vakata_context.element.find("ul:visible").addBack().last().children("li:not(.vakata-context-separator)").first(); }
									o.addClass("vakata-context-hover").children('a').focus();
									e.stopImmediatePropagation();
									e.preventDefault();
								}
								break;
							case 27:
								$.vakata.context.hide();
								e.preventDefault();
								break;
							default:
								//console.log(e.which);
								break;
						}
					})
				.on('keydown', function (e) {
					e.preventDefault();
					var a = vakata_context.element.find('.vakata-contextmenu-shortcut-' + e.which).parent();
					if(a.parent().not('.vakata-context-disabled')) {
						a.click();
					}
				});

			$(document)
				.on("mousedown.vakata.jstree", function (e) {
					if(vakata_context.is_visible && !$.contains(vakata_context.element[0], e.target)) {
						$.vakata.context.hide();
					}
				})
				.on("context_show.vakata.jstree", function (e, data) {
					vakata_context.element.find("li:has(ul)").children("a").addClass("vakata-context-parent");
					if(right_to_left) {
						vakata_context.element.addClass("vakata-context-rtl").css("direction", "rtl");
					}
					// also apply a RTL class?
					vakata_context.element.find("ul").hide().end();
				});
		});
	}($));
	// $.jstree.defaults.plugins.push("contextmenu");


/**
 * ### Drag'n'drop plugin
 *
 * Enables dragging and dropping of nodes in the tree, resulting in a move or copy operations.
 */

	/**
	 * stores all defaults for the drag'n'drop plugin
	 * @name $.jstree.defaults.dnd
	 * @plugin dnd
	 */
	$.jstree.defaults.dnd = {
		/**
		 * a boolean indicating if a copy should be possible while dragging (by pressint the meta key or Ctrl). Defaults to `true`.
		 * @name $.jstree.defaults.dnd.copy
		 * @plugin dnd
		 */
		copy : true,
		/**
		 * a number indicating how long a node should remain hovered while dragging to be opened. Defaults to `500`.
		 * @name $.jstree.defaults.dnd.open_timeout
		 * @plugin dnd
		 */
		open_timeout : 500,
		/**
		 * a function invoked each time a node is about to be dragged, invoked in the tree's scope and receives the nodes about to be dragged as an argument (array) and the event that started the drag - return `false` to prevent dragging
		 * @name $.jstree.defaults.dnd.is_draggable
		 * @plugin dnd
		 */
		is_draggable : true,
		/**
		 * a boolean indicating if checks should constantly be made while the user is dragging the node (as opposed to checking only on drop), default is `true`
		 * @name $.jstree.defaults.dnd.check_while_dragging
		 * @plugin dnd
		 */
		check_while_dragging : true,
		/**
		 * a boolean indicating if nodes from this tree should only be copied with dnd (as opposed to moved), default is `false`
		 * @name $.jstree.defaults.dnd.always_copy
		 * @plugin dnd
		 */
		always_copy : false,
		/**
		 * when dropping a node "inside", this setting indicates the position the node should go to - it can be an integer or a string: "first" (same as 0) or "last", default is `0`
		 * @name $.jstree.defaults.dnd.inside_pos
		 * @plugin dnd
		 */
		inside_pos : 0,
		/**
		 * when starting the drag on a node that is selected this setting controls if all selected nodes are dragged or only the single node, default is `true`, which means all selected nodes are dragged when the drag is started on a selected node
		 * @name $.jstree.defaults.dnd.drag_selection
		 * @plugin dnd
		 */
		drag_selection : true,
		/**
		 * controls whether dnd works on touch devices. If left as boolean true dnd will work the same as in desktop browsers, which in some cases may impair scrolling. If set to boolean false dnd will not work on touch devices. There is a special third option - string "selected" which means only selected nodes can be dragged on touch devices.
		 * @name $.jstree.defaults.dnd.touch
		 * @plugin dnd
		 */
		touch : true,
		/**
		 * controls whether items can be dropped anywhere on the node, not just on the anchor, by default only the node anchor is a valid drop target. Works best with the wholerow plugin. If enabled on mobile depending on the interface it might be hard for the user to cancel the drop, since the whole tree container will be a valid drop target.
		 * @name $.jstree.defaults.dnd.large_drop_target
		 * @plugin dnd
		 */
		large_drop_target : false,
		/**
		 * controls whether a drag can be initiated from any part of the node and not just the text/icon part, works best with the wholerow plugin. Keep in mind it can cause problems with tree scrolling on mobile depending on the interface - in that case set the touch option to "selected".
		 * @name $.jstree.defaults.dnd.large_drag_target
		 * @plugin dnd
		 */
		large_drag_target : false,
		/**
		 * controls whether use HTML5 dnd api instead of classical. That will allow better integration of dnd events with other HTML5 controls.
		 * @reference http://caniuse.com/#feat=dragndrop
		 * @name $.jstree.defaults.dnd.use_html5
		 * @plugin dnd
		 */
		use_html5: false
	};
	var drg, elm;
	// TODO: now check works by checking for each node individually, how about max_children, unique, etc?
	$.jstree.plugins.dnd = function (options, parent) {
		this.init = function (el, options) {
			parent.init.call(this, el, options);
			this.settings.dnd.use_html5 = this.settings.dnd.use_html5 && ('draggable' in document.createElement('span'));
		};
		this.bind = function () {
			parent.bind.call(this);

			this.element
				.on(this.settings.dnd.use_html5 ? 'dragstart.jstree' : 'mousedown.jstree touchstart.jstree', this.settings.dnd.large_drag_target ? '.jstree-node' : '.jstree-anchor', $.proxy(function (e) {
						if(this.settings.dnd.large_drag_target && $(e.target).closest('.jstree-node')[0] !== e.currentTarget) {
							return true;
						}
						if(e.type === "touchstart" && (!this.settings.dnd.touch || (this.settings.dnd.touch === 'selected' && !$(e.currentTarget).closest('.jstree-node').children('.jstree-anchor').hasClass('jstree-clicked')))) {
							return true;
						}
						var obj = this.get_node(e.target),
							mlt = this.is_selected(obj) && this.settings.dnd.drag_selection ? this.get_top_selected().length : 1,
							txt = (mlt > 1 ? mlt + ' ' + this.get_string('nodes') : this.get_text(e.currentTarget));
						if(this.settings.core.force_text) {
							txt = $.vakata.html.escape(txt);
						}
						if(obj && obj.id && obj.id !== $.jstree.root && (e.which === 1 || e.type === "touchstart" || e.type === "dragstart") &&
							(this.settings.dnd.is_draggable === true || ($.isFunction(this.settings.dnd.is_draggable) && this.settings.dnd.is_draggable.call(this, (mlt > 1 ? this.get_top_selected(true) : [obj]), e)))
						) {
							drg = { 'jstree' : true, 'origin' : this, 'obj' : this.get_node(obj,true), 'nodes' : mlt > 1 ? this.get_top_selected() : [obj.id] };
							elm = e.currentTarget;
							if (this.settings.dnd.use_html5) {
								$.vakata.dnd._trigger('start', e, { 'helper': $(), 'element': elm, 'data': drg });
							} else {
								this.element.trigger('mousedown.jstree');
								return $.vakata.dnd.start(e, drg, '<div id="jstree-dnd" class="jstree-' + this.get_theme() + ' jstree-' + this.get_theme() + '-' + this.get_theme_variant() + ' ' + ( this.settings.core.themes.responsive ? ' jstree-dnd-responsive' : '' ) + '"><i class="jstree-icon jstree-er"></i>' + txt + '<ins class="jstree-copy" style="display:none;">+</ins></div>');
							}
						}
					}, this));
			if (this.settings.dnd.use_html5) {
				this.element
					.on('dragover.jstree', function (e) {
							e.preventDefault();
							$.vakata.dnd._trigger('move', e, { 'helper': $(), 'element': elm, 'data': drg });
							return false;
						})
					//.on('dragenter.jstree', this.settings.dnd.large_drop_target ? '.jstree-node' : '.jstree-anchor', $.proxy(function (e) {
					//		e.preventDefault();
					//		$.vakata.dnd._trigger('move', e, { 'helper': $(), 'element': elm, 'data': drg });
					//		return false;
					//	}, this))
					.on('drop.jstree', $.proxy(function (e) {
							e.preventDefault();
							$.vakata.dnd._trigger('stop', e, { 'helper': $(), 'element': elm, 'data': drg });
							return false;
						}, this));
			}
		};
		this.redraw_node = function(obj, deep, callback, force_render) {
			obj = parent.redraw_node.apply(this, arguments);
			if (obj && this.settings.dnd.use_html5) {
				if (this.settings.dnd.large_drag_target) {
					obj.setAttribute('draggable', true);
				} else {
					var i, j, tmp = null;
					for(i = 0, j = obj.childNodes.length; i < j; i++) {
						if(obj.childNodes[i] && obj.childNodes[i].className && obj.childNodes[i].className.indexOf("jstree-anchor") !== -1) {
							tmp = obj.childNodes[i];
							break;
						}
					}
					if(tmp) {
						tmp.setAttribute('draggable', true);
					}
				}
			}
			return obj;
		};
	};

	$(function() {
		// bind only once for all instances
		var lastmv = false,
			laster = false,
			lastev = false,
			opento = false,
			marker = $('<div id="jstree-marker">&#160;</div>').hide(); //.appendTo('body');

		$(document)
			.on('dnd_start.vakata.jstree', function (e, data) {
				lastmv = false;
				lastev = false;
				if(!data || !data.data || !data.data.jstree) { return; }
				marker.appendTo('body'); //.show();
			})
			.on('dnd_move.vakata.jstree', function (e, data) {
				if(opento) {
					if (!data.event || data.event.type !== 'dragover' || data.event.target !== lastev.target) {
						clearTimeout(opento);
					}
				}
				if(!data || !data.data || !data.data.jstree) { return; }

				// if we are hovering the marker image do nothing (can happen on "inside" drags)
				if(data.event.target.id && data.event.target.id === 'jstree-marker') {
					return;
				}
				lastev = data.event;

				var ins = $.jstree.reference(data.event.target),
					ref = false,
					off = false,
					rel = false,
					tmp, l, t, h, p, i, o, ok, t1, t2, op, ps, pr, ip, tm, is_copy, pn;
				// if we are over an instance
				if(ins && ins._data && ins._data.dnd) {
					marker.attr('class', 'jstree-' + ins.get_theme() + ( ins.settings.core.themes.responsive ? ' jstree-dnd-responsive' : '' ));
					is_copy = data.data.origin && (data.data.origin.settings.dnd.always_copy || (data.data.origin.settings.dnd.copy && (data.event.metaKey || data.event.ctrlKey)));
					data.helper
						.children().attr('class', 'jstree-' + ins.get_theme() + ' jstree-' + ins.get_theme() + '-' + ins.get_theme_variant() + ' ' + ( ins.settings.core.themes.responsive ? ' jstree-dnd-responsive' : '' ))
						.find('.jstree-copy').first()[ is_copy ? 'show' : 'hide' ]();

					// if are hovering the container itself add a new root node
					//console.log(data.event);
					if( (data.event.target === ins.element[0] || data.event.target === ins.get_container_ul()[0]) && ins.get_container_ul().children().length === 0) {
						ok = true;
						for(t1 = 0, t2 = data.data.nodes.length; t1 < t2; t1++) {
							ok = ok && ins.check( (data.data.origin && (data.data.origin.settings.dnd.always_copy || (data.data.origin.settings.dnd.copy && (data.event.metaKey || data.event.ctrlKey)) ) ? "copy_node" : "move_node"), (data.data.origin && data.data.origin !== ins ? data.data.origin.get_node(data.data.nodes[t1]) : data.data.nodes[t1]), $.jstree.root, 'last', { 'dnd' : true, 'ref' : ins.get_node($.jstree.root), 'pos' : 'i', 'origin' : data.data.origin, 'is_multi' : (data.data.origin && data.data.origin !== ins), 'is_foreign' : (!data.data.origin) });
							if(!ok) { break; }
						}
						if(ok) {
							lastmv = { 'ins' : ins, 'par' : $.jstree.root, 'pos' : 'last' };
							marker.hide();
							data.helper.find('.jstree-icon').first().removeClass('jstree-er').addClass('jstree-ok');
							if (data.event.originalEvent && data.event.originalEvent.dataTransfer) {
								data.event.originalEvent.dataTransfer.dropEffect = is_copy ? 'copy' : 'move';
							}
							return;
						}
					}
					else {
						// if we are hovering a tree node
						ref = ins.settings.dnd.large_drop_target ? $(data.event.target).closest('.jstree-node').children('.jstree-anchor') : $(data.event.target).closest('.jstree-anchor');
						if(ref && ref.length && ref.parent().is('.jstree-closed, .jstree-open, .jstree-leaf')) {
							off = ref.offset();
							rel = (data.event.pageY !== undefined ? data.event.pageY : data.event.originalEvent.pageY) - off.top;
							h = ref.outerHeight();
							if(rel < h / 3) {
								o = ['b', 'i', 'a'];
							}
							else if(rel > h - h / 3) {
								o = ['a', 'i', 'b'];
							}
							else {
								o = rel > h / 2 ? ['i', 'a', 'b'] : ['i', 'b', 'a'];
							}
							$.each(o, function (j, v) {
								switch(v) {
									case 'b':
										l = off.left - 6;
										t = off.top;
										p = ins.get_parent(ref);
										i = ref.parent().index();
										break;
									case 'i':
										ip = ins.settings.dnd.inside_pos;
										tm = ins.get_node(ref.parent());
										l = off.left - 2;
										t = off.top + h / 2 + 1;
										p = tm.id;
										i = ip === 'first' ? 0 : (ip === 'last' ? tm.children.length : Math.min(ip, tm.children.length));
										break;
									case 'a':
										l = off.left - 6;
										t = off.top + h;
										p = ins.get_parent(ref);
										i = ref.parent().index() + 1;
										break;
								}
								ok = true;
								for(t1 = 0, t2 = data.data.nodes.length; t1 < t2; t1++) {
									op = data.data.origin && (data.data.origin.settings.dnd.always_copy || (data.data.origin.settings.dnd.copy && (data.event.metaKey || data.event.ctrlKey))) ? "copy_node" : "move_node";
									ps = i;
									if(op === "move_node" && v === 'a' && (data.data.origin && data.data.origin === ins) && p === ins.get_parent(data.data.nodes[t1])) {
										pr = ins.get_node(p);
										if(ps > $.inArray(data.data.nodes[t1], pr.children)) {
											ps -= 1;
										}
									}
									ok = ok && ( (ins && ins.settings && ins.settings.dnd && ins.settings.dnd.check_while_dragging === false) || ins.check(op, (data.data.origin && data.data.origin !== ins ? data.data.origin.get_node(data.data.nodes[t1]) : data.data.nodes[t1]), p, ps, { 'dnd' : true, 'ref' : ins.get_node(ref.parent()), 'pos' : v, 'origin' : data.data.origin, 'is_multi' : (data.data.origin && data.data.origin !== ins), 'is_foreign' : (!data.data.origin) }) );
									if(!ok) {
										if(ins && ins.last_error) { laster = ins.last_error(); }
										break;
									}
								}
								if(v === 'i' && ref.parent().is('.jstree-closed') && ins.settings.dnd.open_timeout) {
									opento = setTimeout((function (x, z) { return function () { x.open_node(z); }; }(ins, ref)), ins.settings.dnd.open_timeout);
								}
								if(ok) {
									pn = ins.get_node(p, true);
									if (!pn.hasClass('.jstree-dnd-parent')) {
										$('.jstree-dnd-parent').removeClass('jstree-dnd-parent');
										pn.addClass('jstree-dnd-parent');
									}
									lastmv = { 'ins' : ins, 'par' : p, 'pos' : v === 'i' && ip === 'last' && i === 0 && !ins.is_loaded(tm) ? 'last' : i };
									marker.css({ 'left' : l + 'px', 'top' : t + 'px' }).show();
									data.helper.find('.jstree-icon').first().removeClass('jstree-er').addClass('jstree-ok');
									if (data.event.originalEvent && data.event.originalEvent.dataTransfer) {
										data.event.originalEvent.dataTransfer.dropEffect = is_copy ? 'copy' : 'move';
									}
									laster = {};
									o = true;
									return false;
								}
							});
							if(o === true) { return; }
						}
					}
				}
				$('.jstree-dnd-parent').removeClass('jstree-dnd-parent');
				lastmv = false;
				data.helper.find('.jstree-icon').removeClass('jstree-ok').addClass('jstree-er');
				if (data.event.originalEvent && data.event.originalEvent.dataTransfer) {
					data.event.originalEvent.dataTransfer.dropEffect = 'none';
				}
				marker.hide();
			})
			.on('dnd_scroll.vakata.jstree', function (e, data) {
				if(!data || !data.data || !data.data.jstree) { return; }
				marker.hide();
				lastmv = false;
				lastev = false;
				data.helper.find('.jstree-icon').first().removeClass('jstree-ok').addClass('jstree-er');
			})
			.on('dnd_stop.vakata.jstree', function (e, data) {
				$('.jstree-dnd-parent').removeClass('jstree-dnd-parent');
				if(opento) { clearTimeout(opento); }
				if(!data || !data.data || !data.data.jstree) { return; }
				marker.hide().detach();
				var i, j, nodes = [];
				if(lastmv) {
					for(i = 0, j = data.data.nodes.length; i < j; i++) {
						nodes[i] = data.data.origin ? data.data.origin.get_node(data.data.nodes[i]) : data.data.nodes[i];
					}
					lastmv.ins[ data.data.origin && (data.data.origin.settings.dnd.always_copy || (data.data.origin.settings.dnd.copy && (data.event.metaKey || data.event.ctrlKey))) ? 'copy_node' : 'move_node' ](nodes, lastmv.par, lastmv.pos, false, false, false, data.data.origin);
				}
				else {
					i = $(data.event.target).closest('.jstree');
					if(i.length && laster && laster.error && laster.error === 'check') {
						i = i.jstree(true);
						if(i) {
							i.settings.core.error.call(this, laster);
						}
					}
				}
				lastev = false;
				lastmv = false;
			})
			.on('keyup.jstree keydown.jstree', function (e, data) {
				data = $.vakata.dnd._get();
				if(data && data.data && data.data.jstree) {
					if (e.type === "keyup" && e.which === 27) {
						if (opento) { clearTimeout(opento); }
						lastmv = false;
						laster = false;
						lastev = false;
						opento = false;
						marker.hide().detach();
						$.vakata.dnd._clean();
					} else {
						data.helper.find('.jstree-copy').first()[ data.data.origin && (data.data.origin.settings.dnd.always_copy || (data.data.origin.settings.dnd.copy && (e.metaKey || e.ctrlKey))) ? 'show' : 'hide' ]();
						if(lastev) {
							lastev.metaKey = e.metaKey;
							lastev.ctrlKey = e.ctrlKey;
							$.vakata.dnd._trigger('move', lastev);
						}
					}
				}
			});
	});

	// helpers
	(function ($) {
		$.vakata.html = {
			div : $('<div />'),
			escape : function (str) {
				return $.vakata.html.div.text(str).html();
			},
			strip : function (str) {
				return $.vakata.html.div.empty().append($.parseHTML(str)).text();
			}
		};
		// private variable
		var vakata_dnd = {
			element	: false,
			target	: false,
			is_down	: false,
			is_drag	: false,
			helper	: false,
			helper_w: 0,
			data	: false,
			init_x	: 0,
			init_y	: 0,
			scroll_l: 0,
			scroll_t: 0,
			scroll_e: false,
			scroll_i: false,
			is_touch: false
		};
		$.vakata.dnd = {
			settings : {
				scroll_speed		: 10,
				scroll_proximity	: 20,
				helper_left			: 5,
				helper_top			: 10,
				threshold			: 5,
				threshold_touch		: 50
			},
			_trigger : function (event_name, e, data) {
				if (data === undefined) {
					data = $.vakata.dnd._get();
				}
				data.event = e;
				$(document).triggerHandler("dnd_" + event_name + ".vakata", data);
			},
			_get : function () {
				return {
					"data"		: vakata_dnd.data,
					"element"	: vakata_dnd.element,
					"helper"	: vakata_dnd.helper
				};
			},
			_clean : function () {
				if(vakata_dnd.helper) { vakata_dnd.helper.remove(); }
				if(vakata_dnd.scroll_i) { clearInterval(vakata_dnd.scroll_i); vakata_dnd.scroll_i = false; }
				vakata_dnd = {
					element	: false,
					target	: false,
					is_down	: false,
					is_drag	: false,
					helper	: false,
					helper_w: 0,
					data	: false,
					init_x	: 0,
					init_y	: 0,
					scroll_l: 0,
					scroll_t: 0,
					scroll_e: false,
					scroll_i: false,
					is_touch: false
				};
				$(document).off("mousemove.vakata.jstree touchmove.vakata.jstree", $.vakata.dnd.drag);
				$(document).off("mouseup.vakata.jstree touchend.vakata.jstree", $.vakata.dnd.stop);
			},
			_scroll : function (init_only) {
				if(!vakata_dnd.scroll_e || (!vakata_dnd.scroll_l && !vakata_dnd.scroll_t)) {
					if(vakata_dnd.scroll_i) { clearInterval(vakata_dnd.scroll_i); vakata_dnd.scroll_i = false; }
					return false;
				}
				if(!vakata_dnd.scroll_i) {
					vakata_dnd.scroll_i = setInterval($.vakata.dnd._scroll, 100);
					return false;
				}
				if(init_only === true) { return false; }

				var i = vakata_dnd.scroll_e.scrollTop(),
					j = vakata_dnd.scroll_e.scrollLeft();
				vakata_dnd.scroll_e.scrollTop(i + vakata_dnd.scroll_t * $.vakata.dnd.settings.scroll_speed);
				vakata_dnd.scroll_e.scrollLeft(j + vakata_dnd.scroll_l * $.vakata.dnd.settings.scroll_speed);
				if(i !== vakata_dnd.scroll_e.scrollTop() || j !== vakata_dnd.scroll_e.scrollLeft()) {
					/**
					 * triggered on the document when a drag causes an element to scroll
					 * @event
					 * @plugin dnd
					 * @name dnd_scroll.vakata
					 * @param {Mixed} data any data supplied with the call to $.vakata.dnd.start
					 * @param {DOM} element the DOM element being dragged
					 * @param {jQuery} helper the helper shown next to the mouse
					 * @param {jQuery} event the element that is scrolling
					 */
					$.vakata.dnd._trigger("scroll", vakata_dnd.scroll_e);
				}
			},
			start : function (e, data, html) {
				if(e.type === "touchstart" && e.originalEvent && e.originalEvent.changedTouches && e.originalEvent.changedTouches[0]) {
					e.pageX = e.originalEvent.changedTouches[0].pageX;
					e.pageY = e.originalEvent.changedTouches[0].pageY;
					e.target = document.elementFromPoint(e.originalEvent.changedTouches[0].pageX - window.pageXOffset, e.originalEvent.changedTouches[0].pageY - window.pageYOffset);
				}
				if(vakata_dnd.is_drag) { $.vakata.dnd.stop({}); }
				try {
					e.currentTarget.unselectable = "on";
					e.currentTarget.onselectstart = function() { return false; };
					if(e.currentTarget.style) {
						e.currentTarget.style.touchAction = "none";
						e.currentTarget.style.msTouchAction = "none";
						e.currentTarget.style.MozUserSelect = "none";
					}
				} catch(ignore) { }
				vakata_dnd.init_x	= e.pageX;
				vakata_dnd.init_y	= e.pageY;
				vakata_dnd.data		= data;
				vakata_dnd.is_down	= true;
				vakata_dnd.element	= e.currentTarget;
				vakata_dnd.target	= e.target;
				vakata_dnd.is_touch	= e.type === "touchstart";
				if(html !== false) {
					vakata_dnd.helper = $("<div id='vakata-dnd'></div>").html(html).css({
						"display"		: "block",
						"margin"		: "0",
						"padding"		: "0",
						"position"		: "absolute",
						"top"			: "-2000px",
						"lineHeight"	: "16px",
						"zIndex"		: "10000"
					});
				}
				$(document).on("mousemove.vakata.jstree touchmove.vakata.jstree", $.vakata.dnd.drag);
				$(document).on("mouseup.vakata.jstree touchend.vakata.jstree", $.vakata.dnd.stop);
				return false;
			},
			drag : function (e) {
				if(e.type === "touchmove" && e.originalEvent && e.originalEvent.changedTouches && e.originalEvent.changedTouches[0]) {
					e.pageX = e.originalEvent.changedTouches[0].pageX;
					e.pageY = e.originalEvent.changedTouches[0].pageY;
					e.target = document.elementFromPoint(e.originalEvent.changedTouches[0].pageX - window.pageXOffset, e.originalEvent.changedTouches[0].pageY - window.pageYOffset);
				}
				if(!vakata_dnd.is_down) { return; }
				if(!vakata_dnd.is_drag) {
					if(
						Math.abs(e.pageX - vakata_dnd.init_x) > (vakata_dnd.is_touch ? $.vakata.dnd.settings.threshold_touch : $.vakata.dnd.settings.threshold) ||
						Math.abs(e.pageY - vakata_dnd.init_y) > (vakata_dnd.is_touch ? $.vakata.dnd.settings.threshold_touch : $.vakata.dnd.settings.threshold)
					) {
						if(vakata_dnd.helper) {
							vakata_dnd.helper.appendTo("body");
							vakata_dnd.helper_w = vakata_dnd.helper.outerWidth();
						}
						vakata_dnd.is_drag = true;
						$(vakata_dnd.target).one('click.vakata', false);
						/**
						 * triggered on the document when a drag starts
						 * @event
						 * @plugin dnd
						 * @name dnd_start.vakata
						 * @param {Mixed} data any data supplied with the call to $.vakata.dnd.start
						 * @param {DOM} element the DOM element being dragged
						 * @param {jQuery} helper the helper shown next to the mouse
						 * @param {Object} event the event that caused the start (probably mousemove)
						 */
						$.vakata.dnd._trigger("start", e);
					}
					else { return; }
				}

				var d  = false, w  = false,
					dh = false, wh = false,
					dw = false, ww = false,
					dt = false, dl = false,
					ht = false, hl = false;

				vakata_dnd.scroll_t = 0;
				vakata_dnd.scroll_l = 0;
				vakata_dnd.scroll_e = false;
				$($(e.target).parentsUntil("body").addBack().get().reverse())
					.filter(function () {
						return	(/^auto|scroll$/).test($(this).css("overflow")) &&
								(this.scrollHeight > this.offsetHeight || this.scrollWidth > this.offsetWidth);
					})
					.each(function () {
						var t = $(this), o = t.offset();
						if(this.scrollHeight > this.offsetHeight) {
							if(o.top + t.height() - e.pageY < $.vakata.dnd.settings.scroll_proximity)	{ vakata_dnd.scroll_t = 1; }
							if(e.pageY - o.top < $.vakata.dnd.settings.scroll_proximity)				{ vakata_dnd.scroll_t = -1; }
						}
						if(this.scrollWidth > this.offsetWidth) {
							if(o.left + t.width() - e.pageX < $.vakata.dnd.settings.scroll_proximity)	{ vakata_dnd.scroll_l = 1; }
							if(e.pageX - o.left < $.vakata.dnd.settings.scroll_proximity)				{ vakata_dnd.scroll_l = -1; }
						}
						if(vakata_dnd.scroll_t || vakata_dnd.scroll_l) {
							vakata_dnd.scroll_e = $(this);
							return false;
						}
					});

				if(!vakata_dnd.scroll_e) {
					d  = $(document); w = $(window);
					dh = d.height(); wh = w.height();
					dw = d.width(); ww = w.width();
					dt = d.scrollTop(); dl = d.scrollLeft();
					if(dh > wh && e.pageY - dt < $.vakata.dnd.settings.scroll_proximity)		{ vakata_dnd.scroll_t = -1;  }
					if(dh > wh && wh - (e.pageY - dt) < $.vakata.dnd.settings.scroll_proximity)	{ vakata_dnd.scroll_t = 1; }
					if(dw > ww && e.pageX - dl < $.vakata.dnd.settings.scroll_proximity)		{ vakata_dnd.scroll_l = -1; }
					if(dw > ww && ww - (e.pageX - dl) < $.vakata.dnd.settings.scroll_proximity)	{ vakata_dnd.scroll_l = 1; }
					if(vakata_dnd.scroll_t || vakata_dnd.scroll_l) {
						vakata_dnd.scroll_e = d;
					}
				}
				if(vakata_dnd.scroll_e) { $.vakata.dnd._scroll(true); }

				if(vakata_dnd.helper) {
					ht = parseInt(e.pageY + $.vakata.dnd.settings.helper_top, 10);
					hl = parseInt(e.pageX + $.vakata.dnd.settings.helper_left, 10);
					if(dh && ht + 25 > dh) { ht = dh - 50; }
					if(dw && hl + vakata_dnd.helper_w > dw) { hl = dw - (vakata_dnd.helper_w + 2); }
					vakata_dnd.helper.css({
						left	: hl + "px",
						top		: ht + "px"
					});
				}
				/**
				 * triggered on the document when a drag is in progress
				 * @event
				 * @plugin dnd
				 * @name dnd_move.vakata
				 * @param {Mixed} data any data supplied with the call to $.vakata.dnd.start
				 * @param {DOM} element the DOM element being dragged
				 * @param {jQuery} helper the helper shown next to the mouse
				 * @param {Object} event the event that caused this to trigger (most likely mousemove)
				 */
				$.vakata.dnd._trigger("move", e);
				return false;
			},
			stop : function (e) {
				if(e.type === "touchend" && e.originalEvent && e.originalEvent.changedTouches && e.originalEvent.changedTouches[0]) {
					e.pageX = e.originalEvent.changedTouches[0].pageX;
					e.pageY = e.originalEvent.changedTouches[0].pageY;
					e.target = document.elementFromPoint(e.originalEvent.changedTouches[0].pageX - window.pageXOffset, e.originalEvent.changedTouches[0].pageY - window.pageYOffset);
				}
				if(vakata_dnd.is_drag) {
					/**
					 * triggered on the document when a drag stops (the dragged element is dropped)
					 * @event
					 * @plugin dnd
					 * @name dnd_stop.vakata
					 * @param {Mixed} data any data supplied with the call to $.vakata.dnd.start
					 * @param {DOM} element the DOM element being dragged
					 * @param {jQuery} helper the helper shown next to the mouse
					 * @param {Object} event the event that caused the stop
					 */
					if (e.target !== vakata_dnd.target) {
						$(vakata_dnd.target).off('click.vakata');
					}
					$.vakata.dnd._trigger("stop", e);
				}
				else {
					if(e.type === "touchend" && e.target === vakata_dnd.target) {
						var to = setTimeout(function () { $(e.target).click(); }, 100);
						$(e.target).one('click', function() { if(to) { clearTimeout(to); } });
					}
				}
				$.vakata.dnd._clean();
				return false;
			}
		};
	}($));

	// include the dnd plugin by default
	// $.jstree.defaults.plugins.push("dnd");


/**
 * ### Massload plugin
 *
 * Adds massload functionality to jsTree, so that multiple nodes can be loaded in a single request (only useful with lazy loading).
 */

	/**
	 * massload configuration
	 *
	 * It is possible to set this to a standard jQuery-like AJAX config.
	 * In addition to the standard jQuery ajax options here you can supply functions for `data` and `url`, the functions will be run in the current instance's scope and a param will be passed indicating which node IDs need to be loaded, the return value of those functions will be used.
	 *
	 * You can also set this to a function, that function will receive the node IDs being loaded as argument and a second param which is a function (callback) which should be called with the result.
	 *
	 * Both the AJAX and the function approach rely on the same return value - an object where the keys are the node IDs, and the value is the children of that node as an array.
	 *
	 *	{
	 *		"id1" : [{ "text" : "Child of ID1", "id" : "c1" }, { "text" : "Another child of ID1", "id" : "c2" }],
	 *		"id2" : [{ "text" : "Child of ID2", "id" : "c3" }]
	 *	}
	 * 
	 * @name $.jstree.defaults.massload
	 * @plugin massload
	 */
	$.jstree.defaults.massload = null;
	$.jstree.plugins.massload = function (options, parent) {
		this.init = function (el, options) {
			this._data.massload = {};
			parent.init.call(this, el, options);
		};
		this._load_nodes = function (nodes, callback, is_callback, force_reload) {
			var s = this.settings.massload,
				nodesString = JSON.stringify(nodes),
				toLoad = [],
				m = this._model.data,
				i, j, dom;
			if (!is_callback) {
				for(i = 0, j = nodes.length; i < j; i++) {
					if(!m[nodes[i]] || ( (!m[nodes[i]].state.loaded && !m[nodes[i]].state.failed) || force_reload) ) {
						toLoad.push(nodes[i]);
						dom = this.get_node(nodes[i], true);
						if (dom && dom.length) {
							dom.addClass("jstree-loading").attr('aria-busy',true);
						}
					}
				}
				this._data.massload = {};
				if (toLoad.length) {
					if($.isFunction(s)) {
						return s.call(this, toLoad, $.proxy(function (data) {
							var i, j;
							if(data) {
								for(i in data) {
									if(data.hasOwnProperty(i)) {
										this._data.massload[i] = data[i];
									}
								}
							}
							for(i = 0, j = nodes.length; i < j; i++) {
								dom = this.get_node(nodes[i], true);
								if (dom && dom.length) {
									dom.removeClass("jstree-loading").attr('aria-busy',false);
								}
							}
							parent._load_nodes.call(this, nodes, callback, is_callback, force_reload);
						}, this));
					}
					if(typeof s === 'object' && s && s.url) {
						s = $.extend(true, {}, s);
						if($.isFunction(s.url)) {
							s.url = s.url.call(this, toLoad);
						}
						if($.isFunction(s.data)) {
							s.data = s.data.call(this, toLoad);
						}
						return $.ajax(s)
							.done($.proxy(function (data,t,x) {
									var i, j;
									if(data) {
										for(i in data) {
											if(data.hasOwnProperty(i)) {
												this._data.massload[i] = data[i];
											}
										}
									}
									for(i = 0, j = nodes.length; i < j; i++) {
										dom = this.get_node(nodes[i], true);
										if (dom && dom.length) {
											dom.removeClass("jstree-loading").attr('aria-busy',false);
										}
									}
									parent._load_nodes.call(this, nodes, callback, is_callback, force_reload);
								}, this))
							.fail($.proxy(function (f) {
									parent._load_nodes.call(this, nodes, callback, is_callback, force_reload);
								}, this));
					}
				}
			}
			return parent._load_nodes.call(this, nodes, callback, is_callback, force_reload);
		};
		this._load_node = function (obj, callback) {
			var data = this._data.massload[obj.id],
				rslt = null, dom;
			if(data) {
				rslt = this[typeof data === 'string' ? '_append_html_data' : '_append_json_data'](
					obj,
					typeof data === 'string' ? $($.parseHTML(data)).filter(function () { return this.nodeType !== 3; }) : data,
					function (status) { callback.call(this, status); }
				);
				dom = this.get_node(obj.id, true);
				if (dom && dom.length) {
					dom.removeClass("jstree-loading").attr('aria-busy',false);
				}
				delete this._data.massload[obj.id];
				return rslt;
			}
			return parent._load_node.call(this, obj, callback);
		};
	};

/**
 * ### Search plugin
 *
 * Adds search functionality to jsTree.
 */

	/**
	 * stores all defaults for the search plugin
	 * @name $.jstree.defaults.search
	 * @plugin search
	 */
	$.jstree.defaults.search = {
		/**
		 * a jQuery-like AJAX config, which jstree uses if a server should be queried for results.
		 *
		 * A `str` (which is the search string) parameter will be added with the request, an optional `inside` parameter will be added if the search is limited to a node id. The expected result is a JSON array with nodes that need to be opened so that matching nodes will be revealed.
		 * Leave this setting as `false` to not query the server. You can also set this to a function, which will be invoked in the instance's scope and receive 3 parameters - the search string, the callback to call with the array of nodes to load, and the optional node ID to limit the search to
		 * @name $.jstree.defaults.search.ajax
		 * @plugin search
		 */
		ajax : false,
		/**
		 * Indicates if the search should be fuzzy or not (should `chnd3` match `child node 3`). Default is `false`.
		 * @name $.jstree.defaults.search.fuzzy
		 * @plugin search
		 */
		fuzzy : false,
		/**
		 * Indicates if the search should be case sensitive. Default is `false`.
		 * @name $.jstree.defaults.search.case_sensitive
		 * @plugin search
		 */
		case_sensitive : false,
		/**
		 * Indicates if the tree should be filtered (by default) to show only matching nodes (keep in mind this can be a heavy on large trees in old browsers).
		 * This setting can be changed at runtime when calling the search method. Default is `false`.
		 * @name $.jstree.defaults.search.show_only_matches
		 * @plugin search
		 */
		show_only_matches : false,
		/**
		 * Indicates if the children of matched element are shown (when show_only_matches is true)
		 * This setting can be changed at runtime when calling the search method. Default is `false`.
		 * @name $.jstree.defaults.search.show_only_matches_children
		 * @plugin search
		 */
		show_only_matches_children : false,
		/**
		 * Indicates if all nodes opened to reveal the search result, should be closed when the search is cleared or a new search is performed. Default is `true`.
		 * @name $.jstree.defaults.search.close_opened_onclear
		 * @plugin search
		 */
		close_opened_onclear : true,
		/**
		 * Indicates if only leaf nodes should be included in search results. Default is `false`.
		 * @name $.jstree.defaults.search.search_leaves_only
		 * @plugin search
		 */
		search_leaves_only : false,
		/**
		 * If set to a function it wil be called in the instance's scope with two arguments - search string and node (where node will be every node in the structure, so use with caution).
		 * If the function returns a truthy value the node will be considered a match (it might not be displayed if search_only_leaves is set to true and the node is not a leaf). Default is `false`.
		 * @name $.jstree.defaults.search.search_callback
		 * @plugin search
		 */
		search_callback : false
	};

	$.jstree.plugins.search = function (options, parent) {
		this.bind = function () {
			parent.bind.call(this);

			this._data.search.str = "";
			this._data.search.dom = $();
			this._data.search.res = [];
			this._data.search.opn = [];
			this._data.search.som = false;
			this._data.search.smc = false;
			this._data.search.hdn = [];

			this.element
				.on("search.jstree", $.proxy(function (e, data) {
						if(this._data.search.som && data.res.length) {
							var m = this._model.data, i, j, p = [], k, l;
							for(i = 0, j = data.res.length; i < j; i++) {
								if(m[data.res[i]] && !m[data.res[i]].state.hidden) {
									p.push(data.res[i]);
									p = p.concat(m[data.res[i]].parents);
									if(this._data.search.smc) {
										for (k = 0, l = m[data.res[i]].children_d.length; k < l; k++) {
											if (m[m[data.res[i]].children_d[k]] && !m[m[data.res[i]].children_d[k]].state.hidden) {
												p.push(m[data.res[i]].children_d[k]);
											}
										}
									}
								}
							}
							p = $.vakata.array_remove_item($.vakata.array_unique(p), $.jstree.root);
							this._data.search.hdn = this.hide_all(true);
							this.show_node(p, true);
							this.redraw(true);
						}
					}, this))
				.on("clear_search.jstree", $.proxy(function (e, data) {
						if(this._data.search.som && data.res.length) {
							this.show_node(this._data.search.hdn, true);
							this.redraw(true);
						}
					}, this));
		};
		/**
		 * used to search the tree nodes for a given string
		 * @name search(str [, skip_async])
		 * @param {String} str the search string
		 * @param {Boolean} skip_async if set to true server will not be queried even if configured
		 * @param {Boolean} show_only_matches if set to true only matching nodes will be shown (keep in mind this can be very slow on large trees or old browsers)
		 * @param {mixed} inside an optional node to whose children to limit the search
		 * @param {Boolean} append if set to true the results of this search are appended to the previous search
		 * @plugin search
		 * @trigger search.jstree
		 */
		this.search = function (str, skip_async, show_only_matches, inside, append, show_only_matches_children) {
			if(str === false || $.trim(str.toString()) === "") {
				return this.clear_search();
			}
			inside = this.get_node(inside);
			inside = inside && inside.id ? inside.id : null;
			str = str.toString();
			var s = this.settings.search,
				a = s.ajax ? s.ajax : false,
				m = this._model.data,
				f = null,
				r = [],
				p = [], i, j;
			if(this._data.search.res.length && !append) {
				this.clear_search();
			}
			if(show_only_matches === undefined) {
				show_only_matches = s.show_only_matches;
			}
			if(show_only_matches_children === undefined) {
				show_only_matches_children = s.show_only_matches_children;
			}
			if(!skip_async && a !== false) {
				if($.isFunction(a)) {
					return a.call(this, str, $.proxy(function (d) {
							if(d && d.d) { d = d.d; }
							this._load_nodes(!$.isArray(d) ? [] : $.vakata.array_unique(d), function () {
								this.search(str, true, show_only_matches, inside, append, show_only_matches_children);
							});
						}, this), inside);
				}
				else {
					a = $.extend({}, a);
					if(!a.data) { a.data = {}; }
					a.data.str = str;
					if(inside) {
						a.data.inside = inside;
					}
					if (this._data.search.lastRequest) {
						this._data.search.lastRequest.abort();
					}
					this._data.search.lastRequest = $.ajax(a)
						.fail($.proxy(function () {
							this._data.core.last_error = { 'error' : 'ajax', 'plugin' : 'search', 'id' : 'search_01', 'reason' : 'Could not load search parents', 'data' : JSON.stringify(a) };
							this.settings.core.error.call(this, this._data.core.last_error);
						}, this))
						.done($.proxy(function (d) {
							if(d && d.d) { d = d.d; }
							this._load_nodes(!$.isArray(d) ? [] : $.vakata.array_unique(d), function () {
								this.search(str, true, show_only_matches, inside, append, show_only_matches_children);
							});
						}, this));
					return this._data.search.lastRequest;
				}
			}
			if(!append) {
				this._data.search.str = str;
				this._data.search.dom = $();
				this._data.search.res = [];
				this._data.search.opn = [];
				this._data.search.som = show_only_matches;
				this._data.search.smc = show_only_matches_children;
			}

			f = new $.vakata.search(str, true, { caseSensitive : s.case_sensitive, fuzzy : s.fuzzy });
			$.each(m[inside ? inside : $.jstree.root].children_d, function (ii, i) {
				var v = m[i];
				if(v.text && !v.state.hidden && (!s.search_leaves_only || (v.state.loaded && v.children.length === 0)) && ( (s.search_callback && s.search_callback.call(this, str, v)) || (!s.search_callback && f.search(v.text).isMatch) ) ) {
					r.push(i);
					p = p.concat(v.parents);
				}
			});
			if(r.length) {
				p = $.vakata.array_unique(p);
				for(i = 0, j = p.length; i < j; i++) {
					if(p[i] !== $.jstree.root && m[p[i]] && this.open_node(p[i], null, 0) === true) {
						this._data.search.opn.push(p[i]);
					}
				}
				if(!append) {
					this._data.search.dom = $(this.element[0].querySelectorAll('#' + $.map(r, function (v) { return "0123456789".indexOf(v[0]) !== -1 ? '\\3' + v[0] + ' ' + v.substr(1).replace($.jstree.idregex,'\\$&') : v.replace($.jstree.idregex,'\\$&'); }).join(', #')));
					this._data.search.res = r;
				}
				else {
					this._data.search.dom = this._data.search.dom.add($(this.element[0].querySelectorAll('#' + $.map(r, function (v) { return "0123456789".indexOf(v[0]) !== -1 ? '\\3' + v[0] + ' ' + v.substr(1).replace($.jstree.idregex,'\\$&') : v.replace($.jstree.idregex,'\\$&'); }).join(', #'))));
					this._data.search.res = $.vakata.array_unique(this._data.search.res.concat(r));
				}
				this._data.search.dom.children(".jstree-anchor").addClass('jstree-search');
			}
			/**
			 * triggered after search is complete
			 * @event
			 * @name search.jstree
			 * @param {jQuery} nodes a jQuery collection of matching nodes
			 * @param {String} str the search string
			 * @param {Array} res a collection of objects represeing the matching nodes
			 * @plugin search
			 */
			this.trigger('search', { nodes : this._data.search.dom, str : str, res : this._data.search.res, show_only_matches : show_only_matches });
		};
		/**
		 * used to clear the last search (removes classes and shows all nodes if filtering is on)
		 * @name clear_search()
		 * @plugin search
		 * @trigger clear_search.jstree
		 */
		this.clear_search = function () {
			if(this.settings.search.close_opened_onclear) {
				this.close_node(this._data.search.opn, 0);
			}
			/**
			 * triggered after search is complete
			 * @event
			 * @name clear_search.jstree
			 * @param {jQuery} nodes a jQuery collection of matching nodes (the result from the last search)
			 * @param {String} str the search string (the last search string)
			 * @param {Array} res a collection of objects represeing the matching nodes (the result from the last search)
			 * @plugin search
			 */
			this.trigger('clear_search', { 'nodes' : this._data.search.dom, str : this._data.search.str, res : this._data.search.res });
			if(this._data.search.res.length) {
				this._data.search.dom = $(this.element[0].querySelectorAll('#' + $.map(this._data.search.res, function (v) {
					return "0123456789".indexOf(v[0]) !== -1 ? '\\3' + v[0] + ' ' + v.substr(1).replace($.jstree.idregex,'\\$&') : v.replace($.jstree.idregex,'\\$&');
				}).join(', #')));
				this._data.search.dom.children(".jstree-anchor").removeClass("jstree-search");
			}
			this._data.search.str = "";
			this._data.search.res = [];
			this._data.search.opn = [];
			this._data.search.dom = $();
		};

		this.redraw_node = function(obj, deep, callback, force_render) {
			obj = parent.redraw_node.apply(this, arguments);
			if(obj) {
				if($.inArray(obj.id, this._data.search.res) !== -1) {
					var i, j, tmp = null;
					for(i = 0, j = obj.childNodes.length; i < j; i++) {
						if(obj.childNodes[i] && obj.childNodes[i].className && obj.childNodes[i].className.indexOf("jstree-anchor") !== -1) {
							tmp = obj.childNodes[i];
							break;
						}
					}
					if(tmp) {
						tmp.className += ' jstree-search';
					}
				}
			}
			return obj;
		};
	};

	// helpers
	(function ($) {
		// from http://kiro.me/projects/fuse.html
		$.vakata.search = function(pattern, txt, options) {
			options = options || {};
			options = $.extend({}, $.vakata.search.defaults, options);
			if(options.fuzzy !== false) {
				options.fuzzy = true;
			}
			pattern = options.caseSensitive ? pattern : pattern.toLowerCase();
			var MATCH_LOCATION	= options.location,
				MATCH_DISTANCE	= options.distance,
				MATCH_THRESHOLD	= options.threshold,
				patternLen = pattern.length,
				matchmask, pattern_alphabet, match_bitapScore, search;
			if(patternLen > 32) {
				options.fuzzy = false;
			}
			if(options.fuzzy) {
				matchmask = 1 << (patternLen - 1);
				pattern_alphabet = (function () {
					var mask = {},
						i = 0;
					for (i = 0; i < patternLen; i++) {
						mask[pattern.charAt(i)] = 0;
					}
					for (i = 0; i < patternLen; i++) {
						mask[pattern.charAt(i)] |= 1 << (patternLen - i - 1);
					}
					return mask;
				}());
				match_bitapScore = function (e, x) {
					var accuracy = e / patternLen,
						proximity = Math.abs(MATCH_LOCATION - x);
					if(!MATCH_DISTANCE) {
						return proximity ? 1.0 : accuracy;
					}
					return accuracy + (proximity / MATCH_DISTANCE);
				};
			}
			search = function (text) {
				text = options.caseSensitive ? text : text.toLowerCase();
				if(pattern === text || text.indexOf(pattern) !== -1) {
					return {
						isMatch: true,
						score: 0
					};
				}
				if(!options.fuzzy) {
					return {
						isMatch: false,
						score: 1
					};
				}
				var i, j,
					textLen = text.length,
					scoreThreshold = MATCH_THRESHOLD,
					bestLoc = text.indexOf(pattern, MATCH_LOCATION),
					binMin, binMid,
					binMax = patternLen + textLen,
					lastRd, start, finish, rd, charMatch,
					score = 1,
					locations = [];
				if (bestLoc !== -1) {
					scoreThreshold = Math.min(match_bitapScore(0, bestLoc), scoreThreshold);
					bestLoc = text.lastIndexOf(pattern, MATCH_LOCATION + patternLen);
					if (bestLoc !== -1) {
						scoreThreshold = Math.min(match_bitapScore(0, bestLoc), scoreThreshold);
					}
				}
				bestLoc = -1;
				for (i = 0; i < patternLen; i++) {
					binMin = 0;
					binMid = binMax;
					while (binMin < binMid) {
						if (match_bitapScore(i, MATCH_LOCATION + binMid) <= scoreThreshold) {
							binMin = binMid;
						} else {
							binMax = binMid;
						}
						binMid = Math.floor((binMax - binMin) / 2 + binMin);
					}
					binMax = binMid;
					start = Math.max(1, MATCH_LOCATION - binMid + 1);
					finish = Math.min(MATCH_LOCATION + binMid, textLen) + patternLen;
					rd = new Array(finish + 2);
					rd[finish + 1] = (1 << i) - 1;
					for (j = finish; j >= start; j--) {
						charMatch = pattern_alphabet[text.charAt(j - 1)];
						if (i === 0) {
							rd[j] = ((rd[j + 1] << 1) | 1) & charMatch;
						} else {
							rd[j] = ((rd[j + 1] << 1) | 1) & charMatch | (((lastRd[j + 1] | lastRd[j]) << 1) | 1) | lastRd[j + 1];
						}
						if (rd[j] & matchmask) {
							score = match_bitapScore(i, j - 1);
							if (score <= scoreThreshold) {
								scoreThreshold = score;
								bestLoc = j - 1;
								locations.push(bestLoc);
								if (bestLoc > MATCH_LOCATION) {
									start = Math.max(1, 2 * MATCH_LOCATION - bestLoc);
								} else {
									break;
								}
							}
						}
					}
					if (match_bitapScore(i + 1, MATCH_LOCATION) > scoreThreshold) {
						break;
					}
					lastRd = rd;
				}
				return {
					isMatch: bestLoc >= 0,
					score: score
				};
			};
			return txt === true ? { 'search' : search } : search(txt);
		};
		$.vakata.search.defaults = {
			location : 0,
			distance : 100,
			threshold : 0.6,
			fuzzy : false,
			caseSensitive : false
		};
	}($));

	// include the search plugin by default
	// $.jstree.defaults.plugins.push("search");


/**
 * ### Sort plugin
 *
 * Automatically sorts all siblings in the tree according to a sorting function.
 */

	/**
	 * the settings function used to sort the nodes.
	 * It is executed in the tree's context, accepts two nodes as arguments and should return `1` or `-1`.
	 * @name $.jstree.defaults.sort
	 * @plugin sort
	 */
	$.jstree.defaults.sort = function (a, b) {
		//return this.get_type(a) === this.get_type(b) ? (this.get_text(a) > this.get_text(b) ? 1 : -1) : this.get_type(a) >= this.get_type(b);
		return this.get_text(a) > this.get_text(b) ? 1 : -1;
	};
	$.jstree.plugins.sort = function (options, parent) {
		this.bind = function () {
			parent.bind.call(this);
			this.element
				.on("model.jstree", $.proxy(function (e, data) {
						this.sort(data.parent, true);
					}, this))
				.on("rename_node.jstree create_node.jstree", $.proxy(function (e, data) {
						this.sort(data.parent || data.node.parent, false);
						this.redraw_node(data.parent || data.node.parent, true);
					}, this))
				.on("move_node.jstree copy_node.jstree", $.proxy(function (e, data) {
						this.sort(data.parent, false);
						this.redraw_node(data.parent, true);
					}, this));
		};
		/**
		 * used to sort a node's children
		 * @private
		 * @name sort(obj [, deep])
		 * @param  {mixed} obj the node
		 * @param {Boolean} deep if set to `true` nodes are sorted recursively.
		 * @plugin sort
		 * @trigger search.jstree
		 */
		this.sort = function (obj, deep) {
			var i, j;
			obj = this.get_node(obj);
			if(obj && obj.children && obj.children.length) {
				obj.children.sort($.proxy(this.settings.sort, this));
				if(deep) {
					for(i = 0, j = obj.children_d.length; i < j; i++) {
						this.sort(obj.children_d[i], false);
					}
				}
			}
		};
	};

	// include the sort plugin by default
	// $.jstree.defaults.plugins.push("sort");

/**
 * ### State plugin
 *
 * Saves the state of the tree (selected nodes, opened nodes) on the user's computer using available options (localStorage, cookies, etc)
 */

	var to = false;
	/**
	 * stores all defaults for the state plugin
	 * @name $.jstree.defaults.state
	 * @plugin state
	 */
	$.jstree.defaults.state = {
		/**
		 * A string for the key to use when saving the current tree (change if using multiple trees in your project). Defaults to `jstree`.
		 * @name $.jstree.defaults.state.key
		 * @plugin state
		 */
		key		: 'jstree',
		/**
		 * A space separated list of events that trigger a state save. Defaults to `changed.jstree open_node.jstree close_node.jstree`.
		 * @name $.jstree.defaults.state.events
		 * @plugin state
		 */
		events	: 'changed.jstree open_node.jstree close_node.jstree check_node.jstree uncheck_node.jstree',
		/**
		 * Time in milliseconds after which the state will expire. Defaults to 'false' meaning - no expire.
		 * @name $.jstree.defaults.state.ttl
		 * @plugin state
		 */
		ttl		: false,
		/**
		 * A function that will be executed prior to restoring state with one argument - the state object. Can be used to clear unwanted parts of the state.
		 * @name $.jstree.defaults.state.filter
		 * @plugin state
		 */
		filter	: false
	};
	$.jstree.plugins.state = function (options, parent) {
		this.bind = function () {
			parent.bind.call(this);
			var bind = $.proxy(function () {
				this.element.on(this.settings.state.events, $.proxy(function () {
					if(to) { clearTimeout(to); }
					to = setTimeout($.proxy(function () { this.save_state(); }, this), 100);
				}, this));
				/**
				 * triggered when the state plugin is finished restoring the state (and immediately after ready if there is no state to restore).
				 * @event
				 * @name state_ready.jstree
				 * @plugin state
				 */
				this.trigger('state_ready');
			}, this);
			this.element
				.on("ready.jstree", $.proxy(function (e, data) {
						this.element.one("restore_state.jstree", bind);
						if(!this.restore_state()) { bind(); }
					}, this));
		};
		/**
		 * save the state
		 * @name save_state()
		 * @plugin state
		 */
		this.save_state = function () {
			var st = { 'state' : this.get_state(), 'ttl' : this.settings.state.ttl, 'sec' : +(new Date()) };
			$.vakata.storage.set(this.settings.state.key, JSON.stringify(st));
		};
		/**
		 * restore the state from the user's computer
		 * @name restore_state()
		 * @plugin state
		 */
		this.restore_state = function () {
			var k = $.vakata.storage.get(this.settings.state.key);
			if(!!k) { try { k = JSON.parse(k); } catch(ex) { return false; } }
			if(!!k && k.ttl && k.sec && +(new Date()) - k.sec > k.ttl) { return false; }
			if(!!k && k.state) { k = k.state; }
			if(!!k && $.isFunction(this.settings.state.filter)) { k = this.settings.state.filter.call(this, k); }
			if(!!k) {
				this.element.one("set_state.jstree", function (e, data) { data.instance.trigger('restore_state', { 'state' : $.extend(true, {}, k) }); });
				this.set_state(k);
				return true;
			}
			return false;
		};
		/**
		 * clear the state on the user's computer
		 * @name clear_state()
		 * @plugin state
		 */
		this.clear_state = function () {
			return $.vakata.storage.del(this.settings.state.key);
		};
	};

	(function ($, undefined) {
		$.vakata.storage = {
			// simply specifying the functions in FF throws an error
			set : function (key, val) { return window.localStorage.setItem(key, val); },
			get : function (key) { return window.localStorage.getItem(key); },
			del : function (key) { return window.localStorage.removeItem(key); }
		};
	}($));

	// include the state plugin by default
	// $.jstree.defaults.plugins.push("state");

/**
 * ### Types plugin
 *
 * Makes it possible to add predefined types for groups of nodes, which make it possible to easily control nesting rules and icon for each group.
 */

	/**
	 * An object storing all types as key value pairs, where the key is the type name and the value is an object that could contain following keys (all optional).
	 *
	 * * `max_children` the maximum number of immediate children this node type can have. Do not specify or set to `-1` for unlimited.
	 * * `max_depth` the maximum number of nesting this node type can have. A value of `1` would mean that the node can have children, but no grandchildren. Do not specify or set to `-1` for unlimited.
	 * * `valid_children` an array of node type strings, that nodes of this type can have as children. Do not specify or set to `-1` for no limits.
	 * * `icon` a string - can be a path to an icon or a className, if using an image that is in the current directory use a `./` prefix, otherwise it will be detected as a class. Omit to use the default icon from your theme.
	 * * `li_attr` an object of values which will be used to add HTML attributes on the resulting LI DOM node (merged with the node's own data)
	 * * `a_attr` an object of values which will be used to add HTML attributes on the resulting A DOM node (merged with the node's own data)
	 *
	 * There are two predefined types:
	 *
	 * * `#` represents the root of the tree, for example `max_children` would control the maximum number of root nodes.
	 * * `default` represents the default node - any settings here will be applied to all nodes that do not have a type specified.
	 *
	 * @name $.jstree.defaults.types
	 * @plugin types
	 */
	$.jstree.defaults.types = {
		'default' : {}
	};
	$.jstree.defaults.types[$.jstree.root] = {};

	$.jstree.plugins.types = function (options, parent) {
		this.init = function (el, options) {
			var i, j;
			if(options && options.types && options.types['default']) {
				for(i in options.types) {
					if(i !== "default" && i !== $.jstree.root && options.types.hasOwnProperty(i)) {
						for(j in options.types['default']) {
							if(options.types['default'].hasOwnProperty(j) && options.types[i][j] === undefined) {
								options.types[i][j] = options.types['default'][j];
							}
						}
					}
				}
			}
			parent.init.call(this, el, options);
			this._model.data[$.jstree.root].type = $.jstree.root;
		};
		this.refresh = function (skip_loading, forget_state) {
			parent.refresh.call(this, skip_loading, forget_state);
			this._model.data[$.jstree.root].type = $.jstree.root;
		};
		this.bind = function () {
			this.element
				.on('model.jstree', $.proxy(function (e, data) {
						var m = this._model.data,
							dpc = data.nodes,
							t = this.settings.types,
							i, j, c = 'default', k;
						for(i = 0, j = dpc.length; i < j; i++) {
							c = 'default';
							if(m[dpc[i]].original && m[dpc[i]].original.type && t[m[dpc[i]].original.type]) {
								c = m[dpc[i]].original.type;
							}
							if(m[dpc[i]].data && m[dpc[i]].data.jstree && m[dpc[i]].data.jstree.type && t[m[dpc[i]].data.jstree.type]) {
								c = m[dpc[i]].data.jstree.type;
							}
							m[dpc[i]].type = c;
							if(m[dpc[i]].icon === true && t[c].icon !== undefined) {
								m[dpc[i]].icon = t[c].icon;
							}
							if(t[c].li_attr !== undefined && typeof t[c].li_attr === 'object') {
								for (k in t[c].li_attr) {
									if (t[c].li_attr.hasOwnProperty(k)) {
										if (k === 'id') {
											continue;
										}
										else if (m[dpc[i]].li_attr[k] === undefined) {
											m[dpc[i]].li_attr[k] = t[c].li_attr[k];
										}
										else if (k === 'class') {
											m[dpc[i]].li_attr['class'] = t[c].li_attr['class'] + ' ' + m[dpc[i]].li_attr['class'];
										}
									}
								}
							}
							if(t[c].a_attr !== undefined && typeof t[c].a_attr === 'object') {
								for (k in t[c].a_attr) {
									if (t[c].a_attr.hasOwnProperty(k)) {
										if (k === 'id') {
											continue;
										}
										else if (m[dpc[i]].a_attr[k] === undefined) {
											m[dpc[i]].a_attr[k] = t[c].a_attr[k];
										}
										else if (k === 'href' && m[dpc[i]].a_attr[k] === '#') {
											m[dpc[i]].a_attr['href'] = t[c].a_attr['href'];
										}
										else if (k === 'class') {
											m[dpc[i]].a_attr['class'] = t[c].a_attr['class'] + ' ' + m[dpc[i]].a_attr['class'];
										}
									}
								}
							}
						}
						m[$.jstree.root].type = $.jstree.root;
					}, this));
			parent.bind.call(this);
		};
		this.get_json = function (obj, options, flat) {
			var i, j,
				m = this._model.data,
				opt = options ? $.extend(true, {}, options, {no_id:false}) : {},
				tmp = parent.get_json.call(this, obj, opt, flat);
			if(tmp === false) { return false; }
			if($.isArray(tmp)) {
				for(i = 0, j = tmp.length; i < j; i++) {
					tmp[i].type = tmp[i].id && m[tmp[i].id] && m[tmp[i].id].type ? m[tmp[i].id].type : "default";
					if(options && options.no_id) {
						delete tmp[i].id;
						if(tmp[i].li_attr && tmp[i].li_attr.id) {
							delete tmp[i].li_attr.id;
						}
						if(tmp[i].a_attr && tmp[i].a_attr.id) {
							delete tmp[i].a_attr.id;
						}
					}
				}
			}
			else {
				tmp.type = tmp.id && m[tmp.id] && m[tmp.id].type ? m[tmp.id].type : "default";
				if(options && options.no_id) {
					tmp = this._delete_ids(tmp);
				}
			}
			return tmp;
		};
		this._delete_ids = function (tmp) {
			if($.isArray(tmp)) {
				for(var i = 0, j = tmp.length; i < j; i++) {
					tmp[i] = this._delete_ids(tmp[i]);
				}
				return tmp;
			}
			delete tmp.id;
			if(tmp.li_attr && tmp.li_attr.id) {
				delete tmp.li_attr.id;
			}
			if(tmp.a_attr && tmp.a_attr.id) {
				delete tmp.a_attr.id;
			}
			if(tmp.children && $.isArray(tmp.children)) {
				tmp.children = this._delete_ids(tmp.children);
			}
			return tmp;
		};
		this.check = function (chk, obj, par, pos, more) {
			if(parent.check.call(this, chk, obj, par, pos, more) === false) { return false; }
			obj = obj && obj.id ? obj : this.get_node(obj);
			par = par && par.id ? par : this.get_node(par);
			var m = obj && obj.id ? (more && more.origin ? more.origin : $.jstree.reference(obj.id)) : null, tmp, d, i, j;
			m = m && m._model && m._model.data ? m._model.data : null;
			switch(chk) {
				case "create_node":
				case "move_node":
				case "copy_node":
					if(chk !== 'move_node' || $.inArray(obj.id, par.children) === -1) {
						tmp = this.get_rules(par);
						if(tmp.max_children !== undefined && tmp.max_children !== -1 && tmp.max_children === par.children.length) {
							this._data.core.last_error = { 'error' : 'check', 'plugin' : 'types', 'id' : 'types_01', 'reason' : 'max_children prevents function: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
							return false;
						}
						if(tmp.valid_children !== undefined && tmp.valid_children !== -1 && $.inArray((obj.type || 'default'), tmp.valid_children) === -1) {
							this._data.core.last_error = { 'error' : 'check', 'plugin' : 'types', 'id' : 'types_02', 'reason' : 'valid_children prevents function: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
							return false;
						}
						if(m && obj.children_d && obj.parents) {
							d = 0;
							for(i = 0, j = obj.children_d.length; i < j; i++) {
								d = Math.max(d, m[obj.children_d[i]].parents.length);
							}
							d = d - obj.parents.length + 1;
						}
						if(d <= 0 || d === undefined) { d = 1; }
						do {
							if(tmp.max_depth !== undefined && tmp.max_depth !== -1 && tmp.max_depth < d) {
								this._data.core.last_error = { 'error' : 'check', 'plugin' : 'types', 'id' : 'types_03', 'reason' : 'max_depth prevents function: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
								return false;
							}
							par = this.get_node(par.parent);
							tmp = this.get_rules(par);
							d++;
						} while(par);
					}
					break;
			}
			return true;
		};
		/**
		 * used to retrieve the type settings object for a node
		 * @name get_rules(obj)
		 * @param {mixed} obj the node to find the rules for
		 * @return {Object}
		 * @plugin types
		 */
		this.get_rules = function (obj) {
			obj = this.get_node(obj);
			if(!obj) { return false; }
			var tmp = this.get_type(obj, true);
			if(tmp.max_depth === undefined) { tmp.max_depth = -1; }
			if(tmp.max_children === undefined) { tmp.max_children = -1; }
			if(tmp.valid_children === undefined) { tmp.valid_children = -1; }
			return tmp;
		};
		/**
		 * used to retrieve the type string or settings object for a node
		 * @name get_type(obj [, rules])
		 * @param {mixed} obj the node to find the rules for
		 * @param {Boolean} rules if set to `true` instead of a string the settings object will be returned
		 * @return {String|Object}
		 * @plugin types
		 */
		this.get_type = function (obj, rules) {
			obj = this.get_node(obj);
			return (!obj) ? false : ( rules ? $.extend({ 'type' : obj.type }, this.settings.types[obj.type]) : obj.type);
		};
		/**
		 * used to change a node's type
		 * @name set_type(obj, type)
		 * @param {mixed} obj the node to change
		 * @param {String} type the new type
		 * @plugin types
		 */
		this.set_type = function (obj, type) {
			var m = this._model.data, t, t1, t2, old_type, old_icon, k, d, a;
			if($.isArray(obj)) {
				obj = obj.slice();
				for(t1 = 0, t2 = obj.length; t1 < t2; t1++) {
					this.set_type(obj[t1], type);
				}
				return true;
			}
			t = this.settings.types;
			obj = this.get_node(obj);
			if(!t[type] || !obj) { return false; }
			d = this.get_node(obj, true);
			if (d && d.length) {
				a = d.children('.jstree-anchor');
			}
			old_type = obj.type;
			old_icon = this.get_icon(obj);
			obj.type = type;
			if(old_icon === true || !t[old_type] || (t[old_type].icon !== undefined && old_icon === t[old_type].icon)) {
				this.set_icon(obj, t[type].icon !== undefined ? t[type].icon : true);
			}

			// remove old type props
			if(t[old_type] && t[old_type].li_attr !== undefined && typeof t[old_type].li_attr === 'object') {
				for (k in t[old_type].li_attr) {
					if (t[old_type].li_attr.hasOwnProperty(k)) {
						if (k === 'id') {
							continue;
						}
						else if (k === 'class') {
							m[obj.id].li_attr['class'] = (m[obj.id].li_attr['class'] || '').replace(t[old_type].li_attr[k], '');
							if (d) { d.removeClass(t[old_type].li_attr[k]); }
						}
						else if (m[obj.id].li_attr[k] === t[old_type].li_attr[k]) {
							m[obj.id].li_attr[k] = null;
							if (d) { d.removeAttr(k); }
						}
					}
				}
			}
			if(t[old_type] && t[old_type].a_attr !== undefined && typeof t[old_type].a_attr === 'object') {
				for (k in t[old_type].a_attr) {
					if (t[old_type].a_attr.hasOwnProperty(k)) {
						if (k === 'id') {
							continue;
						}
						else if (k === 'class') {
							m[obj.id].a_attr['class'] = (m[obj.id].a_attr['class'] || '').replace(t[old_type].a_attr[k], '');
							if (a) { a.removeClass(t[old_type].a_attr[k]); }
						}
						else if (m[obj.id].a_attr[k] === t[old_type].a_attr[k]) {
							if (k === 'href') {
								m[obj.id].a_attr[k] = '#';
								if (a) { a.attr('href', '#'); }
							}
							else {
								delete m[obj.id].a_attr[k];
								if (a) { a.removeAttr(k); }
							}
						}
					}
				}
			}

			// add new props
			if(t[type].li_attr !== undefined && typeof t[type].li_attr === 'object') {
				for (k in t[type].li_attr) {
					if (t[type].li_attr.hasOwnProperty(k)) {
						if (k === 'id') {
							continue;
						}
						else if (m[obj.id].li_attr[k] === undefined) {
							m[obj.id].li_attr[k] = t[type].li_attr[k];
							if (d) {
								if (k === 'class') {
									d.addClass(t[type].li_attr[k]);
								}
								else {
									d.attr(k, t[type].li_attr[k]);
								}
							}
						}
						else if (k === 'class') {
							m[obj.id].li_attr['class'] = t[type].li_attr[k] + ' ' + m[obj.id].li_attr['class'];
							if (d) { d.addClass(t[type].li_attr[k]); }
						}
					}
				}
			}
			if(t[type].a_attr !== undefined && typeof t[type].a_attr === 'object') {
				for (k in t[type].a_attr) {
					if (t[type].a_attr.hasOwnProperty(k)) {
						if (k === 'id') {
							continue;
						}
						else if (m[obj.id].a_attr[k] === undefined) {
							m[obj.id].a_attr[k] = t[type].a_attr[k];
							if (a) {
								if (k === 'class') {
									a.addClass(t[type].a_attr[k]);
								}
								else {
									a.attr(k, t[type].a_attr[k]);
								}
							}
						}
						else if (k === 'href' && m[obj.id].a_attr[k] === '#') {
							m[obj.id].a_attr['href'] = t[type].a_attr['href'];
							if (a) { a.attr('href', t[type].a_attr['href']); }
						}
						else if (k === 'class') {
							m[obj.id].a_attr['class'] = t[type].a_attr['class'] + ' ' + m[obj.id].a_attr['class'];
							if (a) { a.addClass(t[type].a_attr[k]); }
						}
					}
				}
			}

			return true;
		};
	};
	// include the types plugin by default
	// $.jstree.defaults.plugins.push("types");


/**
 * ### Unique plugin
 *
 * Enforces that no nodes with the same name can coexist as siblings.
 */

	/**
	 * stores all defaults for the unique plugin
	 * @name $.jstree.defaults.unique
	 * @plugin unique
	 */
	$.jstree.defaults.unique = {
		/**
		 * Indicates if the comparison should be case sensitive. Default is `false`.
		 * @name $.jstree.defaults.unique.case_sensitive
		 * @plugin unique
		 */
		case_sensitive : false,
		/**
		 * A callback executed in the instance's scope when a new node is created and the name is already taken, the two arguments are the conflicting name and the counter. The default will produce results like `New node (2)`.
		 * @name $.jstree.defaults.unique.duplicate
		 * @plugin unique
		 */
		duplicate : function (name, counter) {
			return name + ' (' + counter + ')';
		}
	};

	$.jstree.plugins.unique = function (options, parent) {
		this.check = function (chk, obj, par, pos, more) {
			if(parent.check.call(this, chk, obj, par, pos, more) === false) { return false; }
			obj = obj && obj.id ? obj : this.get_node(obj);
			par = par && par.id ? par : this.get_node(par);
			if(!par || !par.children) { return true; }
			var n = chk === "rename_node" ? pos : obj.text,
				c = [],
				s = this.settings.unique.case_sensitive,
				m = this._model.data, i, j;
			for(i = 0, j = par.children.length; i < j; i++) {
				c.push(s ? m[par.children[i]].text : m[par.children[i]].text.toLowerCase());
			}
			if(!s) { n = n.toLowerCase(); }
			switch(chk) {
				case "delete_node":
					return true;
				case "rename_node":
					i = ($.inArray(n, c) === -1 || (obj.text && obj.text[ s ? 'toString' : 'toLowerCase']() === n));
					if(!i) {
						this._data.core.last_error = { 'error' : 'check', 'plugin' : 'unique', 'id' : 'unique_01', 'reason' : 'Child with name ' + n + ' already exists. Preventing: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
					}
					return i;
				case "create_node":
					i = ($.inArray(n, c) === -1);
					if(!i) {
						this._data.core.last_error = { 'error' : 'check', 'plugin' : 'unique', 'id' : 'unique_04', 'reason' : 'Child with name ' + n + ' already exists. Preventing: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
					}
					return i;
				case "copy_node":
					i = ($.inArray(n, c) === -1);
					if(!i) {
						this._data.core.last_error = { 'error' : 'check', 'plugin' : 'unique', 'id' : 'unique_02', 'reason' : 'Child with name ' + n + ' already exists. Preventing: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
					}
					return i;
				case "move_node":
					i = ( (obj.parent === par.id && (!more || !more.is_multi)) || $.inArray(n, c) === -1);
					if(!i) {
						this._data.core.last_error = { 'error' : 'check', 'plugin' : 'unique', 'id' : 'unique_03', 'reason' : 'Child with name ' + n + ' already exists. Preventing: ' + chk, 'data' : JSON.stringify({ 'chk' : chk, 'pos' : pos, 'obj' : obj && obj.id ? obj.id : false, 'par' : par && par.id ? par.id : false }) };
					}
					return i;
			}
			return true;
		};
		this.create_node = function (par, node, pos, callback, is_loaded) {
			if(!node || node.text === undefined) {
				if(par === null) {
					par = $.jstree.root;
				}
				par = this.get_node(par);
				if(!par) {
					return parent.create_node.call(this, par, node, pos, callback, is_loaded);
				}
				pos = pos === undefined ? "last" : pos;
				if(!pos.toString().match(/^(before|after)$/) && !is_loaded && !this.is_loaded(par)) {
					return parent.create_node.call(this, par, node, pos, callback, is_loaded);
				}
				if(!node) { node = {}; }
				var tmp, n, dpc, i, j, m = this._model.data, s = this.settings.unique.case_sensitive, cb = this.settings.unique.duplicate;
				n = tmp = this.get_string('New node');
				dpc = [];
				for(i = 0, j = par.children.length; i < j; i++) {
					dpc.push(s ? m[par.children[i]].text : m[par.children[i]].text.toLowerCase());
				}
				i = 1;
				while($.inArray(s ? n : n.toLowerCase(), dpc) !== -1) {
					n = cb.call(this, tmp, (++i)).toString();
				}
				node.text = n;
			}
			return parent.create_node.call(this, par, node, pos, callback, is_loaded);
		};
	};

	// include the unique plugin by default
	// $.jstree.defaults.plugins.push("unique");


/**
 * ### Wholerow plugin
 *
 * Makes each node appear block level. Making selection easier. May cause slow down for large trees in old browsers.
 */

	var div = document.createElement('DIV');
	div.setAttribute('unselectable','on');
	div.setAttribute('role','presentation');
	div.className = 'jstree-wholerow';
	div.innerHTML = '&#160;';
	$.jstree.plugins.wholerow = function (options, parent) {
		this.bind = function () {
			parent.bind.call(this);

			this.element
				.on('ready.jstree set_state.jstree', $.proxy(function () {
						this.hide_dots();
					}, this))
				.on("init.jstree loading.jstree ready.jstree", $.proxy(function () {
						//div.style.height = this._data.core.li_height + 'px';
						this.get_container_ul().addClass('jstree-wholerow-ul');
					}, this))
				.on("deselect_all.jstree", $.proxy(function (e, data) {
						this.element.find('.jstree-wholerow-clicked').removeClass('jstree-wholerow-clicked');
					}, this))
				.on("changed.jstree", $.proxy(function (e, data) {
						this.element.find('.jstree-wholerow-clicked').removeClass('jstree-wholerow-clicked');
						var tmp = false, i, j;
						for(i = 0, j = data.selected.length; i < j; i++) {
							tmp = this.get_node(data.selected[i], true);
							if(tmp && tmp.length) {
								tmp.children('.jstree-wholerow').addClass('jstree-wholerow-clicked');
							}
						}
					}, this))
				.on("open_node.jstree", $.proxy(function (e, data) {
						this.get_node(data.node, true).find('.jstree-clicked').parent().children('.jstree-wholerow').addClass('jstree-wholerow-clicked');
					}, this))
				.on("hover_node.jstree dehover_node.jstree", $.proxy(function (e, data) {
						if(e.type === "hover_node" && this.is_disabled(data.node)) { return; }
						this.get_node(data.node, true).children('.jstree-wholerow')[e.type === "hover_node"?"addClass":"removeClass"]('jstree-wholerow-hovered');
					}, this))
				.on("contextmenu.jstree", ".jstree-wholerow", $.proxy(function (e) {
						if (this._data.contextmenu) {
							e.preventDefault();
							var tmp = $.Event('contextmenu', { metaKey : e.metaKey, ctrlKey : e.ctrlKey, altKey : e.altKey, shiftKey : e.shiftKey, pageX : e.pageX, pageY : e.pageY });
							$(e.currentTarget).closest(".jstree-node").children(".jstree-anchor").first().trigger(tmp);
						}
					}, this))
				/*!
				.on("mousedown.jstree touchstart.jstree", ".jstree-wholerow", function (e) {
						if(e.target === e.currentTarget) {
							var a = $(e.currentTarget).closest(".jstree-node").children(".jstree-anchor");
							e.target = a[0];
							a.trigger(e);
						}
					})
				*/
				.on("click.jstree", ".jstree-wholerow", function (e) {
						e.stopImmediatePropagation();
						var tmp = $.Event('click', { metaKey : e.metaKey, ctrlKey : e.ctrlKey, altKey : e.altKey, shiftKey : e.shiftKey });
						$(e.currentTarget).closest(".jstree-node").children(".jstree-anchor").first().trigger(tmp).focus();
					})
				.on("dblclick.jstree", ".jstree-wholerow", function (e) {
						e.stopImmediatePropagation();
						var tmp = $.Event('dblclick', { metaKey : e.metaKey, ctrlKey : e.ctrlKey, altKey : e.altKey, shiftKey : e.shiftKey });
						$(e.currentTarget).closest(".jstree-node").children(".jstree-anchor").first().trigger(tmp).focus();
					})
				.on("click.jstree", ".jstree-leaf > .jstree-ocl", $.proxy(function (e) {
						e.stopImmediatePropagation();
						var tmp = $.Event('click', { metaKey : e.metaKey, ctrlKey : e.ctrlKey, altKey : e.altKey, shiftKey : e.shiftKey });
						$(e.currentTarget).closest(".jstree-node").children(".jstree-anchor").first().trigger(tmp).focus();
					}, this))
				.on("mouseover.jstree", ".jstree-wholerow, .jstree-icon", $.proxy(function (e) {
						e.stopImmediatePropagation();
						if(!this.is_disabled(e.currentTarget)) {
							this.hover_node(e.currentTarget);
						}
						return false;
					}, this))
				.on("mouseleave.jstree", ".jstree-node", $.proxy(function (e) {
						this.dehover_node(e.currentTarget);
					}, this));
		};
		this.teardown = function () {
			if(this.settings.wholerow) {
				this.element.find(".jstree-wholerow").remove();
			}
			parent.teardown.call(this);
		};
		this.redraw_node = function(obj, deep, callback, force_render) {
			obj = parent.redraw_node.apply(this, arguments);
			if(obj) {
				var tmp = div.cloneNode(true);
				//tmp.style.height = this._data.core.li_height + 'px';
				if($.inArray(obj.id, this._data.core.selected) !== -1) { tmp.className += ' jstree-wholerow-clicked'; }
				if(this._data.core.focused && this._data.core.focused === obj.id) { tmp.className += ' jstree-wholerow-hovered'; }
				obj.insertBefore(tmp, obj.childNodes[0]);
			}
			return obj;
		};
	};
	// include the wholerow plugin by default
	// $.jstree.defaults.plugins.push("wholerow");
	if(document.registerElement && Object && Object.create) {
		var proto = Object.create(HTMLElement.prototype);
		proto.createdCallback = function () {
			var c = { core : {}, plugins : [] }, i;
			for(i in $.jstree.plugins) {
				if($.jstree.plugins.hasOwnProperty(i) && this.attributes[i]) {
					c.plugins.push(i);
					if(this.getAttribute(i) && JSON.parse(this.getAttribute(i))) {
						c[i] = JSON.parse(this.getAttribute(i));
					}
				}
			}
			for(i in $.jstree.defaults.core) {
				if($.jstree.defaults.core.hasOwnProperty(i) && this.attributes[i]) {
					c.core[i] = JSON.parse(this.getAttribute(i)) || this.getAttribute(i);
				}
			}
			$(this).jstree(c);
		};
		// proto.attributeChangedCallback = function (name, previous, value) { };
		try {
			document.registerElement("vakata-jstree", { prototype: proto });
		} catch(ignore) { }
	}

}));
// EXTRACTED FROM COMMCAREHQ main.js
var SaveButton = {
    /*
        options: {
            save: "Function to call when the user clicks Save",
            unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
            csrftoken: "Token required in headers of AJAX request to prevent CSRF"
        }
    */
    init: function (options) {
        var button = {
            disabled: false,
            csrftoken: options.csrftoken,
            $save: $('<span/>').text(SaveButton.message.SAVE).click(function (e) {
                button.fire('save', e);
            }).addClass('btn btn-success'),
            $retry: $('<span/>').text(SaveButton.message.RETRY).click(function (e) {
                button.fire('save', e);
            }).addClass('btn btn-success'),
            $saving: $('<span/>').text(SaveButton.message.SAVING).prepend('<i class="fa fa-refresh icon-spin"></i> ').addClass('btn btn-default disabled'),
            $saved: $('<span/>').text(SaveButton.message.SAVED).addClass('btn btn-default disabled'),
            ui: $('<div/>').addClass('pull-right'),
            setStateWhenReady: function (state) {
                if (this.state === 'saving') {
                    this.nextState = state;
                } else {
                    this.setState(state);
                }
            },
            setState: function (state) {
                if (this.state === state) {
                    return;
                }
                this.state = state;
                this.$save.detach();
                this.$saving.detach();
                this.$saved.detach();
                this.$retry.detach();
                if (state === 'save') {
                    this.ui.append(this.$save);
                } else if (state === 'saving') {
                    this.ui.append(this.$saving);
                } else if (state === 'saved') {
                    this.ui.append(this.$saved);
                } else if (state === 'retry') {
                    this.ui.append(this.$retry);
                }
                this.fire('state:change');
            },
            ajaxOptions: function (options) {
                var options = options || {},
                    beforeSend = options.beforeSend || function () {},
                    success = options.success || function () {},
                    error = options.error || function () {},
                    that = this;
                options.beforeSend = function (xhr) {
                    if (that.csrftoken && !this.crossDomain) {
                        xhr.setRequestHeader("X-CSRFToken", that.csrftoken);
                    }
                    that.setState('saving');
                    that.nextState = 'saved';
                    beforeSend.apply(this, arguments);
                };
                options.success = function (data) {
                    that.setState(that.nextState);
                    success.apply(this, arguments);
                };
                options.error = function (data) {
                    that.nextState = null;
                    that.setState('retry');
                    alert(SaveButton.message.ERROR_SAVING);
                    error.apply(this, arguments);
                };
                return options;
            },
            ajax: function (options) {
                options = button.ajaxOptions(options);

                if (typeof options.url === 'function') {
                    options.beforeSend();
                    var result = options.url(options.data);
                    options.success(result || {});
                } else {
                    $.ajax(options);
                }
            },
            beforeunload: function () {
                var stillAttached = button.ui.parents()[button.ui.parents().length - 1].tagName.toLowerCase() == 'html';
                if (button.state !== 'saved' && stillAttached) {
                    return options.unsavedMessage || "";
                }
            }
        };
        eventize(button);
        button.setState('saved');
        button.on('change', function () {
            this.setStateWhenReady('save');
        });
        button.on('disable', function () {
            this.disabled = true;
            this.$save.addClass('disabled');
            this.$saving.addClass('disabled');
            this.$retry.addClass('disabled');
        });
        button.on('enable', function () {
            this.disabled = false;
            this.$save.removeClass('disabled');
            this.$saving.removeClass('disabled');
            this.$retry.removeClass('disabled');
        });
        button.on('save', function (event) {
            if (button.disabled){
                return;
            } else if (options.save) {
                options.save(event);
            } else if (options.saveRequest){
                var o = button.ajaxOptions();
                o.beforeSend();
                options.saveRequest(event)
                    .success(o.success)
                    .error(o.error)
                ;
            }
        });
        return button;
    },
    initForm: function ($form, options) {
        var url = $form.attr('action'),
            button = SaveButton.init({
                unsavedMessage: options.unsavedMessage,
                save: function () {
                    button.ajax({
                        url: url,
                        type: 'POST',
                        dataType: 'json',
                        data: $form.serialize(),
                        success: options.success
                    });
                }
            }),
            fireChange = function () {
                button.fire('change');
            };
        $form.find('*').change(fireChange);
//        $form.on('textchange', 'input, textarea', fireChange);
        $form.find('input, textarea').bind('textchange', fireChange);
        return button;
    },
    message: {
        SAVE: 'Save',
        SAVING: 'Saving',
        SAVED: 'Saved',
        RETRY: 'Try Again',
        ERROR_SAVING: 'There was an error saving'
    }
};

var eventize = function (that) {
    'use strict';
    var events = {};
    that.on = function (tag, callback) {
        if (events[tag] === undefined) {
            events[tag] = [];
        }
        events[tag].push(callback);
        return that;
    };
    that.fire = function (tag, e) {
        var i;
        if (events[tag] !== undefined) {
            for (i = 0; i < events[tag].length; i += 1) {
                events[tag][i].apply(that, [e]);
            }
        }
        return that;
    };
    return that;
};


define("save-button", ["jquery"], (function (global) {
    return function () {
        var ret, fn;
        return ret || global.SaveButton;
    };
}(this)));

/*
Copyright (c) 2003-2016, CKSource - Frederico Knabben. All rights reserved.
For licensing, see LICENSE.md or http://ckeditor.com/license
*/
(function(){window.CKEDITOR&&window.CKEDITOR.dom||(window.CKEDITOR||(window.CKEDITOR=function(){var a=/(^|.*[\\\/])ckeditor\.js(?:\?.*|;.*)?$/i,e={timestamp:"GB9H",version:"4.6.0 DEV",revision:"e93f6a7",rnd:Math.floor(900*Math.random())+100,_:{pending:[],basePathSrcPattern:a},status:"unloaded",basePath:function(){var d=window.CKEDITOR_BASEPATH||"";if(!d)for(var g=document.getElementsByTagName("script"),e=0;e<g.length;e++){var h=g[e].src.match(a);if(h){d=h[1];break}}-1==d.indexOf(":/")&&"//"!=d.slice(0,
2)&&(d=0===d.indexOf("/")?location.href.match(/^.*?:\/\/[^\/]*/)[0]+d:location.href.match(/^[^\?]*\/(?:)/)[0]+d);if(!d)throw'The CKEditor installation path could not be automatically detected. Please set the global variable "CKEDITOR_BASEPATH" before creating editor instances.';return d}(),getUrl:function(a){-1==a.indexOf(":/")&&0!==a.indexOf("/")&&(a=this.basePath+a);this.timestamp&&"/"!=a.charAt(a.length-1)&&!/[&?]t=/.test(a)&&(a+=(0<=a.indexOf("?")?"\x26":"?")+"t\x3d"+this.timestamp);return a},
domReady:function(){function a(){try{document.addEventListener?(document.removeEventListener("DOMContentLoaded",a,!1),d()):document.attachEvent&&"complete"===document.readyState&&(document.detachEvent("onreadystatechange",a),d())}catch(h){}}function d(){for(var a;a=g.shift();)a()}var g=[];return function(h){function b(){try{document.documentElement.doScroll("left")}catch(f){setTimeout(b,1);return}a()}g.push(h);"complete"===document.readyState&&setTimeout(a,1);if(1==g.length)if(document.addEventListener)document.addEventListener("DOMContentLoaded",
a,!1),window.addEventListener("load",a,!1);else if(document.attachEvent){document.attachEvent("onreadystatechange",a);window.attachEvent("onload",a);h=!1;try{h=!window.frameElement}catch(c){}document.documentElement.doScroll&&h&&b()}}}()},d=window.CKEDITOR_GETURL;if(d){var g=e.getUrl;e.getUrl=function(a){return d.call(e,a)||g.call(e,a)}}return e}()),CKEDITOR.event||(CKEDITOR.event=function(){},CKEDITOR.event.implementOn=function(a){var e=CKEDITOR.event.prototype,d;for(d in e)null==a[d]&&(a[d]=e[d])},
CKEDITOR.event.prototype=function(){function a(a){var l=e(this);return l[a]||(l[a]=new d(a))}var e=function(a){a=a.getPrivate&&a.getPrivate()||a._||(a._={});return a.events||(a.events={})},d=function(a){this.name=a;this.listeners=[]};d.prototype={getListenerIndex:function(a){for(var d=0,e=this.listeners;d<e.length;d++)if(e[d].fn==a)return d;return-1}};return{define:function(d,e){var k=a.call(this,d);CKEDITOR.tools.extend(k,e,!0)},on:function(d,e,k,m,h){function b(f,p,a,b){f={name:d,sender:this,editor:f,
data:p,listenerData:m,stop:a,cancel:b,removeListener:c};return!1===e.call(k,f)?!1:f.data}function c(){p.removeListener(d,e)}var f=a.call(this,d);if(0>f.getListenerIndex(e)){f=f.listeners;k||(k=this);isNaN(h)&&(h=10);var p=this;b.fn=e;b.priority=h;for(var B=f.length-1;0<=B;B--)if(f[B].priority<=h)return f.splice(B+1,0,b),{removeListener:c};f.unshift(b)}return{removeListener:c}},once:function(){var a=Array.prototype.slice.call(arguments),d=a[1];a[1]=function(a){a.removeListener();return d.apply(this,
arguments)};return this.on.apply(this,a)},capture:function(){CKEDITOR.event.useCapture=1;var a=this.on.apply(this,arguments);CKEDITOR.event.useCapture=0;return a},fire:function(){var a=0,d=function(){a=1},k=0,m=function(){k=1};return function(h,b,c){var f=e(this)[h];h=a;var p=k;a=k=0;if(f){var B=f.listeners;if(B.length)for(var B=B.slice(0),x,t=0;t<B.length;t++){if(f.errorProof)try{x=B[t].call(this,c,b,d,m)}catch(u){}else x=B[t].call(this,c,b,d,m);!1===x?k=1:"undefined"!=typeof x&&(b=x);if(a||k)break}}b=
k?!1:"undefined"==typeof b?!0:b;a=h;k=p;return b}}(),fireOnce:function(a,d,k){d=this.fire(a,d,k);delete e(this)[a];return d},removeListener:function(a,d){var k=e(this)[a];if(k){var m=k.getListenerIndex(d);0<=m&&k.listeners.splice(m,1)}},removeAllListeners:function(){var a=e(this),d;for(d in a)delete a[d]},hasListeners:function(a){return(a=e(this)[a])&&0<a.listeners.length}}}()),CKEDITOR.editor||(CKEDITOR.editor=function(){CKEDITOR._.pending.push([this,arguments]);CKEDITOR.event.call(this)},CKEDITOR.editor.prototype.fire=
function(a,e){a in{instanceReady:1,loaded:1}&&(this[a]=!0);return CKEDITOR.event.prototype.fire.call(this,a,e,this)},CKEDITOR.editor.prototype.fireOnce=function(a,e){a in{instanceReady:1,loaded:1}&&(this[a]=!0);return CKEDITOR.event.prototype.fireOnce.call(this,a,e,this)},CKEDITOR.event.implementOn(CKEDITOR.editor.prototype)),CKEDITOR.env||(CKEDITOR.env=function(){var a=navigator.userAgent.toLowerCase(),e=a.match(/edge[ \/](\d+.?\d*)/),d=-1<a.indexOf("trident/"),d=!(!e&&!d),d={ie:d,edge:!!e,webkit:!d&&
-1<a.indexOf(" applewebkit/"),air:-1<a.indexOf(" adobeair/"),mac:-1<a.indexOf("macintosh"),quirks:"BackCompat"==document.compatMode&&(!document.documentMode||10>document.documentMode),mobile:-1<a.indexOf("mobile"),iOS:/(ipad|iphone|ipod)/.test(a),isCustomDomain:function(){if(!this.ie)return!1;var a=document.domain,d=window.location.hostname;return a!=d&&a!="["+d+"]"},secure:"https:"==location.protocol};d.gecko="Gecko"==navigator.product&&!d.webkit&&!d.ie;d.webkit&&(-1<a.indexOf("chrome")?d.chrome=
!0:d.safari=!0);var g=0;d.ie&&(g=e?parseFloat(e[1]):d.quirks||!document.documentMode?parseFloat(a.match(/msie (\d+)/)[1]):document.documentMode,d.ie9Compat=9==g,d.ie8Compat=8==g,d.ie7Compat=7==g,d.ie6Compat=7>g||d.quirks);d.gecko&&(e=a.match(/rv:([\d\.]+)/))&&(e=e[1].split("."),g=1E4*e[0]+100*(e[1]||0)+1*(e[2]||0));d.air&&(g=parseFloat(a.match(/ adobeair\/(\d+)/)[1]));d.webkit&&(g=parseFloat(a.match(/ applewebkit\/(\d+)/)[1]));d.version=g;d.isCompatible=!(d.ie&&7>g)&&!(d.gecko&&4E4>g)&&!(d.webkit&&
534>g);d.hidpi=2<=window.devicePixelRatio;d.needsBrFiller=d.gecko||d.webkit||d.ie&&10<g;d.needsNbspFiller=d.ie&&11>g;d.cssClass="cke_browser_"+(d.ie?"ie":d.gecko?"gecko":d.webkit?"webkit":"unknown");d.quirks&&(d.cssClass+=" cke_browser_quirks");d.ie&&(d.cssClass+=" cke_browser_ie"+(d.quirks?"6 cke_browser_iequirks":d.version));d.air&&(d.cssClass+=" cke_browser_air");d.iOS&&(d.cssClass+=" cke_browser_ios");d.hidpi&&(d.cssClass+=" cke_hidpi");return d}()),"unloaded"==CKEDITOR.status&&function(){CKEDITOR.event.implementOn(CKEDITOR);
CKEDITOR.loadFullCore=function(){if("basic_ready"!=CKEDITOR.status)CKEDITOR.loadFullCore._load=1;else{delete CKEDITOR.loadFullCore;var a=document.createElement("script");a.type="text/javascript";a.src=CKEDITOR.basePath+"ckeditor.js";document.getElementsByTagName("head")[0].appendChild(a)}};CKEDITOR.loadFullCoreTimeout=0;CKEDITOR.add=function(a){(this._.pending||(this._.pending=[])).push(a)};(function(){CKEDITOR.domReady(function(){var a=CKEDITOR.loadFullCore,e=CKEDITOR.loadFullCoreTimeout;a&&(CKEDITOR.status=
"basic_ready",a&&a._load?a():e&&setTimeout(function(){CKEDITOR.loadFullCore&&CKEDITOR.loadFullCore()},1E3*e))})})();CKEDITOR.status="basic_loaded"}(),"use strict",CKEDITOR.VERBOSITY_WARN=1,CKEDITOR.VERBOSITY_ERROR=2,CKEDITOR.verbosity=CKEDITOR.VERBOSITY_WARN|CKEDITOR.VERBOSITY_ERROR,CKEDITOR.warn=function(a,e){CKEDITOR.verbosity&CKEDITOR.VERBOSITY_WARN&&CKEDITOR.fire("log",{type:"warn",errorCode:a,additionalData:e})},CKEDITOR.error=function(a,e){CKEDITOR.verbosity&CKEDITOR.VERBOSITY_ERROR&&CKEDITOR.fire("log",
{type:"error",errorCode:a,additionalData:e})},CKEDITOR.on("log",function(a){if(window.console&&window.console.log){var e=console[a.data.type]?a.data.type:"log",d=a.data.errorCode;if(a=a.data.additionalData)console[e]("[CKEDITOR] Error code: "+d+".",a);else console[e]("[CKEDITOR] Error code: "+d+".");console[e]("[CKEDITOR] For more information about this error go to http://docs.ckeditor.com/#!/guide/dev_errors-section-"+d)}},null,null,999),CKEDITOR.dom={},function(){var a=[],e=CKEDITOR.env.gecko?"-moz-":
CKEDITOR.env.webkit?"-webkit-":CKEDITOR.env.ie?"-ms-":"",d=/&/g,g=/>/g,l=/</g,k=/"/g,m=/&(lt|gt|amp|quot|nbsp|shy|#\d{1,5});/g,h={lt:"\x3c",gt:"\x3e",amp:"\x26",quot:'"',nbsp:" ",shy:"­"},b=function(c,f){return"#"==f[0]?String.fromCharCode(parseInt(f.slice(1),10)):h[f]};CKEDITOR.on("reset",function(){a=[]});CKEDITOR.tools={arrayCompare:function(c,f){if(!c&&!f)return!0;if(!c||!f||c.length!=f.length)return!1;for(var a=0;a<c.length;a++)if(c[a]!=f[a])return!1;return!0},getIndex:function(c,f){for(var a=
0;a<c.length;++a)if(f(c[a]))return a;return-1},clone:function(c){var f;if(c&&c instanceof Array){f=[];for(var a=0;a<c.length;a++)f[a]=CKEDITOR.tools.clone(c[a]);return f}if(null===c||"object"!=typeof c||c instanceof String||c instanceof Number||c instanceof Boolean||c instanceof Date||c instanceof RegExp||c.nodeType||c.window===c)return c;f=new c.constructor;for(a in c)f[a]=CKEDITOR.tools.clone(c[a]);return f},capitalize:function(c,f){return c.charAt(0).toUpperCase()+(f?c.slice(1):c.slice(1).toLowerCase())},
extend:function(c){var f=arguments.length,a,b;"boolean"==typeof(a=arguments[f-1])?f--:"boolean"==typeof(a=arguments[f-2])&&(b=arguments[f-1],f-=2);for(var d=1;d<f;d++){var h=arguments[d],g;for(g in h)if(!0===a||null==c[g])if(!b||g in b)c[g]=h[g]}return c},prototypedCopy:function(c){var f=function(){};f.prototype=c;return new f},copy:function(c){var f={},a;for(a in c)f[a]=c[a];return f},isArray:function(c){return"[object Array]"==Object.prototype.toString.call(c)},isEmpty:function(c){for(var f in c)if(c.hasOwnProperty(f))return!1;
return!0},cssVendorPrefix:function(c,f,a){if(a)return e+c+":"+f+";"+c+":"+f;a={};a[c]=f;a[e+c]=f;return a},cssStyleToDomStyle:function(){var c=document.createElement("div").style,f="undefined"!=typeof c.cssFloat?"cssFloat":"undefined"!=typeof c.styleFloat?"styleFloat":"float";return function(c){return"float"==c?f:c.replace(/-./g,function(f){return f.substr(1).toUpperCase()})}}(),buildStyleHtml:function(c){c=[].concat(c);for(var f,a=[],b=0;b<c.length;b++)if(f=c[b])/@import|[{}]/.test(f)?a.push("\x3cstyle\x3e"+
f+"\x3c/style\x3e"):a.push('\x3clink type\x3d"text/css" rel\x3dstylesheet href\x3d"'+f+'"\x3e');return a.join("")},htmlEncode:function(c){return void 0===c||null===c?"":String(c).replace(d,"\x26amp;").replace(g,"\x26gt;").replace(l,"\x26lt;")},htmlDecode:function(c){return c.replace(m,b)},htmlEncodeAttr:function(c){return CKEDITOR.tools.htmlEncode(c).replace(k,"\x26quot;")},htmlDecodeAttr:function(c){return CKEDITOR.tools.htmlDecode(c)},transformPlainTextToHtml:function(c,f){var a=f==CKEDITOR.ENTER_BR,
b=this.htmlEncode(c.replace(/\r\n/g,"\n")),b=b.replace(/\t/g,"\x26nbsp;\x26nbsp; \x26nbsp;"),d=f==CKEDITOR.ENTER_P?"p":"div";if(!a){var h=/\n{2}/g;if(h.test(b))var g="\x3c"+d+"\x3e",e="\x3c/"+d+"\x3e",b=g+b.replace(h,function(){return e+g})+e}b=b.replace(/\n/g,"\x3cbr\x3e");a||(b=b.replace(new RegExp("\x3cbr\x3e(?\x3d\x3c/"+d+"\x3e)"),function(f){return CKEDITOR.tools.repeat(f,2)}));b=b.replace(/^ | $/g,"\x26nbsp;");return b=b.replace(/(>|\s) /g,function(f,c){return c+"\x26nbsp;"}).replace(/ (?=<)/g,
"\x26nbsp;")},getNextNumber:function(){var c=0;return function(){return++c}}(),getNextId:function(){return"cke_"+this.getNextNumber()},getUniqueId:function(){for(var c="e",f=0;8>f;f++)c+=Math.floor(65536*(1+Math.random())).toString(16).substring(1);return c},override:function(c,f){var a=f(c);a.prototype=c.prototype;return a},setTimeout:function(c,f,a,b,d){d||(d=window);a||(a=d);return d.setTimeout(function(){b?c.apply(a,[].concat(b)):c.apply(a)},f||0)},trim:function(){var c=/(?:^[ \t\n\r]+)|(?:[ \t\n\r]+$)/g;
return function(f){return f.replace(c,"")}}(),ltrim:function(){var c=/^[ \t\n\r]+/g;return function(f){return f.replace(c,"")}}(),rtrim:function(){var c=/[ \t\n\r]+$/g;return function(f){return f.replace(c,"")}}(),indexOf:function(c,f){if("function"==typeof f)for(var a=0,b=c.length;a<b;a++){if(f(c[a]))return a}else{if(c.indexOf)return c.indexOf(f);a=0;for(b=c.length;a<b;a++)if(c[a]===f)return a}return-1},search:function(c,f){var a=CKEDITOR.tools.indexOf(c,f);return 0<=a?c[a]:null},bind:function(c,
f){return function(){return c.apply(f,arguments)}},createClass:function(c){var f=c.$,a=c.base,b=c.privates||c._,d=c.proto;c=c.statics;!f&&(f=function(){a&&this.base.apply(this,arguments)});if(b)var h=f,f=function(){var f=this._||(this._={}),c;for(c in b){var a=b[c];f[c]="function"==typeof a?CKEDITOR.tools.bind(a,this):a}h.apply(this,arguments)};a&&(f.prototype=this.prototypedCopy(a.prototype),f.prototype.constructor=f,f.base=a,f.baseProto=a.prototype,f.prototype.base=function(){this.base=a.prototype.base;
a.apply(this,arguments);this.base=arguments.callee});d&&this.extend(f.prototype,d,!0);c&&this.extend(f,c,!0);return f},addFunction:function(c,f){return a.push(function(){return c.apply(f||this,arguments)})-1},removeFunction:function(c){a[c]=null},callFunction:function(c){var f=a[c];return f&&f.apply(window,Array.prototype.slice.call(arguments,1))},cssLength:function(){var c=/^-?\d+\.?\d*px$/,f;return function(a){f=CKEDITOR.tools.trim(a+"")+"px";return c.test(f)?f:a||""}}(),convertToPx:function(){var c;
return function(f){c||(c=CKEDITOR.dom.element.createFromHtml('\x3cdiv style\x3d"position:absolute;left:-9999px;top:-9999px;margin:0px;padding:0px;border:0px;"\x3e\x3c/div\x3e',CKEDITOR.document),CKEDITOR.document.getBody().append(c));return/%$/.test(f)?f:(c.setStyle("width",f),c.$.clientWidth)}}(),repeat:function(c,f){return Array(f+1).join(c)},tryThese:function(){for(var c,f=0,a=arguments.length;f<a;f++){var b=arguments[f];try{c=b();break}catch(d){}}return c},genKey:function(){return Array.prototype.slice.call(arguments).join("-")},
defer:function(c){return function(){var f=arguments,a=this;window.setTimeout(function(){c.apply(a,f)},0)}},normalizeCssText:function(c,f){var a=[],b,d=CKEDITOR.tools.parseCssText(c,!0,f);for(b in d)a.push(b+":"+d[b]);a.sort();return a.length?a.join(";")+";":""},convertRgbToHex:function(c){return c.replace(/(?:rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\))/gi,function(f,c,a,b){f=[c,a,b];for(c=0;3>c;c++)f[c]=("0"+parseInt(f[c],10).toString(16)).slice(-2);return"#"+f.join("")})},normalizeHex:function(c){return c.replace(/#(([0-9a-f]{3}){1,2})($|;|\s+)/gi,
function(f,c,a,b){f=c.toLowerCase();3==f.length&&(f=f.split(""),f=[f[0],f[0],f[1],f[1],f[2],f[2]].join(""));return"#"+f+b})},parseCssText:function(c,f,a){var b={};a&&(c=(new CKEDITOR.dom.element("span")).setAttribute("style",c).getAttribute("style")||"");c&&(c=CKEDITOR.tools.normalizeHex(CKEDITOR.tools.convertRgbToHex(c)));if(!c||";"==c)return b;c.replace(/&quot;/g,'"').replace(/\s*([^:;\s]+)\s*:\s*([^;]+)\s*(?=;|$)/g,function(c,a,p){f&&(a=a.toLowerCase(),"font-family"==a&&(p=p.replace(/\s*,\s*/g,
",")),p=CKEDITOR.tools.trim(p));b[a]=p});return b},writeCssText:function(c,f){var a,b=[];for(a in c)b.push(a+":"+c[a]);f&&b.sort();return b.join("; ")},objectCompare:function(c,f,a){var b;if(!c&&!f)return!0;if(!c||!f)return!1;for(b in c)if(c[b]!=f[b])return!1;if(!a)for(b in f)if(c[b]!=f[b])return!1;return!0},objectKeys:function(c){var f=[],a;for(a in c)f.push(a);return f},convertArrayToObject:function(c,f){var a={};1==arguments.length&&(f=!0);for(var b=0,d=c.length;b<d;++b)a[c[b]]=f;return a},fixDomain:function(){for(var a;;)try{a=
window.parent.document.domain;break}catch(f){a=a?a.replace(/.+?(?:\.|$)/,""):document.domain;if(!a)break;document.domain=a}return!!a},eventsBuffer:function(a,f,b){function d(){g=(new Date).getTime();h=!1;b?f.call(b):f()}var h,g=0;return{input:function(){if(!h){var f=(new Date).getTime()-g;f<a?h=setTimeout(d,a-f):d()}},reset:function(){h&&clearTimeout(h);h=g=0}}},enableHtml5Elements:function(a,f){for(var b="abbr article aside audio bdi canvas data datalist details figcaption figure footer header hgroup main mark meter nav output progress section summary time video".split(" "),
d=b.length,h;d--;)h=a.createElement(b[d]),f&&a.appendChild(h)},checkIfAnyArrayItemMatches:function(a,f){for(var b=0,d=a.length;b<d;++b)if(a[b].match(f))return!0;return!1},checkIfAnyObjectPropertyMatches:function(a,f){for(var b in a)if(b.match(f))return!0;return!1},keystrokeToString:function(a,f){var b=f&16711680,d=f&65535,h=CKEDITOR.env.mac,g=[],e=[];b&CKEDITOR.CTRL&&(g.push(h?"⌘":a[17]),e.push(h?a[224]:a[17]));b&CKEDITOR.ALT&&(g.push(h?"⌥":a[18]),e.push(a[18]));b&CKEDITOR.SHIFT&&(g.push(h?"⇧":a[16]),
e.push(a[16]));d&&(a[d]?(g.push(a[d]),e.push(a[d])):(g.push(String.fromCharCode(d)),e.push(String.fromCharCode(d))));return{display:g.join("+"),aria:e.join("+")}},transparentImageData:"data:image/gif;base64,R0lGODlhAQABAPABAP///wAAACH5BAEKAAAALAAAAAABAAEAAAICRAEAOw\x3d\x3d",getCookie:function(a){a=a.toLowerCase();for(var f=document.cookie.split(";"),b,d,h=0;h<f.length;h++)if(b=f[h].split("\x3d"),d=decodeURIComponent(CKEDITOR.tools.trim(b[0]).toLowerCase()),d===a)return decodeURIComponent(1<b.length?
b[1]:"");return null},setCookie:function(a,f){document.cookie=encodeURIComponent(a)+"\x3d"+encodeURIComponent(f)+";path\x3d/"},getCsrfToken:function(){var a=CKEDITOR.tools.getCookie("ckCsrfToken");if(!a||40!=a.length){var a=[],f="";if(window.crypto&&window.crypto.getRandomValues)a=new Uint8Array(40),window.crypto.getRandomValues(a);else for(var b=0;40>b;b++)a.push(Math.floor(256*Math.random()));for(b=0;b<a.length;b++)var d="abcdefghijklmnopqrstuvwxyz0123456789".charAt(a[b]%36),f=f+(.5<Math.random()?
d.toUpperCase():d);a=f;CKEDITOR.tools.setCookie("ckCsrfToken",a)}return a},escapeCss:function(a){return a?window.CSS&&CSS.escape?CSS.escape(a):isNaN(parseInt(a.charAt(0),10))?a:"\\3"+a.charAt(0)+" "+a.substring(1,a.length):""},style:{parse:{_colors:{aliceblue:"#F0F8FF",antiquewhite:"#FAEBD7",aqua:"#00FFFF",aquamarine:"#7FFFD4",azure:"#F0FFFF",beige:"#F5F5DC",bisque:"#FFE4C4",black:"#000000",blanchedalmond:"#FFEBCD",blue:"#0000FF",blueviolet:"#8A2BE2",brown:"#A52A2A",burlywood:"#DEB887",cadetblue:"#5F9EA0",
chartreuse:"#7FFF00",chocolate:"#D2691E",coral:"#FF7F50",cornflowerblue:"#6495ED",cornsilk:"#FFF8DC",crimson:"#DC143C",cyan:"#00FFFF",darkblue:"#00008B",darkcyan:"#008B8B",darkgoldenrod:"#B8860B",darkgray:"#A9A9A9",darkgreen:"#006400",darkgrey:"#A9A9A9",darkkhaki:"#BDB76B",darkmagenta:"#8B008B",darkolivegreen:"#556B2F",darkorange:"#FF8C00",darkorchid:"#9932CC",darkred:"#8B0000",darksalmon:"#E9967A",darkseagreen:"#8FBC8F",darkslateblue:"#483D8B",darkslategray:"#2F4F4F",darkslategrey:"#2F4F4F",darkturquoise:"#00CED1",
darkviolet:"#9400D3",deeppink:"#FF1493",deepskyblue:"#00BFFF",dimgray:"#696969",dimgrey:"#696969",dodgerblue:"#1E90FF",firebrick:"#B22222",floralwhite:"#FFFAF0",forestgreen:"#228B22",fuchsia:"#FF00FF",gainsboro:"#DCDCDC",ghostwhite:"#F8F8FF",gold:"#FFD700",goldenrod:"#DAA520",gray:"#808080",green:"#008000",greenyellow:"#ADFF2F",grey:"#808080",honeydew:"#F0FFF0",hotpink:"#FF69B4",indianred:"#CD5C5C",indigo:"#4B0082",ivory:"#FFFFF0",khaki:"#F0E68C",lavender:"#E6E6FA",lavenderblush:"#FFF0F5",lawngreen:"#7CFC00",
lemonchiffon:"#FFFACD",lightblue:"#ADD8E6",lightcoral:"#F08080",lightcyan:"#E0FFFF",lightgoldenrodyellow:"#FAFAD2",lightgray:"#D3D3D3",lightgreen:"#90EE90",lightgrey:"#D3D3D3",lightpink:"#FFB6C1",lightsalmon:"#FFA07A",lightseagreen:"#20B2AA",lightskyblue:"#87CEFA",lightslategray:"#778899",lightslategrey:"#778899",lightsteelblue:"#B0C4DE",lightyellow:"#FFFFE0",lime:"#00FF00",limegreen:"#32CD32",linen:"#FAF0E6",magenta:"#FF00FF",maroon:"#800000",mediumaquamarine:"#66CDAA",mediumblue:"#0000CD",mediumorchid:"#BA55D3",
mediumpurple:"#9370DB",mediumseagreen:"#3CB371",mediumslateblue:"#7B68EE",mediumspringgreen:"#00FA9A",mediumturquoise:"#48D1CC",mediumvioletred:"#C71585",midnightblue:"#191970",mintcream:"#F5FFFA",mistyrose:"#FFE4E1",moccasin:"#FFE4B5",navajowhite:"#FFDEAD",navy:"#000080",oldlace:"#FDF5E6",olive:"#808000",olivedrab:"#6B8E23",orange:"#FFA500",orangered:"#FF4500",orchid:"#DA70D6",palegoldenrod:"#EEE8AA",palegreen:"#98FB98",paleturquoise:"#AFEEEE",palevioletred:"#DB7093",papayawhip:"#FFEFD5",peachpuff:"#FFDAB9",
peru:"#CD853F",pink:"#FFC0CB",plum:"#DDA0DD",powderblue:"#B0E0E6",purple:"#800080",rebeccapurple:"#663399",red:"#FF0000",rosybrown:"#BC8F8F",royalblue:"#4169E1",saddlebrown:"#8B4513",salmon:"#FA8072",sandybrown:"#F4A460",seagreen:"#2E8B57",seashell:"#FFF5EE",sienna:"#A0522D",silver:"#C0C0C0",skyblue:"#87CEEB",slateblue:"#6A5ACD",slategray:"#708090",slategrey:"#708090",snow:"#FFFAFA",springgreen:"#00FF7F",steelblue:"#4682B4",tan:"#D2B48C",teal:"#008080",thistle:"#D8BFD8",tomato:"#FF6347",turquoise:"#40E0D0",
violet:"#EE82EE",wheat:"#F5DEB3",white:"#FFFFFF",whitesmoke:"#F5F5F5",yellow:"#FFFF00",yellowgreen:"#9ACD32"},_rgbaRegExp:/rgba?\(\s*\d+%?\s*,\s*\d+%?\s*,\s*\d+%?\s*(?:,\s*[0-9.]+\s*)?\)/gi,_hslaRegExp:/hsla?\(\s*[0-9.]+\s*,\s*\d+%\s*,\s*\d+%\s*(?:,\s*[0-9.]+\s*)?\)/gi,background:function(a){var f=[],b=[],b=this._findColor(a);b.length&&(f.color=b[0],CKEDITOR.tools.array.forEach(b,function(f){a=a.replace(f,"")}));if(a=CKEDITOR.tools.trim(a))f.unprocessed=a;return f},margin:function(a){function f(f){b.top=
d[f[0]];b.right=d[f[1]];b.bottom=d[f[2]];b.left=d[f[3]]}var b={},d=a.match(/(?:\-?[\.\d]+(?:%|\w*)|auto|inherit|initial|unset)/g)||["0px"];switch(d.length){case 1:f([0,0,0,0]);break;case 2:f([0,1,0,1]);break;case 3:f([0,1,2,1]);break;case 4:f([0,1,2,3])}return b},_findColor:function(a){var f=[],b=CKEDITOR.tools.array,f=f.concat(a.match(this._rgbaRegExp)||[]),f=f.concat(a.match(this._hslaRegExp)||[]);return f=f.concat(b.filter(a.split(/\s+/),function(f){return f.match(/^\#[a-f0-9]{3}(?:[a-f0-9]{3})?$/gi)?
!0:f.toLowerCase()in CKEDITOR.tools.style.parse._colors}))}}},array:{filter:function(a,f,b){var d=[];this.forEach(a,function(h,g){f.call(b,h,g,a)&&d.push(h)});return d},forEach:function(a,f,b){var d=a.length,h;for(h=0;h<d;h++)f.call(b,a[h],h,a)}}};CKEDITOR.tools.array.indexOf=CKEDITOR.tools.indexOf;CKEDITOR.tools.array.isArray=CKEDITOR.tools.isArray}(),CKEDITOR.dtd=function(){var a=CKEDITOR.tools.extend,e=function(a,f){for(var b=CKEDITOR.tools.clone(a),d=1;d<arguments.length;d++){f=arguments[d];for(var h in f)delete b[h]}return b},
d={},g={},l={address:1,article:1,aside:1,blockquote:1,details:1,div:1,dl:1,fieldset:1,figure:1,footer:1,form:1,h1:1,h2:1,h3:1,h4:1,h5:1,h6:1,header:1,hgroup:1,hr:1,main:1,menu:1,nav:1,ol:1,p:1,pre:1,section:1,table:1,ul:1},k={command:1,link:1,meta:1,noscript:1,script:1,style:1},m={},h={"#":1},b={center:1,dir:1,noframes:1};a(d,{a:1,abbr:1,area:1,audio:1,b:1,bdi:1,bdo:1,br:1,button:1,canvas:1,cite:1,code:1,command:1,datalist:1,del:1,dfn:1,em:1,embed:1,i:1,iframe:1,img:1,input:1,ins:1,kbd:1,keygen:1,
label:1,map:1,mark:1,meter:1,noscript:1,object:1,output:1,progress:1,q:1,ruby:1,s:1,samp:1,script:1,select:1,small:1,span:1,strong:1,sub:1,sup:1,textarea:1,time:1,u:1,"var":1,video:1,wbr:1},h,{acronym:1,applet:1,basefont:1,big:1,font:1,isindex:1,strike:1,style:1,tt:1});a(g,l,d,b);e={a:e(d,{a:1,button:1}),abbr:d,address:g,area:m,article:g,aside:g,audio:a({source:1,track:1},g),b:d,base:m,bdi:d,bdo:d,blockquote:g,body:g,br:m,button:e(d,{a:1,button:1}),canvas:d,caption:g,cite:d,code:d,col:m,colgroup:{col:1},
command:m,datalist:a({option:1},d),dd:g,del:d,details:a({summary:1},g),dfn:d,div:g,dl:{dt:1,dd:1},dt:g,em:d,embed:m,fieldset:a({legend:1},g),figcaption:g,figure:a({figcaption:1},g),footer:g,form:g,h1:d,h2:d,h3:d,h4:d,h5:d,h6:d,head:a({title:1,base:1},k),header:g,hgroup:{h1:1,h2:1,h3:1,h4:1,h5:1,h6:1},hr:m,html:a({head:1,body:1},g,k),i:d,iframe:h,img:m,input:m,ins:d,kbd:d,keygen:m,label:d,legend:d,li:g,link:m,main:g,map:g,mark:d,menu:a({li:1},g),meta:m,meter:e(d,{meter:1}),nav:g,noscript:a({link:1,
meta:1,style:1},d),object:a({param:1},d),ol:{li:1},optgroup:{option:1},option:h,output:d,p:d,param:m,pre:d,progress:e(d,{progress:1}),q:d,rp:d,rt:d,ruby:a({rp:1,rt:1},d),s:d,samp:d,script:h,section:g,select:{optgroup:1,option:1},small:d,source:m,span:d,strong:d,style:h,sub:d,summary:a({h1:1,h2:1,h3:1,h4:1,h5:1,h6:1},d),sup:d,table:{caption:1,colgroup:1,thead:1,tfoot:1,tbody:1,tr:1},tbody:{tr:1},td:g,textarea:h,tfoot:{tr:1},th:g,thead:{tr:1},time:e(d,{time:1}),title:h,tr:{th:1,td:1},track:m,u:d,ul:{li:1},
"var":d,video:a({source:1,track:1},g),wbr:m,acronym:d,applet:a({param:1},g),basefont:m,big:d,center:g,dialog:m,dir:{li:1},font:d,isindex:m,noframes:g,strike:d,tt:d};a(e,{$block:a({audio:1,dd:1,dt:1,figcaption:1,li:1,video:1},l,b),$blockLimit:{article:1,aside:1,audio:1,body:1,caption:1,details:1,dir:1,div:1,dl:1,fieldset:1,figcaption:1,figure:1,footer:1,form:1,header:1,hgroup:1,main:1,menu:1,nav:1,ol:1,section:1,table:1,td:1,th:1,tr:1,ul:1,video:1},$cdata:{script:1,style:1},$editable:{address:1,article:1,
aside:1,blockquote:1,body:1,details:1,div:1,fieldset:1,figcaption:1,footer:1,form:1,h1:1,h2:1,h3:1,h4:1,h5:1,h6:1,header:1,hgroup:1,main:1,nav:1,p:1,pre:1,section:1},$empty:{area:1,base:1,basefont:1,br:1,col:1,command:1,dialog:1,embed:1,hr:1,img:1,input:1,isindex:1,keygen:1,link:1,meta:1,param:1,source:1,track:1,wbr:1},$inline:d,$list:{dl:1,ol:1,ul:1},$listItem:{dd:1,dt:1,li:1},$nonBodyContent:a({body:1,head:1,html:1},e.head),$nonEditable:{applet:1,audio:1,button:1,embed:1,iframe:1,map:1,object:1,
option:1,param:1,script:1,textarea:1,video:1},$object:{applet:1,audio:1,button:1,hr:1,iframe:1,img:1,input:1,object:1,select:1,table:1,textarea:1,video:1},$removeEmpty:{abbr:1,acronym:1,b:1,bdi:1,bdo:1,big:1,cite:1,code:1,del:1,dfn:1,em:1,font:1,i:1,ins:1,label:1,kbd:1,mark:1,meter:1,output:1,q:1,ruby:1,s:1,samp:1,small:1,span:1,strike:1,strong:1,sub:1,sup:1,time:1,tt:1,u:1,"var":1},$tabIndex:{a:1,area:1,button:1,input:1,object:1,select:1,textarea:1},$tableContent:{caption:1,col:1,colgroup:1,tbody:1,
td:1,tfoot:1,th:1,thead:1,tr:1},$transparent:{a:1,audio:1,canvas:1,del:1,ins:1,map:1,noscript:1,object:1,video:1},$intermediate:{caption:1,colgroup:1,dd:1,dt:1,figcaption:1,legend:1,li:1,optgroup:1,option:1,rp:1,rt:1,summary:1,tbody:1,td:1,tfoot:1,th:1,thead:1,tr:1}});return e}(),CKEDITOR.dom.event=function(a){this.$=a},CKEDITOR.dom.event.prototype={getKey:function(){return this.$.keyCode||this.$.which},getKeystroke:function(){var a=this.getKey();if(this.$.ctrlKey||this.$.metaKey)a+=CKEDITOR.CTRL;
this.$.shiftKey&&(a+=CKEDITOR.SHIFT);this.$.altKey&&(a+=CKEDITOR.ALT);return a},preventDefault:function(a){var e=this.$;e.preventDefault?e.preventDefault():e.returnValue=!1;a&&this.stopPropagation()},stopPropagation:function(){var a=this.$;a.stopPropagation?a.stopPropagation():a.cancelBubble=!0},getTarget:function(){var a=this.$.target||this.$.srcElement;return a?new CKEDITOR.dom.node(a):null},getPhase:function(){return this.$.eventPhase||2},getPageOffset:function(){var a=this.getTarget().getDocument().$;
return{x:this.$.pageX||this.$.clientX+(a.documentElement.scrollLeft||a.body.scrollLeft),y:this.$.pageY||this.$.clientY+(a.documentElement.scrollTop||a.body.scrollTop)}}},CKEDITOR.CTRL=1114112,CKEDITOR.SHIFT=2228224,CKEDITOR.ALT=4456448,CKEDITOR.EVENT_PHASE_CAPTURING=1,CKEDITOR.EVENT_PHASE_AT_TARGET=2,CKEDITOR.EVENT_PHASE_BUBBLING=3,CKEDITOR.dom.domObject=function(a){a&&(this.$=a)},CKEDITOR.dom.domObject.prototype=function(){var a=function(a,d){return function(g){"undefined"!=typeof CKEDITOR&&a.fire(d,
new CKEDITOR.dom.event(g))}};return{getPrivate:function(){var a;(a=this.getCustomData("_"))||this.setCustomData("_",a={});return a},on:function(e){var d=this.getCustomData("_cke_nativeListeners");d||(d={},this.setCustomData("_cke_nativeListeners",d));d[e]||(d=d[e]=a(this,e),this.$.addEventListener?this.$.addEventListener(e,d,!!CKEDITOR.event.useCapture):this.$.attachEvent&&this.$.attachEvent("on"+e,d));return CKEDITOR.event.prototype.on.apply(this,arguments)},removeListener:function(a){CKEDITOR.event.prototype.removeListener.apply(this,
arguments);if(!this.hasListeners(a)){var d=this.getCustomData("_cke_nativeListeners"),g=d&&d[a];g&&(this.$.removeEventListener?this.$.removeEventListener(a,g,!1):this.$.detachEvent&&this.$.detachEvent("on"+a,g),delete d[a])}},removeAllListeners:function(){var a=this.getCustomData("_cke_nativeListeners"),d;for(d in a){var g=a[d];this.$.detachEvent?this.$.detachEvent("on"+d,g):this.$.removeEventListener&&this.$.removeEventListener(d,g,!1);delete a[d]}CKEDITOR.event.prototype.removeAllListeners.call(this)}}}(),
function(a){var e={};CKEDITOR.on("reset",function(){e={}});a.equals=function(a){try{return a&&a.$===this.$}catch(g){return!1}};a.setCustomData=function(a,g){var l=this.getUniqueId();(e[l]||(e[l]={}))[a]=g;return this};a.getCustomData=function(a){var g=this.$["data-cke-expando"];return(g=g&&e[g])&&a in g?g[a]:null};a.removeCustomData=function(a){var g=this.$["data-cke-expando"],g=g&&e[g],l,k;g&&(l=g[a],k=a in g,delete g[a]);return k?l:null};a.clearCustomData=function(){this.removeAllListeners();var a=
this.$["data-cke-expando"];a&&delete e[a]};a.getUniqueId=function(){return this.$["data-cke-expando"]||(this.$["data-cke-expando"]=CKEDITOR.tools.getNextNumber())};CKEDITOR.event.implementOn(a)}(CKEDITOR.dom.domObject.prototype),CKEDITOR.dom.node=function(a){return a?new CKEDITOR.dom[a.nodeType==CKEDITOR.NODE_DOCUMENT?"document":a.nodeType==CKEDITOR.NODE_ELEMENT?"element":a.nodeType==CKEDITOR.NODE_TEXT?"text":a.nodeType==CKEDITOR.NODE_COMMENT?"comment":a.nodeType==CKEDITOR.NODE_DOCUMENT_FRAGMENT?
"documentFragment":"domObject"](a):this},CKEDITOR.dom.node.prototype=new CKEDITOR.dom.domObject,CKEDITOR.NODE_ELEMENT=1,CKEDITOR.NODE_DOCUMENT=9,CKEDITOR.NODE_TEXT=3,CKEDITOR.NODE_COMMENT=8,CKEDITOR.NODE_DOCUMENT_FRAGMENT=11,CKEDITOR.POSITION_IDENTICAL=0,CKEDITOR.POSITION_DISCONNECTED=1,CKEDITOR.POSITION_FOLLOWING=2,CKEDITOR.POSITION_PRECEDING=4,CKEDITOR.POSITION_IS_CONTAINED=8,CKEDITOR.POSITION_CONTAINS=16,CKEDITOR.tools.extend(CKEDITOR.dom.node.prototype,{appendTo:function(a,e){a.append(this,e);
return a},clone:function(a,e){function d(g){g["data-cke-expando"]&&(g["data-cke-expando"]=!1);if(g.nodeType==CKEDITOR.NODE_ELEMENT||g.nodeType==CKEDITOR.NODE_DOCUMENT_FRAGMENT)if(e||g.nodeType!=CKEDITOR.NODE_ELEMENT||g.removeAttribute("id",!1),a){g=g.childNodes;for(var l=0;l<g.length;l++)d(g[l])}}function g(d){if(d.type==CKEDITOR.NODE_ELEMENT||d.type==CKEDITOR.NODE_DOCUMENT_FRAGMENT){if(d.type!=CKEDITOR.NODE_DOCUMENT_FRAGMENT){var e=d.getName();":"==e[0]&&d.renameNode(e.substring(1))}if(a)for(e=0;e<
d.getChildCount();e++)g(d.getChild(e))}}var l=this.$.cloneNode(a);d(l);l=new CKEDITOR.dom.node(l);CKEDITOR.env.ie&&9>CKEDITOR.env.version&&(this.type==CKEDITOR.NODE_ELEMENT||this.type==CKEDITOR.NODE_DOCUMENT_FRAGMENT)&&g(l);return l},hasPrevious:function(){return!!this.$.previousSibling},hasNext:function(){return!!this.$.nextSibling},insertAfter:function(a){a.$.parentNode.insertBefore(this.$,a.$.nextSibling);return a},insertBefore:function(a){a.$.parentNode.insertBefore(this.$,a.$);return a},insertBeforeMe:function(a){this.$.parentNode.insertBefore(a.$,
this.$);return a},getAddress:function(a){for(var e=[],d=this.getDocument().$.documentElement,g=this.$;g&&g!=d;){var l=g.parentNode;l&&e.unshift(this.getIndex.call({$:g},a));g=l}return e},getDocument:function(){return new CKEDITOR.dom.document(this.$.ownerDocument||this.$.parentNode.ownerDocument)},getIndex:function(a){function e(a,h){var b=h?a.nextSibling:a.previousSibling;return b&&b.nodeType==CKEDITOR.NODE_TEXT?d(b)?e(b,h):b:null}function d(a){return!a.nodeValue||a.nodeValue==CKEDITOR.dom.selection.FILLING_CHAR_SEQUENCE}
var g=this.$,l=-1,k;if(!this.$.parentNode||a&&g.nodeType==CKEDITOR.NODE_TEXT&&d(g)&&!e(g)&&!e(g,!0))return-1;do a&&g!=this.$&&g.nodeType==CKEDITOR.NODE_TEXT&&(k||d(g))||(l++,k=g.nodeType==CKEDITOR.NODE_TEXT);while(g=g.previousSibling);return l},getNextSourceNode:function(a,e,d){if(d&&!d.call){var g=d;d=function(a){return!a.equals(g)}}a=!a&&this.getFirst&&this.getFirst();var l;if(!a){if(this.type==CKEDITOR.NODE_ELEMENT&&d&&!1===d(this,!0))return null;a=this.getNext()}for(;!a&&(l=(l||this).getParent());){if(d&&
!1===d(l,!0))return null;a=l.getNext()}return!a||d&&!1===d(a)?null:e&&e!=a.type?a.getNextSourceNode(!1,e,d):a},getPreviousSourceNode:function(a,e,d){if(d&&!d.call){var g=d;d=function(a){return!a.equals(g)}}a=!a&&this.getLast&&this.getLast();var l;if(!a){if(this.type==CKEDITOR.NODE_ELEMENT&&d&&!1===d(this,!0))return null;a=this.getPrevious()}for(;!a&&(l=(l||this).getParent());){if(d&&!1===d(l,!0))return null;a=l.getPrevious()}return!a||d&&!1===d(a)?null:e&&a.type!=e?a.getPreviousSourceNode(!1,e,d):
a},getPrevious:function(a){var e=this.$,d;do d=(e=e.previousSibling)&&10!=e.nodeType&&new CKEDITOR.dom.node(e);while(d&&a&&!a(d));return d},getNext:function(a){var e=this.$,d;do d=(e=e.nextSibling)&&new CKEDITOR.dom.node(e);while(d&&a&&!a(d));return d},getParent:function(a){var e=this.$.parentNode;return e&&(e.nodeType==CKEDITOR.NODE_ELEMENT||a&&e.nodeType==CKEDITOR.NODE_DOCUMENT_FRAGMENT)?new CKEDITOR.dom.node(e):null},getParents:function(a){var e=this,d=[];do d[a?"push":"unshift"](e);while(e=e.getParent());
return d},getCommonAncestor:function(a){if(a.equals(this))return this;if(a.contains&&a.contains(this))return a;var e=this.contains?this:this.getParent();do if(e.contains(a))return e;while(e=e.getParent());return null},getPosition:function(a){var e=this.$,d=a.$;if(e.compareDocumentPosition)return e.compareDocumentPosition(d);if(e==d)return CKEDITOR.POSITION_IDENTICAL;if(this.type==CKEDITOR.NODE_ELEMENT&&a.type==CKEDITOR.NODE_ELEMENT){if(e.contains){if(e.contains(d))return CKEDITOR.POSITION_CONTAINS+
CKEDITOR.POSITION_PRECEDING;if(d.contains(e))return CKEDITOR.POSITION_IS_CONTAINED+CKEDITOR.POSITION_FOLLOWING}if("sourceIndex"in e)return 0>e.sourceIndex||0>d.sourceIndex?CKEDITOR.POSITION_DISCONNECTED:e.sourceIndex<d.sourceIndex?CKEDITOR.POSITION_PRECEDING:CKEDITOR.POSITION_FOLLOWING}e=this.getAddress();a=a.getAddress();for(var d=Math.min(e.length,a.length),g=0;g<d;g++)if(e[g]!=a[g])return e[g]<a[g]?CKEDITOR.POSITION_PRECEDING:CKEDITOR.POSITION_FOLLOWING;return e.length<a.length?CKEDITOR.POSITION_CONTAINS+
CKEDITOR.POSITION_PRECEDING:CKEDITOR.POSITION_IS_CONTAINED+CKEDITOR.POSITION_FOLLOWING},getAscendant:function(a,e){var d=this.$,g,l;e||(d=d.parentNode);"function"==typeof a?(l=!0,g=a):(l=!1,g=function(d){d="string"==typeof d.nodeName?d.nodeName.toLowerCase():"";return"string"==typeof a?d==a:d in a});for(;d;){if(g(l?new CKEDITOR.dom.node(d):d))return new CKEDITOR.dom.node(d);try{d=d.parentNode}catch(k){d=null}}return null},hasAscendant:function(a,e){var d=this.$;e||(d=d.parentNode);for(;d;){if(d.nodeName&&
d.nodeName.toLowerCase()==a)return!0;d=d.parentNode}return!1},move:function(a,e){a.append(this.remove(),e)},remove:function(a){var e=this.$,d=e.parentNode;if(d){if(a)for(;a=e.firstChild;)d.insertBefore(e.removeChild(a),e);d.removeChild(e)}return this},replace:function(a){this.insertBefore(a);a.remove()},trim:function(){this.ltrim();this.rtrim()},ltrim:function(){for(var a;this.getFirst&&(a=this.getFirst());){if(a.type==CKEDITOR.NODE_TEXT){var e=CKEDITOR.tools.ltrim(a.getText()),d=a.getLength();if(e)e.length<
d&&(a.split(d-e.length),this.$.removeChild(this.$.firstChild));else{a.remove();continue}}break}},rtrim:function(){for(var a;this.getLast&&(a=this.getLast());){if(a.type==CKEDITOR.NODE_TEXT){var e=CKEDITOR.tools.rtrim(a.getText()),d=a.getLength();if(e)e.length<d&&(a.split(e.length),this.$.lastChild.parentNode.removeChild(this.$.lastChild));else{a.remove();continue}}break}CKEDITOR.env.needsBrFiller&&(a=this.$.lastChild)&&1==a.type&&"br"==a.nodeName.toLowerCase()&&a.parentNode.removeChild(a)},isReadOnly:function(a){var e=
this;this.type!=CKEDITOR.NODE_ELEMENT&&(e=this.getParent());CKEDITOR.env.edge&&e&&e.is("textarea","input")&&(a=!0);if(!a&&e&&"undefined"!=typeof e.$.isContentEditable)return!(e.$.isContentEditable||e.data("cke-editable"));for(;e;){if(e.data("cke-editable"))return!1;if(e.hasAttribute("contenteditable"))return"false"==e.getAttribute("contenteditable");e=e.getParent()}return!0}}),CKEDITOR.dom.window=function(a){CKEDITOR.dom.domObject.call(this,a)},CKEDITOR.dom.window.prototype=new CKEDITOR.dom.domObject,
CKEDITOR.tools.extend(CKEDITOR.dom.window.prototype,{focus:function(){this.$.focus()},getViewPaneSize:function(){var a=this.$.document,e="CSS1Compat"==a.compatMode;return{width:(e?a.documentElement.clientWidth:a.body.clientWidth)||0,height:(e?a.documentElement.clientHeight:a.body.clientHeight)||0}},getScrollPosition:function(){var a=this.$;if("pageXOffset"in a)return{x:a.pageXOffset||0,y:a.pageYOffset||0};a=a.document;return{x:a.documentElement.scrollLeft||a.body.scrollLeft||0,y:a.documentElement.scrollTop||
a.body.scrollTop||0}},getFrame:function(){var a=this.$.frameElement;return a?new CKEDITOR.dom.element.get(a):null}}),CKEDITOR.dom.document=function(a){CKEDITOR.dom.domObject.call(this,a)},CKEDITOR.dom.document.prototype=new CKEDITOR.dom.domObject,CKEDITOR.tools.extend(CKEDITOR.dom.document.prototype,{type:CKEDITOR.NODE_DOCUMENT,appendStyleSheet:function(a){if(this.$.createStyleSheet)this.$.createStyleSheet(a);else{var e=new CKEDITOR.dom.element("link");e.setAttributes({rel:"stylesheet",type:"text/css",
href:a});this.getHead().append(e)}},appendStyleText:function(a){if(this.$.createStyleSheet){var e=this.$.createStyleSheet("");e.cssText=a}else{var d=new CKEDITOR.dom.element("style",this);d.append(new CKEDITOR.dom.text(a,this));this.getHead().append(d)}return e||d.$.sheet},createElement:function(a,e){var d=new CKEDITOR.dom.element(a,this);e&&(e.attributes&&d.setAttributes(e.attributes),e.styles&&d.setStyles(e.styles));return d},createText:function(a){return new CKEDITOR.dom.text(a,this)},focus:function(){this.getWindow().focus()},
getActive:function(){var a;try{a=this.$.activeElement}catch(e){return null}return new CKEDITOR.dom.element(a)},getById:function(a){return(a=this.$.getElementById(a))?new CKEDITOR.dom.element(a):null},getByAddress:function(a,e){for(var d=this.$.documentElement,g=0;d&&g<a.length;g++){var l=a[g];if(e)for(var k=-1,m=0;m<d.childNodes.length;m++){var h=d.childNodes[m];if(!0!==e||3!=h.nodeType||!h.previousSibling||3!=h.previousSibling.nodeType)if(k++,k==l){d=h;break}}else d=d.childNodes[l]}return d?new CKEDITOR.dom.node(d):
null},getElementsByTag:function(a,e){CKEDITOR.env.ie&&8>=document.documentMode||!e||(a=e+":"+a);return new CKEDITOR.dom.nodeList(this.$.getElementsByTagName(a))},getHead:function(){var a=this.$.getElementsByTagName("head")[0];return a=a?new CKEDITOR.dom.element(a):this.getDocumentElement().append(new CKEDITOR.dom.element("head"),!0)},getBody:function(){return new CKEDITOR.dom.element(this.$.body)},getDocumentElement:function(){return new CKEDITOR.dom.element(this.$.documentElement)},getWindow:function(){return new CKEDITOR.dom.window(this.$.parentWindow||
this.$.defaultView)},write:function(a){this.$.open("text/html","replace");CKEDITOR.env.ie&&(a=a.replace(/(?:^\s*<!DOCTYPE[^>]*?>)|^/i,'$\x26\n\x3cscript data-cke-temp\x3d"1"\x3e('+CKEDITOR.tools.fixDomain+")();\x3c/script\x3e"));this.$.write(a);this.$.close()},find:function(a){return new CKEDITOR.dom.nodeList(this.$.querySelectorAll(a))},findOne:function(a){return(a=this.$.querySelector(a))?new CKEDITOR.dom.element(a):null},_getHtml5ShivFrag:function(){var a=this.getCustomData("html5ShivFrag");a||
(a=this.$.createDocumentFragment(),CKEDITOR.tools.enableHtml5Elements(a,!0),this.setCustomData("html5ShivFrag",a));return a}}),CKEDITOR.dom.nodeList=function(a){this.$=a},CKEDITOR.dom.nodeList.prototype={count:function(){return this.$.length},getItem:function(a){return 0>a||a>=this.$.length?null:(a=this.$[a])?new CKEDITOR.dom.node(a):null}},CKEDITOR.dom.element=function(a,e){"string"==typeof a&&(a=(e?e.$:document).createElement(a));CKEDITOR.dom.domObject.call(this,a)},CKEDITOR.dom.element.get=function(a){return(a=
"string"==typeof a?document.getElementById(a)||document.getElementsByName(a)[0]:a)&&(a.$?a:new CKEDITOR.dom.element(a))},CKEDITOR.dom.element.prototype=new CKEDITOR.dom.node,CKEDITOR.dom.element.createFromHtml=function(a,e){var d=new CKEDITOR.dom.element("div",e);d.setHtml(a);return d.getFirst().remove()},CKEDITOR.dom.element.setMarker=function(a,e,d,g){var l=e.getCustomData("list_marker_id")||e.setCustomData("list_marker_id",CKEDITOR.tools.getNextNumber()).getCustomData("list_marker_id"),k=e.getCustomData("list_marker_names")||
e.setCustomData("list_marker_names",{}).getCustomData("list_marker_names");a[l]=e;k[d]=1;return e.setCustomData(d,g)},CKEDITOR.dom.element.clearAllMarkers=function(a){for(var e in a)CKEDITOR.dom.element.clearMarkers(a,a[e],1)},CKEDITOR.dom.element.clearMarkers=function(a,e,d){var g=e.getCustomData("list_marker_names"),l=e.getCustomData("list_marker_id"),k;for(k in g)e.removeCustomData(k);e.removeCustomData("list_marker_names");d&&(e.removeCustomData("list_marker_id"),delete a[l])},function(){function a(a,
b){return-1<(" "+a+" ").replace(k," ").indexOf(" "+b+" ")}function e(a){var b=!0;a.$.id||(a.$.id="cke_tmp_"+CKEDITOR.tools.getNextNumber(),b=!1);return function(){b||a.removeAttribute("id")}}function d(a,b){var c=CKEDITOR.tools.escapeCss(a.$.id);return"#"+c+" "+b.split(/,\s*/).join(", #"+c+" ")}function g(a){for(var b=0,c=0,f=m[a].length;c<f;c++)b+=parseInt(this.getComputedStyle(m[a][c])||0,10)||0;return b}var l=document.createElement("_").classList,l="undefined"!==typeof l&&null!==String(l.add).match(/\[Native code\]/gi),
k=/[\n\t\r]/g;CKEDITOR.tools.extend(CKEDITOR.dom.element.prototype,{type:CKEDITOR.NODE_ELEMENT,addClass:l?function(a){this.$.classList.add(a);return this}:function(d){var b=this.$.className;b&&(a(b,d)||(b+=" "+d));this.$.className=b||d;return this},removeClass:l?function(a){var b=this.$;b.classList.remove(a);b.className||b.removeAttribute("class");return this}:function(d){var b=this.getAttribute("class");b&&a(b,d)&&((b=b.replace(new RegExp("(?:^|\\s+)"+d+"(?\x3d\\s|$)"),"").replace(/^\s+/,""))?this.setAttribute("class",
b):this.removeAttribute("class"));return this},hasClass:function(d){return a(this.$.className,d)},append:function(a,b){"string"==typeof a&&(a=this.getDocument().createElement(a));b?this.$.insertBefore(a.$,this.$.firstChild):this.$.appendChild(a.$);return a},appendHtml:function(a){if(this.$.childNodes.length){var b=new CKEDITOR.dom.element("div",this.getDocument());b.setHtml(a);b.moveChildren(this)}else this.setHtml(a)},appendText:function(a){null!=this.$.text&&CKEDITOR.env.ie&&9>CKEDITOR.env.version?
this.$.text+=a:this.append(new CKEDITOR.dom.text(a))},appendBogus:function(a){if(a||CKEDITOR.env.needsBrFiller){for(a=this.getLast();a&&a.type==CKEDITOR.NODE_TEXT&&!CKEDITOR.tools.rtrim(a.getText());)a=a.getPrevious();a&&a.is&&a.is("br")||(a=this.getDocument().createElement("br"),CKEDITOR.env.gecko&&a.setAttribute("type","_moz"),this.append(a))}},breakParent:function(a,b){var c=new CKEDITOR.dom.range(this.getDocument());c.setStartAfter(this);c.setEndAfter(a);var f=c.extractContents(!1,b||!1),d;c.insertNode(this.remove());
if(CKEDITOR.env.ie&&!CKEDITOR.env.edge){for(c=new CKEDITOR.dom.element("div");d=f.getFirst();)d.$.style.backgroundColor&&(d.$.style.backgroundColor=d.$.style.backgroundColor),c.append(d);c.insertAfter(this);c.remove(!0)}else f.insertAfterNode(this)},contains:document.compareDocumentPosition?function(a){return!!(this.$.compareDocumentPosition(a.$)&16)}:function(a){var b=this.$;return a.type!=CKEDITOR.NODE_ELEMENT?b.contains(a.getParent().$):b!=a.$&&b.contains(a.$)},focus:function(){function a(){try{this.$.focus()}catch(b){}}
return function(b){b?CKEDITOR.tools.setTimeout(a,100,this):a.call(this)}}(),getHtml:function(){var a=this.$.innerHTML;return CKEDITOR.env.ie?a.replace(/<\?[^>]*>/g,""):a},getOuterHtml:function(){if(this.$.outerHTML)return this.$.outerHTML.replace(/<\?[^>]*>/,"");var a=this.$.ownerDocument.createElement("div");a.appendChild(this.$.cloneNode(!0));return a.innerHTML},getClientRect:function(){var a=CKEDITOR.tools.extend({},this.$.getBoundingClientRect());!a.width&&(a.width=a.right-a.left);!a.height&&
(a.height=a.bottom-a.top);return a},setHtml:CKEDITOR.env.ie&&9>CKEDITOR.env.version?function(a){try{var b=this.$;if(this.getParent())return b.innerHTML=a;var c=this.getDocument()._getHtml5ShivFrag();c.appendChild(b);b.innerHTML=a;c.removeChild(b);return a}catch(f){this.$.innerHTML="";b=new CKEDITOR.dom.element("body",this.getDocument());b.$.innerHTML=a;for(b=b.getChildren();b.count();)this.append(b.getItem(0));return a}}:function(a){return this.$.innerHTML=a},setText:function(){var a=document.createElement("p");
a.innerHTML="x";a=a.textContent;return function(b){this.$[a?"textContent":"innerText"]=b}}(),getAttribute:function(){var a=function(a){return this.$.getAttribute(a,2)};return CKEDITOR.env.ie&&(CKEDITOR.env.ie7Compat||CKEDITOR.env.quirks)?function(a){switch(a){case "class":a="className";break;case "http-equiv":a="httpEquiv";break;case "name":return this.$.name;case "tabindex":return a=this.$.getAttribute(a,2),0!==a&&0===this.$.tabIndex&&(a=null),a;case "checked":return a=this.$.attributes.getNamedItem(a),
(a.specified?a.nodeValue:this.$.checked)?"checked":null;case "hspace":case "value":return this.$[a];case "style":return this.$.style.cssText;case "contenteditable":case "contentEditable":return this.$.attributes.getNamedItem("contentEditable").specified?this.$.getAttribute("contentEditable"):null}return this.$.getAttribute(a,2)}:a}(),getAttributes:function(a){var b={},c=this.$.attributes,f;a=CKEDITOR.tools.isArray(a)?a:[];for(f=0;f<c.length;f++)-1===CKEDITOR.tools.indexOf(a,c[f].name)&&(b[c[f].name]=
c[f].value);return b},getChildren:function(){return new CKEDITOR.dom.nodeList(this.$.childNodes)},getComputedStyle:document.defaultView&&document.defaultView.getComputedStyle?function(a){var b=this.getWindow().$.getComputedStyle(this.$,null);return b?b.getPropertyValue(a):""}:function(a){return this.$.currentStyle[CKEDITOR.tools.cssStyleToDomStyle(a)]},getDtd:function(){var a=CKEDITOR.dtd[this.getName()];this.getDtd=function(){return a};return a},getElementsByTag:CKEDITOR.dom.document.prototype.getElementsByTag,
getTabIndex:function(){var a=this.$.tabIndex;return 0!==a||CKEDITOR.dtd.$tabIndex[this.getName()]||0===parseInt(this.getAttribute("tabindex"),10)?a:-1},getText:function(){return this.$.textContent||this.$.innerText||""},getWindow:function(){return this.getDocument().getWindow()},getId:function(){return this.$.id||null},getNameAtt:function(){return this.$.name||null},getName:function(){var a=this.$.nodeName.toLowerCase();if(CKEDITOR.env.ie&&8>=document.documentMode){var b=this.$.scopeName;"HTML"!=
b&&(a=b.toLowerCase()+":"+a)}this.getName=function(){return a};return this.getName()},getValue:function(){return this.$.value},getFirst:function(a){var b=this.$.firstChild;(b=b&&new CKEDITOR.dom.node(b))&&a&&!a(b)&&(b=b.getNext(a));return b},getLast:function(a){var b=this.$.lastChild;(b=b&&new CKEDITOR.dom.node(b))&&a&&!a(b)&&(b=b.getPrevious(a));return b},getStyle:function(a){return this.$.style[CKEDITOR.tools.cssStyleToDomStyle(a)]},is:function(){var a=this.getName();if("object"==typeof arguments[0])return!!arguments[0][a];
for(var b=0;b<arguments.length;b++)if(arguments[b]==a)return!0;return!1},isEditable:function(a){var b=this.getName();return this.isReadOnly()||"none"==this.getComputedStyle("display")||"hidden"==this.getComputedStyle("visibility")||CKEDITOR.dtd.$nonEditable[b]||CKEDITOR.dtd.$empty[b]||this.is("a")&&(this.data("cke-saved-name")||this.hasAttribute("name"))&&!this.getChildCount()?!1:!1!==a?(a=CKEDITOR.dtd[b]||CKEDITOR.dtd.span,!(!a||!a["#"])):!0},isIdentical:function(a){var b=this.clone(0,1);a=a.clone(0,
1);b.removeAttributes(["_moz_dirty","data-cke-expando","data-cke-saved-href","data-cke-saved-name"]);a.removeAttributes(["_moz_dirty","data-cke-expando","data-cke-saved-href","data-cke-saved-name"]);if(b.$.isEqualNode)return b.$.style.cssText=CKEDITOR.tools.normalizeCssText(b.$.style.cssText),a.$.style.cssText=CKEDITOR.tools.normalizeCssText(a.$.style.cssText),b.$.isEqualNode(a.$);b=b.getOuterHtml();a=a.getOuterHtml();if(CKEDITOR.env.ie&&9>CKEDITOR.env.version&&this.is("a")){var c=this.getParent();
c.type==CKEDITOR.NODE_ELEMENT&&(c=c.clone(),c.setHtml(b),b=c.getHtml(),c.setHtml(a),a=c.getHtml())}return b==a},isVisible:function(){var a=(this.$.offsetHeight||this.$.offsetWidth)&&"hidden"!=this.getComputedStyle("visibility"),b,c;a&&CKEDITOR.env.webkit&&(b=this.getWindow(),!b.equals(CKEDITOR.document.getWindow())&&(c=b.$.frameElement)&&(a=(new CKEDITOR.dom.element(c)).isVisible()));return!!a},isEmptyInlineRemoveable:function(){if(!CKEDITOR.dtd.$removeEmpty[this.getName()])return!1;for(var a=this.getChildren(),
b=0,c=a.count();b<c;b++){var f=a.getItem(b);if(f.type!=CKEDITOR.NODE_ELEMENT||!f.data("cke-bookmark"))if(f.type==CKEDITOR.NODE_ELEMENT&&!f.isEmptyInlineRemoveable()||f.type==CKEDITOR.NODE_TEXT&&CKEDITOR.tools.trim(f.getText()))return!1}return!0},hasAttributes:CKEDITOR.env.ie&&(CKEDITOR.env.ie7Compat||CKEDITOR.env.quirks)?function(){for(var a=this.$.attributes,b=0;b<a.length;b++){var c=a[b];switch(c.nodeName){case "class":if(this.getAttribute("class"))return!0;case "data-cke-expando":continue;default:if(c.specified)return!0}}return!1}:
function(){var a=this.$.attributes,b=a.length,c={"data-cke-expando":1,_moz_dirty:1};return 0<b&&(2<b||!c[a[0].nodeName]||2==b&&!c[a[1].nodeName])},hasAttribute:function(){function a(b){var c=this.$.attributes.getNamedItem(b);if("input"==this.getName())switch(b){case "class":return 0<this.$.className.length;case "checked":return!!this.$.checked;case "value":return b=this.getAttribute("type"),"checkbox"==b||"radio"==b?"on"!=this.$.value:!!this.$.value}return c?c.specified:!1}return CKEDITOR.env.ie?
8>CKEDITOR.env.version?function(b){return"name"==b?!!this.$.name:a.call(this,b)}:a:function(a){return!!this.$.attributes.getNamedItem(a)}}(),hide:function(){this.setStyle("display","none")},moveChildren:function(a,b){var c=this.$;a=a.$;if(c!=a){var f;if(b)for(;f=c.lastChild;)a.insertBefore(c.removeChild(f),a.firstChild);else for(;f=c.firstChild;)a.appendChild(c.removeChild(f))}},mergeSiblings:function(){function a(b,c,f){if(c&&c.type==CKEDITOR.NODE_ELEMENT){for(var d=[];c.data("cke-bookmark")||c.isEmptyInlineRemoveable();)if(d.push(c),
c=f?c.getNext():c.getPrevious(),!c||c.type!=CKEDITOR.NODE_ELEMENT)return;if(b.isIdentical(c)){for(var g=f?b.getLast():b.getFirst();d.length;)d.shift().move(b,!f);c.moveChildren(b,!f);c.remove();g&&g.type==CKEDITOR.NODE_ELEMENT&&g.mergeSiblings()}}}return function(b){if(!1===b||CKEDITOR.dtd.$removeEmpty[this.getName()]||this.is("a"))a(this,this.getNext(),!0),a(this,this.getPrevious())}}(),show:function(){this.setStyles({display:"",visibility:""})},setAttribute:function(){var a=function(a,c){this.$.setAttribute(a,
c);return this};return CKEDITOR.env.ie&&(CKEDITOR.env.ie7Compat||CKEDITOR.env.quirks)?function(b,c){"class"==b?this.$.className=c:"style"==b?this.$.style.cssText=c:"tabindex"==b?this.$.tabIndex=c:"checked"==b?this.$.checked=c:"contenteditable"==b?a.call(this,"contentEditable",c):a.apply(this,arguments);return this}:CKEDITOR.env.ie8Compat&&CKEDITOR.env.secure?function(b,c){if("src"==b&&c.match(/^http:\/\//))try{a.apply(this,arguments)}catch(f){}else a.apply(this,arguments);return this}:a}(),setAttributes:function(a){for(var b in a)this.setAttribute(b,
a[b]);return this},setValue:function(a){this.$.value=a;return this},removeAttribute:function(){var a=function(a){this.$.removeAttribute(a)};return CKEDITOR.env.ie&&(CKEDITOR.env.ie7Compat||CKEDITOR.env.quirks)?function(a){"class"==a?a="className":"tabindex"==a?a="tabIndex":"contenteditable"==a&&(a="contentEditable");this.$.removeAttribute(a)}:a}(),removeAttributes:function(a){if(CKEDITOR.tools.isArray(a))for(var b=0;b<a.length;b++)this.removeAttribute(a[b]);else for(b in a=a||this.getAttributes(),
a)a.hasOwnProperty(b)&&this.removeAttribute(b)},removeStyle:function(a){var b=this.$.style;if(b.removeProperty||"border"!=a&&"margin"!=a&&"padding"!=a)b.removeProperty?b.removeProperty(a):b.removeAttribute(CKEDITOR.tools.cssStyleToDomStyle(a)),this.$.style.cssText||this.removeAttribute("style");else{var c=["top","left","right","bottom"],f;"border"==a&&(f=["color","style","width"]);for(var b=[],d=0;d<c.length;d++)if(f)for(var g=0;g<f.length;g++)b.push([a,c[d],f[g]].join("-"));else b.push([a,c[d]].join("-"));
for(a=0;a<b.length;a++)this.removeStyle(b[a])}},setStyle:function(a,b){this.$.style[CKEDITOR.tools.cssStyleToDomStyle(a)]=b;return this},setStyles:function(a){for(var b in a)this.setStyle(b,a[b]);return this},setOpacity:function(a){CKEDITOR.env.ie&&9>CKEDITOR.env.version?(a=Math.round(100*a),this.setStyle("filter",100<=a?"":"progid:DXImageTransform.Microsoft.Alpha(opacity\x3d"+a+")")):this.setStyle("opacity",a)},unselectable:function(){this.setStyles(CKEDITOR.tools.cssVendorPrefix("user-select","none"));
if(CKEDITOR.env.ie){this.setAttribute("unselectable","on");for(var a,b=this.getElementsByTag("*"),c=0,f=b.count();c<f;c++)a=b.getItem(c),a.setAttribute("unselectable","on")}},getPositionedAncestor:function(){for(var a=this;"html"!=a.getName();){if("static"!=a.getComputedStyle("position"))return a;a=a.getParent()}return null},getDocumentPosition:function(a){var b=0,c=0,f=this.getDocument(),d=f.getBody(),g="BackCompat"==f.$.compatMode;if(document.documentElement.getBoundingClientRect&&(CKEDITOR.env.ie?
8!==CKEDITOR.env.version:1)){var e=this.$.getBoundingClientRect(),k=f.$.documentElement,u=k.clientTop||d.$.clientTop||0,l=k.clientLeft||d.$.clientLeft||0,m=!0;CKEDITOR.env.ie&&(m=f.getDocumentElement().contains(this),f=f.getBody().contains(this),m=g&&f||!g&&m);m&&(CKEDITOR.env.webkit||CKEDITOR.env.ie&&12<=CKEDITOR.env.version?(b=d.$.scrollLeft||k.scrollLeft,c=d.$.scrollTop||k.scrollTop):(c=g?d.$:k,b=c.scrollLeft,c=c.scrollTop),b=e.left+b-l,c=e.top+c-u)}else for(u=this,l=null;u&&"body"!=u.getName()&&
"html"!=u.getName();){b+=u.$.offsetLeft-u.$.scrollLeft;c+=u.$.offsetTop-u.$.scrollTop;u.equals(this)||(b+=u.$.clientLeft||0,c+=u.$.clientTop||0);for(;l&&!l.equals(u);)b-=l.$.scrollLeft,c-=l.$.scrollTop,l=l.getParent();l=u;u=(e=u.$.offsetParent)?new CKEDITOR.dom.element(e):null}a&&(e=this.getWindow(),u=a.getWindow(),!e.equals(u)&&e.$.frameElement&&(a=(new CKEDITOR.dom.element(e.$.frameElement)).getDocumentPosition(a),b+=a.x,c+=a.y));document.documentElement.getBoundingClientRect||!CKEDITOR.env.gecko||
g||(b+=this.$.clientLeft?1:0,c+=this.$.clientTop?1:0);return{x:b,y:c}},scrollIntoView:function(a){var b=this.getParent();if(b){do if((b.$.clientWidth&&b.$.clientWidth<b.$.scrollWidth||b.$.clientHeight&&b.$.clientHeight<b.$.scrollHeight)&&!b.is("body")&&this.scrollIntoParent(b,a,1),b.is("html")){var c=b.getWindow();try{var f=c.$.frameElement;f&&(b=new CKEDITOR.dom.element(f))}catch(d){}}while(b=b.getParent())}},scrollIntoParent:function(a,b,c){var f,d,g,e;function k(f,b){/body|html/.test(a.getName())?
a.getWindow().$.scrollBy(f,b):(a.$.scrollLeft+=f,a.$.scrollTop+=b)}function u(a,f){var b={x:0,y:0};if(!a.is(m?"body":"html")){var c=a.$.getBoundingClientRect();b.x=c.left;b.y=c.top}c=a.getWindow();c.equals(f)||(c=u(CKEDITOR.dom.element.get(c.$.frameElement),f),b.x+=c.x,b.y+=c.y);return b}function l(a,f){return parseInt(a.getComputedStyle("margin-"+f)||0,10)||0}!a&&(a=this.getWindow());g=a.getDocument();var m="BackCompat"==g.$.compatMode;a instanceof CKEDITOR.dom.window&&(a=m?g.getBody():g.getDocumentElement());
CKEDITOR.env.webkit&&(g=this.getEditor(!1))&&(g._.previousScrollTop=null);g=a.getWindow();d=u(this,g);var w=u(a,g),F=this.$.offsetHeight;f=this.$.offsetWidth;var n=a.$.clientHeight,r=a.$.clientWidth;g=d.x-l(this,"left")-w.x||0;e=d.y-l(this,"top")-w.y||0;f=d.x+f+l(this,"right")-(w.x+r)||0;d=d.y+F+l(this,"bottom")-(w.y+n)||0;(0>e||0<d)&&k(0,!0===b?e:!1===b?d:0>e?e:d);c&&(0>g||0<f)&&k(0>g?g:f,0)},setState:function(a,b,c){b=b||"cke";switch(a){case CKEDITOR.TRISTATE_ON:this.addClass(b+"_on");this.removeClass(b+
"_off");this.removeClass(b+"_disabled");c&&this.setAttribute("aria-pressed",!0);c&&this.removeAttribute("aria-disabled");break;case CKEDITOR.TRISTATE_DISABLED:this.addClass(b+"_disabled");this.removeClass(b+"_off");this.removeClass(b+"_on");c&&this.setAttribute("aria-disabled",!0);c&&this.removeAttribute("aria-pressed");break;default:this.addClass(b+"_off"),this.removeClass(b+"_on"),this.removeClass(b+"_disabled"),c&&this.removeAttribute("aria-pressed"),c&&this.removeAttribute("aria-disabled")}},
getFrameDocument:function(){var a=this.$;try{a.contentWindow.document}catch(b){a.src=a.src}return a&&new CKEDITOR.dom.document(a.contentWindow.document)},copyAttributes:function(a,b){var c=this.$.attributes;b=b||{};for(var f=0;f<c.length;f++){var d=c[f],g=d.nodeName.toLowerCase(),e;if(!(g in b))if("checked"==g&&(e=this.getAttribute(g)))a.setAttribute(g,e);else if(!CKEDITOR.env.ie||this.hasAttribute(g))e=this.getAttribute(g),null===e&&(e=d.nodeValue),a.setAttribute(g,e)}""!==this.$.style.cssText&&
(a.$.style.cssText=this.$.style.cssText)},renameNode:function(a){if(this.getName()!=a){var b=this.getDocument();a=new CKEDITOR.dom.element(a,b);this.copyAttributes(a);this.moveChildren(a);this.getParent(!0)&&this.$.parentNode.replaceChild(a.$,this.$);a.$["data-cke-expando"]=this.$["data-cke-expando"];this.$=a.$;delete this.getName}},getChild:function(){function a(b,c){var f=b.childNodes;if(0<=c&&c<f.length)return f[c]}return function(b){var c=this.$;if(b.slice)for(b=b.slice();0<b.length&&c;)c=a(c,
b.shift());else c=a(c,b);return c?new CKEDITOR.dom.node(c):null}}(),getChildCount:function(){return this.$.childNodes.length},disableContextMenu:function(){function a(b){return b.type==CKEDITOR.NODE_ELEMENT&&b.hasClass("cke_enable_context_menu")}this.on("contextmenu",function(b){b.data.getTarget().getAscendant(a,!0)||b.data.preventDefault()})},getDirection:function(a){return a?this.getComputedStyle("direction")||this.getDirection()||this.getParent()&&this.getParent().getDirection(1)||this.getDocument().$.dir||
"ltr":this.getStyle("direction")||this.getAttribute("dir")},data:function(a,b){a="data-"+a;if(void 0===b)return this.getAttribute(a);!1===b?this.removeAttribute(a):this.setAttribute(a,b);return null},getEditor:function(a){var b=CKEDITOR.instances,c,f,d;a=a||void 0===a;for(c in b)if(f=b[c],f.element.equals(this)&&f.elementMode!=CKEDITOR.ELEMENT_MODE_APPENDTO||!a&&(d=f.editable())&&(d.equals(this)||d.contains(this)))return f;return null},find:function(a){var b=e(this);a=new CKEDITOR.dom.nodeList(this.$.querySelectorAll(d(this,
a)));b();return a},findOne:function(a){var b=e(this);a=this.$.querySelector(d(this,a));b();return a?new CKEDITOR.dom.element(a):null},forEach:function(a,b,c){if(!(c||b&&this.type!=b))var f=a(this);if(!1!==f){c=this.getChildren();for(var d=0;d<c.count();d++)f=c.getItem(d),f.type==CKEDITOR.NODE_ELEMENT?f.forEach(a,b):b&&f.type!=b||a(f)}}});var m={width:["border-left-width","border-right-width","padding-left","padding-right"],height:["border-top-width","border-bottom-width","padding-top","padding-bottom"]};
CKEDITOR.dom.element.prototype.setSize=function(a,b,c){"number"==typeof b&&(!c||CKEDITOR.env.ie&&CKEDITOR.env.quirks||(b-=g.call(this,a)),this.setStyle(a,b+"px"))};CKEDITOR.dom.element.prototype.getSize=function(a,b){var c=Math.max(this.$["offset"+CKEDITOR.tools.capitalize(a)],this.$["client"+CKEDITOR.tools.capitalize(a)])||0;b&&(c-=g.call(this,a));return c}}(),CKEDITOR.dom.documentFragment=function(a){a=a||CKEDITOR.document;this.$=a.type==CKEDITOR.NODE_DOCUMENT?a.$.createDocumentFragment():a},CKEDITOR.tools.extend(CKEDITOR.dom.documentFragment.prototype,
CKEDITOR.dom.element.prototype,{type:CKEDITOR.NODE_DOCUMENT_FRAGMENT,insertAfterNode:function(a){a=a.$;a.parentNode.insertBefore(this.$,a.nextSibling)},getHtml:function(){var a=new CKEDITOR.dom.element("div");this.clone(1,1).appendTo(a);return a.getHtml().replace(/\s*data-cke-expando=".*?"/g,"")}},!0,{append:1,appendBogus:1,clone:1,getFirst:1,getHtml:1,getLast:1,getParent:1,getNext:1,getPrevious:1,appendTo:1,moveChildren:1,insertBefore:1,insertAfterNode:1,replace:1,trim:1,type:1,ltrim:1,rtrim:1,getDocument:1,
getChildCount:1,getChild:1,getChildren:1}),function(){function a(a,f){var b=this.range;if(this._.end)return null;if(!this._.start){this._.start=1;if(b.collapsed)return this.end(),null;b.optimize()}var c,d=b.startContainer;c=b.endContainer;var g=b.startOffset,p=b.endOffset,e,n=this.guard,r=this.type,C=a?"getPreviousSourceNode":"getNextSourceNode";if(!a&&!this._.guardLTR){var D=c.type==CKEDITOR.NODE_ELEMENT?c:c.getParent(),k=c.type==CKEDITOR.NODE_ELEMENT?c.getChild(p):c.getNext();this._.guardLTR=function(a,
f){return(!f||!D.equals(a))&&(!k||!a.equals(k))&&(a.type!=CKEDITOR.NODE_ELEMENT||!f||!a.equals(b.root))}}if(a&&!this._.guardRTL){var h=d.type==CKEDITOR.NODE_ELEMENT?d:d.getParent(),l=d.type==CKEDITOR.NODE_ELEMENT?g?d.getChild(g-1):null:d.getPrevious();this._.guardRTL=function(a,f){return(!f||!h.equals(a))&&(!l||!a.equals(l))&&(a.type!=CKEDITOR.NODE_ELEMENT||!f||!a.equals(b.root))}}var m=a?this._.guardRTL:this._.guardLTR;e=n?function(a,f){return!1===m(a,f)?!1:n(a,f)}:m;this.current?c=this.current[C](!1,
r,e):(a?c.type==CKEDITOR.NODE_ELEMENT&&(c=0<p?c.getChild(p-1):!1===e(c,!0)?null:c.getPreviousSourceNode(!0,r,e)):(c=d,c.type==CKEDITOR.NODE_ELEMENT&&((c=c.getChild(g))||(c=!1===e(d,!0)?null:d.getNextSourceNode(!0,r,e)))),c&&!1===e(c)&&(c=null));for(;c&&!this._.end;){this.current=c;if(!this.evaluator||!1!==this.evaluator(c)){if(!f)return c}else if(f&&this.evaluator)return!1;c=c[C](!1,r,e)}this.end();return this.current=null}function e(f){for(var c,b=null;c=a.call(this,f);)b=c;return b}CKEDITOR.dom.walker=
CKEDITOR.tools.createClass({$:function(a){this.range=a;this._={}},proto:{end:function(){this._.end=1},next:function(){return a.call(this)},previous:function(){return a.call(this,1)},checkForward:function(){return!1!==a.call(this,0,1)},checkBackward:function(){return!1!==a.call(this,1,1)},lastForward:function(){return e.call(this)},lastBackward:function(){return e.call(this,1)},reset:function(){delete this.current;this._={}}}});var d={block:1,"list-item":1,table:1,"table-row-group":1,"table-header-group":1,
"table-footer-group":1,"table-row":1,"table-column-group":1,"table-column":1,"table-cell":1,"table-caption":1},g={absolute:1,fixed:1};CKEDITOR.dom.element.prototype.isBlockBoundary=function(a){return"none"!=this.getComputedStyle("float")||this.getComputedStyle("position")in g||!d[this.getComputedStyle("display")]?!!(this.is(CKEDITOR.dtd.$block)||a&&this.is(a)):!0};CKEDITOR.dom.walker.blockBoundary=function(a){return function(f){return!(f.type==CKEDITOR.NODE_ELEMENT&&f.isBlockBoundary(a))}};CKEDITOR.dom.walker.listItemBoundary=
function(){return this.blockBoundary({br:1})};CKEDITOR.dom.walker.bookmark=function(a,f){function c(a){return a&&a.getName&&"span"==a.getName()&&a.data("cke-bookmark")}return function(b){var d,g;d=b&&b.type!=CKEDITOR.NODE_ELEMENT&&(g=b.getParent())&&c(g);d=a?d:d||c(b);return!!(f^d)}};CKEDITOR.dom.walker.whitespaces=function(a){return function(f){var c;f&&f.type==CKEDITOR.NODE_TEXT&&(c=!CKEDITOR.tools.trim(f.getText())||CKEDITOR.env.webkit&&f.getText()==CKEDITOR.dom.selection.FILLING_CHAR_SEQUENCE);
return!!(a^c)}};CKEDITOR.dom.walker.invisible=function(a){var f=CKEDITOR.dom.walker.whitespaces(),c=CKEDITOR.env.webkit?1:0;return function(b){f(b)?b=1:(b.type==CKEDITOR.NODE_TEXT&&(b=b.getParent()),b=b.$.offsetWidth<=c);return!!(a^b)}};CKEDITOR.dom.walker.nodeType=function(a,f){return function(c){return!!(f^c.type==a)}};CKEDITOR.dom.walker.bogus=function(a){function f(a){return!k(a)&&!m(a)}return function(c){var b=CKEDITOR.env.needsBrFiller?c.is&&c.is("br"):c.getText&&l.test(c.getText());b&&(b=c.getParent(),
c=c.getNext(f),b=b.isBlockBoundary()&&(!c||c.type==CKEDITOR.NODE_ELEMENT&&c.isBlockBoundary()));return!!(a^b)}};CKEDITOR.dom.walker.temp=function(a){return function(f){f.type!=CKEDITOR.NODE_ELEMENT&&(f=f.getParent());f=f&&f.hasAttribute("data-cke-temp");return!!(a^f)}};var l=/^[\t\r\n ]*(?:&nbsp;|\xa0)$/,k=CKEDITOR.dom.walker.whitespaces(),m=CKEDITOR.dom.walker.bookmark(),h=CKEDITOR.dom.walker.temp(),b=function(a){return m(a)||k(a)||a.type==CKEDITOR.NODE_ELEMENT&&a.is(CKEDITOR.dtd.$inline)&&!a.is(CKEDITOR.dtd.$empty)};
CKEDITOR.dom.walker.ignored=function(a){return function(f){f=k(f)||m(f)||h(f);return!!(a^f)}};var c=CKEDITOR.dom.walker.ignored();CKEDITOR.dom.walker.empty=function(a){return function(f){for(var b=0,d=f.getChildCount();b<d;++b)if(!c(f.getChild(b)))return!!a;return!a}};var f=CKEDITOR.dom.walker.empty(),p=CKEDITOR.dom.walker.validEmptyBlockContainers=CKEDITOR.tools.extend(function(a){var f={},c;for(c in a)CKEDITOR.dtd[c]["#"]&&(f[c]=1);return f}(CKEDITOR.dtd.$block),{caption:1,td:1,th:1});CKEDITOR.dom.walker.editable=
function(a){return function(b){b=c(b)?!1:b.type==CKEDITOR.NODE_TEXT||b.type==CKEDITOR.NODE_ELEMENT&&(b.is(CKEDITOR.dtd.$inline)||b.is("hr")||"false"==b.getAttribute("contenteditable")||!CKEDITOR.env.needsBrFiller&&b.is(p)&&f(b))?!0:!1;return!!(a^b)}};CKEDITOR.dom.element.prototype.getBogus=function(){var a=this;do a=a.getPreviousSourceNode();while(b(a));return a&&(CKEDITOR.env.needsBrFiller?a.is&&a.is("br"):a.getText&&l.test(a.getText()))?a:!1}}(),CKEDITOR.dom.range=function(a){this.endOffset=this.endContainer=
this.startOffset=this.startContainer=null;this.collapsed=!0;var e=a instanceof CKEDITOR.dom.document;this.document=e?a:a.getDocument();this.root=e?a.getBody():a},function(){function a(a){a.collapsed=a.startContainer&&a.endContainer&&a.startContainer.equals(a.endContainer)&&a.startOffset==a.endOffset}function e(a,b,c,d,g){function e(a,f,c,b){var d=c?a.getPrevious():a.getNext();if(b&&l)return d;n||b?f.append(a.clone(!0,g),c):(a.remove(),m&&f.append(a));return d}function k(){var a,f,c,b=Math.min(v.length,
q.length);for(a=0;a<b;a++)if(f=v[a],c=q[a],!f.equals(c))return a;return a-1}function h(){var c=N-1,b=P&&L&&!r.equals(C);c<G-1||c<X-1||b?(b?a.moveToPosition(C,CKEDITOR.POSITION_BEFORE_START):X==c+1&&J?a.moveToPosition(q[c],CKEDITOR.POSITION_BEFORE_END):a.moveToPosition(q[c+1],CKEDITOR.POSITION_BEFORE_START),d&&(c=v[c+1])&&c.type==CKEDITOR.NODE_ELEMENT&&(b=CKEDITOR.dom.element.createFromHtml('\x3cspan data-cke-bookmark\x3d"1" style\x3d"display:none"\x3e\x26nbsp;\x3c/span\x3e',a.document),b.insertAfter(c),
c.mergeSiblings(!1),a.moveToBookmark({startNode:b}))):a.collapse(!0)}a.optimizeBookmark();var l=0===b,m=1==b,n=2==b;b=n||m;var r=a.startContainer,C=a.endContainer,D=a.startOffset,z=a.endOffset,K,J,P,L,O,S;if(n&&C.type==CKEDITOR.NODE_TEXT&&r.equals(C))r=a.document.createText(r.substring(D,z)),c.append(r);else{C.type==CKEDITOR.NODE_TEXT?n?S=!0:C=C.split(z):0<C.getChildCount()?z>=C.getChildCount()?(C=C.getChild(z-1),J=!0):C=C.getChild(z):L=J=!0;r.type==CKEDITOR.NODE_TEXT?n?O=!0:r.split(D):0<r.getChildCount()?
0===D?(r=r.getChild(D),K=!0):r=r.getChild(D-1):P=K=!0;for(var v=r.getParents(),q=C.getParents(),N=k(),G=v.length-1,X=q.length-1,R=c,Q,Z,Y,ca=-1,V=N;V<=G;V++){Z=v[V];Y=Z.getNext();for(V!=G||Z.equals(q[V])&&G<X?b&&(Q=R.append(Z.clone(0,g))):K?e(Z,R,!1,P):O&&R.append(a.document.createText(Z.substring(D)));Y;){if(Y.equals(q[V])){ca=V;break}Y=e(Y,R)}R=Q}R=c;for(V=N;V<=X;V++)if(c=q[V],Y=c.getPrevious(),c.equals(v[V]))b&&(R=R.getChild(0));else{V!=X||c.equals(v[V])&&X<G?b&&(Q=R.append(c.clone(0,g))):J?e(c,
R,!1,L):S&&R.append(a.document.createText(c.substring(0,z)));if(V>ca)for(;Y;)Y=e(Y,R,!0);R=Q}n||h()}}function d(){var a=!1,c=CKEDITOR.dom.walker.whitespaces(),b=CKEDITOR.dom.walker.bookmark(!0),d=CKEDITOR.dom.walker.bogus();return function(g){return b(g)||c(g)?!0:d(g)&&!a?a=!0:g.type==CKEDITOR.NODE_TEXT&&(g.hasAscendant("pre")||CKEDITOR.tools.trim(g.getText()).length)||g.type==CKEDITOR.NODE_ELEMENT&&!g.is(k)?!1:!0}}function g(a){var c=CKEDITOR.dom.walker.whitespaces(),b=CKEDITOR.dom.walker.bookmark(1);
return function(d){return b(d)||c(d)?!0:!a&&m(d)||d.type==CKEDITOR.NODE_ELEMENT&&d.is(CKEDITOR.dtd.$removeEmpty)}}function l(a){return function(){var d;return this[a?"getPreviousNode":"getNextNode"](function(a){!d&&c(a)&&(d=a);return b(a)&&!(m(a)&&a.equals(d))})}}var k={abbr:1,acronym:1,b:1,bdo:1,big:1,cite:1,code:1,del:1,dfn:1,em:1,font:1,i:1,ins:1,label:1,kbd:1,q:1,samp:1,small:1,span:1,strike:1,strong:1,sub:1,sup:1,tt:1,u:1,"var":1},m=CKEDITOR.dom.walker.bogus(),h=/^[\t\r\n ]*(?:&nbsp;|\xa0)$/,
b=CKEDITOR.dom.walker.editable(),c=CKEDITOR.dom.walker.ignored(!0);CKEDITOR.dom.range.prototype={clone:function(){var a=new CKEDITOR.dom.range(this.root);a._setStartContainer(this.startContainer);a.startOffset=this.startOffset;a._setEndContainer(this.endContainer);a.endOffset=this.endOffset;a.collapsed=this.collapsed;return a},collapse:function(a){a?(this._setEndContainer(this.startContainer),this.endOffset=this.startOffset):(this._setStartContainer(this.endContainer),this.startOffset=this.endOffset);
this.collapsed=!0},cloneContents:function(a){var c=new CKEDITOR.dom.documentFragment(this.document);this.collapsed||e(this,2,c,!1,"undefined"==typeof a?!0:a);return c},deleteContents:function(a){this.collapsed||e(this,0,null,a)},extractContents:function(a,c){var b=new CKEDITOR.dom.documentFragment(this.document);this.collapsed||e(this,1,b,a,"undefined"==typeof c?!0:c);return b},createBookmark:function(a){var c,b,d,g,e=this.collapsed;c=this.document.createElement("span");c.data("cke-bookmark",1);c.setStyle("display",
"none");c.setHtml("\x26nbsp;");a&&(d="cke_bm_"+CKEDITOR.tools.getNextNumber(),c.setAttribute("id",d+(e?"C":"S")));e||(b=c.clone(),b.setHtml("\x26nbsp;"),a&&b.setAttribute("id",d+"E"),g=this.clone(),g.collapse(),g.insertNode(b));g=this.clone();g.collapse(!0);g.insertNode(c);b?(this.setStartAfter(c),this.setEndBefore(b)):this.moveToPosition(c,CKEDITOR.POSITION_AFTER_END);return{startNode:a?d+(e?"C":"S"):c,endNode:a?d+"E":b,serializable:a,collapsed:e}},createBookmark2:function(){function a(f){var c=
f.container,d=f.offset,g;g=c;var e=d;g=g.type!=CKEDITOR.NODE_ELEMENT||0===e||e==g.getChildCount()?0:g.getChild(e-1).type==CKEDITOR.NODE_TEXT&&g.getChild(e).type==CKEDITOR.NODE_TEXT;g&&(c=c.getChild(d-1),d=c.getLength());if(c.type==CKEDITOR.NODE_ELEMENT&&0<d){a:{for(g=c;d--;)if(e=g.getChild(d).getIndex(!0),0<=e){d=e;break a}d=-1}d+=1}if(c.type==CKEDITOR.NODE_TEXT){g=c;for(e=0;(g=g.getPrevious())&&g.type==CKEDITOR.NODE_TEXT;)e+=g.getText().replace(CKEDITOR.dom.selection.FILLING_CHAR_SEQUENCE,"").length;
g=e;c.getText()?d+=g:(e=c.getPrevious(b),g?(d=g,c=e?e.getNext():c.getParent().getFirst()):(c=c.getParent(),d=e?e.getIndex(!0)+1:0))}f.container=c;f.offset=d}function c(a,f){var b=f.getCustomData("cke-fillingChar");if(b){var d=a.container;b.equals(d)&&(a.offset-=CKEDITOR.dom.selection.FILLING_CHAR_SEQUENCE.length,0>=a.offset&&(a.offset=d.getIndex(),a.container=d.getParent()))}}var b=CKEDITOR.dom.walker.nodeType(CKEDITOR.NODE_TEXT,!0);return function(b){var d=this.collapsed,g={container:this.startContainer,
offset:this.startOffset},e={container:this.endContainer,offset:this.endOffset};b&&(a(g),c(g,this.root),d||(a(e),c(e,this.root)));return{start:g.container.getAddress(b),end:d?null:e.container.getAddress(b),startOffset:g.offset,endOffset:e.offset,normalized:b,collapsed:d,is2:!0}}}(),moveToBookmark:function(a){if(a.is2){var c=this.document.getByAddress(a.start,a.normalized),b=a.startOffset,d=a.end&&this.document.getByAddress(a.end,a.normalized);a=a.endOffset;this.setStart(c,b);d?this.setEnd(d,a):this.collapse(!0)}else c=
(b=a.serializable)?this.document.getById(a.startNode):a.startNode,a=b?this.document.getById(a.endNode):a.endNode,this.setStartBefore(c),c.remove(),a?(this.setEndBefore(a),a.remove()):this.collapse(!0)},getBoundaryNodes:function(){var a=this.startContainer,c=this.endContainer,b=this.startOffset,d=this.endOffset,g;if(a.type==CKEDITOR.NODE_ELEMENT)if(g=a.getChildCount(),g>b)a=a.getChild(b);else if(1>g)a=a.getPreviousSourceNode();else{for(a=a.$;a.lastChild;)a=a.lastChild;a=new CKEDITOR.dom.node(a);a=
a.getNextSourceNode()||a}if(c.type==CKEDITOR.NODE_ELEMENT)if(g=c.getChildCount(),g>d)c=c.getChild(d).getPreviousSourceNode(!0);else if(1>g)c=c.getPreviousSourceNode();else{for(c=c.$;c.lastChild;)c=c.lastChild;c=new CKEDITOR.dom.node(c)}a.getPosition(c)&CKEDITOR.POSITION_FOLLOWING&&(a=c);return{startNode:a,endNode:c}},getCommonAncestor:function(a,c){var b=this.startContainer,d=this.endContainer,b=b.equals(d)?a&&b.type==CKEDITOR.NODE_ELEMENT&&this.startOffset==this.endOffset-1?b.getChild(this.startOffset):
b:b.getCommonAncestor(d);return c&&!b.is?b.getParent():b},optimize:function(){var a=this.startContainer,c=this.startOffset;a.type!=CKEDITOR.NODE_ELEMENT&&(c?c>=a.getLength()&&this.setStartAfter(a):this.setStartBefore(a));a=this.endContainer;c=this.endOffset;a.type!=CKEDITOR.NODE_ELEMENT&&(c?c>=a.getLength()&&this.setEndAfter(a):this.setEndBefore(a))},optimizeBookmark:function(){var a=this.startContainer,c=this.endContainer;a.is&&a.is("span")&&a.data("cke-bookmark")&&this.setStartAt(a,CKEDITOR.POSITION_BEFORE_START);
c&&c.is&&c.is("span")&&c.data("cke-bookmark")&&this.setEndAt(c,CKEDITOR.POSITION_AFTER_END)},trim:function(a,c){var b=this.startContainer,d=this.startOffset,g=this.collapsed;if((!a||g)&&b&&b.type==CKEDITOR.NODE_TEXT){if(d)if(d>=b.getLength())d=b.getIndex()+1,b=b.getParent();else{var e=b.split(d),d=b.getIndex()+1,b=b.getParent();this.startContainer.equals(this.endContainer)?this.setEnd(e,this.endOffset-this.startOffset):b.equals(this.endContainer)&&(this.endOffset+=1)}else d=b.getIndex(),b=b.getParent();
this.setStart(b,d);if(g){this.collapse(!0);return}}b=this.endContainer;d=this.endOffset;c||g||!b||b.type!=CKEDITOR.NODE_TEXT||(d?(d>=b.getLength()||b.split(d),d=b.getIndex()+1):d=b.getIndex(),b=b.getParent(),this.setEnd(b,d))},enlarge:function(a,c){function b(a){return a&&a.type==CKEDITOR.NODE_ELEMENT&&a.hasAttribute("contenteditable")?null:a}var d=new RegExp(/[^\s\ufeff]/);switch(a){case CKEDITOR.ENLARGE_INLINE:var g=1;case CKEDITOR.ENLARGE_ELEMENT:var e=function(a,f){var c=new CKEDITOR.dom.range(h);
c.setStart(a,f);c.setEndAt(h,CKEDITOR.POSITION_BEFORE_END);var c=new CKEDITOR.dom.walker(c),b;for(c.guard=function(a){return!(a.type==CKEDITOR.NODE_ELEMENT&&a.isBlockBoundary())};b=c.next();){if(b.type!=CKEDITOR.NODE_TEXT)return!1;K=b!=a?b.getText():b.substring(f);if(d.test(K))return!1}return!0};if(this.collapsed)break;var k=this.getCommonAncestor(),h=this.root,l,m,n,r,C,D=!1,z,K;z=this.startContainer;var J=this.startOffset;z.type==CKEDITOR.NODE_TEXT?(J&&(z=!CKEDITOR.tools.trim(z.substring(0,J)).length&&
z,D=!!z),z&&((r=z.getPrevious())||(n=z.getParent()))):(J&&(r=z.getChild(J-1)||z.getLast()),r||(n=z));for(n=b(n);n||r;){if(n&&!r){!C&&n.equals(k)&&(C=!0);if(g?n.isBlockBoundary():!h.contains(n))break;D&&"inline"==n.getComputedStyle("display")||(D=!1,C?l=n:this.setStartBefore(n));r=n.getPrevious()}for(;r;)if(z=!1,r.type==CKEDITOR.NODE_COMMENT)r=r.getPrevious();else{if(r.type==CKEDITOR.NODE_TEXT)K=r.getText(),d.test(K)&&(r=null),z=/[\s\ufeff]$/.test(K);else if((r.$.offsetWidth>(CKEDITOR.env.webkit?1:
0)||c&&r.is("br"))&&!r.data("cke-bookmark"))if(D&&CKEDITOR.dtd.$removeEmpty[r.getName()]){K=r.getText();if(d.test(K))r=null;else for(var J=r.$.getElementsByTagName("*"),P=0,L;L=J[P++];)if(!CKEDITOR.dtd.$removeEmpty[L.nodeName.toLowerCase()]){r=null;break}r&&(z=!!K.length)}else r=null;z&&(D?C?l=n:n&&this.setStartBefore(n):D=!0);if(r){z=r.getPrevious();if(!n&&!z){n=r;r=null;break}r=z}else n=null}n&&(n=b(n.getParent()))}z=this.endContainer;J=this.endOffset;n=r=null;C=D=!1;z.type==CKEDITOR.NODE_TEXT?
CKEDITOR.tools.trim(z.substring(J)).length?D=!0:(D=!z.getLength(),J==z.getLength()?(r=z.getNext())||(n=z.getParent()):e(z,J)&&(n=z.getParent())):(r=z.getChild(J))||(n=z);for(;n||r;){if(n&&!r){!C&&n.equals(k)&&(C=!0);if(g?n.isBlockBoundary():!h.contains(n))break;D&&"inline"==n.getComputedStyle("display")||(D=!1,C?m=n:n&&this.setEndAfter(n));r=n.getNext()}for(;r;){z=!1;if(r.type==CKEDITOR.NODE_TEXT)K=r.getText(),e(r,0)||(r=null),z=/^[\s\ufeff]/.test(K);else if(r.type==CKEDITOR.NODE_ELEMENT){if((0<r.$.offsetWidth||
c&&r.is("br"))&&!r.data("cke-bookmark"))if(D&&CKEDITOR.dtd.$removeEmpty[r.getName()]){K=r.getText();if(d.test(K))r=null;else for(J=r.$.getElementsByTagName("*"),P=0;L=J[P++];)if(!CKEDITOR.dtd.$removeEmpty[L.nodeName.toLowerCase()]){r=null;break}r&&(z=!!K.length)}else r=null}else z=1;z&&D&&(C?m=n:this.setEndAfter(n));if(r){z=r.getNext();if(!n&&!z){n=r;r=null;break}r=z}else n=null}n&&(n=b(n.getParent()))}l&&m&&(k=l.contains(m)?m:l,this.setStartBefore(k),this.setEndAfter(k));break;case CKEDITOR.ENLARGE_BLOCK_CONTENTS:case CKEDITOR.ENLARGE_LIST_ITEM_CONTENTS:n=
new CKEDITOR.dom.range(this.root);h=this.root;n.setStartAt(h,CKEDITOR.POSITION_AFTER_START);n.setEnd(this.startContainer,this.startOffset);n=new CKEDITOR.dom.walker(n);var O,S,v=CKEDITOR.dom.walker.blockBoundary(a==CKEDITOR.ENLARGE_LIST_ITEM_CONTENTS?{br:1}:null),q=null,N=function(a){if(a.type==CKEDITOR.NODE_ELEMENT&&"false"==a.getAttribute("contenteditable"))if(q){if(q.equals(a)){q=null;return}}else q=a;else if(q)return;var f=v(a);f||(O=a);return f},g=function(a){var f=N(a);!f&&a.is&&a.is("br")&&
(S=a);return f};n.guard=N;n=n.lastBackward();O=O||h;this.setStartAt(O,!O.is("br")&&(!n&&this.checkStartOfBlock()||n&&O.contains(n))?CKEDITOR.POSITION_AFTER_START:CKEDITOR.POSITION_AFTER_END);if(a==CKEDITOR.ENLARGE_LIST_ITEM_CONTENTS){n=this.clone();n=new CKEDITOR.dom.walker(n);var G=CKEDITOR.dom.walker.whitespaces(),X=CKEDITOR.dom.walker.bookmark();n.evaluator=function(a){return!G(a)&&!X(a)};if((n=n.previous())&&n.type==CKEDITOR.NODE_ELEMENT&&n.is("br"))break}n=this.clone();n.collapse();n.setEndAt(h,
CKEDITOR.POSITION_BEFORE_END);n=new CKEDITOR.dom.walker(n);n.guard=a==CKEDITOR.ENLARGE_LIST_ITEM_CONTENTS?g:N;O=q=S=null;n=n.lastForward();O=O||h;this.setEndAt(O,!n&&this.checkEndOfBlock()||n&&O.contains(n)?CKEDITOR.POSITION_BEFORE_END:CKEDITOR.POSITION_BEFORE_START);S&&this.setEndAfter(S)}},shrink:function(a,c,b){if(!this.collapsed){a=a||CKEDITOR.SHRINK_TEXT;var d=this.clone(),g=this.startContainer,e=this.endContainer,k=this.startOffset,h=this.endOffset,l=1,m=1;g&&g.type==CKEDITOR.NODE_TEXT&&(k?
k>=g.getLength()?d.setStartAfter(g):(d.setStartBefore(g),l=0):d.setStartBefore(g));e&&e.type==CKEDITOR.NODE_TEXT&&(h?h>=e.getLength()?d.setEndAfter(e):(d.setEndAfter(e),m=0):d.setEndBefore(e));var d=new CKEDITOR.dom.walker(d),n=CKEDITOR.dom.walker.bookmark();d.evaluator=function(c){return c.type==(a==CKEDITOR.SHRINK_ELEMENT?CKEDITOR.NODE_ELEMENT:CKEDITOR.NODE_TEXT)};var r;d.guard=function(c,d){if(n(c))return!0;if(a==CKEDITOR.SHRINK_ELEMENT&&c.type==CKEDITOR.NODE_TEXT||d&&c.equals(r)||!1===b&&c.type==
CKEDITOR.NODE_ELEMENT&&c.isBlockBoundary()||c.type==CKEDITOR.NODE_ELEMENT&&c.hasAttribute("contenteditable"))return!1;d||c.type!=CKEDITOR.NODE_ELEMENT||(r=c);return!0};l&&(g=d[a==CKEDITOR.SHRINK_ELEMENT?"lastForward":"next"]())&&this.setStartAt(g,c?CKEDITOR.POSITION_AFTER_START:CKEDITOR.POSITION_BEFORE_START);m&&(d.reset(),(d=d[a==CKEDITOR.SHRINK_ELEMENT?"lastBackward":"previous"]())&&this.setEndAt(d,c?CKEDITOR.POSITION_BEFORE_END:CKEDITOR.POSITION_AFTER_END));return!(!l&&!m)}},insertNode:function(a){this.optimizeBookmark();
this.trim(!1,!0);var c=this.startContainer,b=c.getChild(this.startOffset);b?a.insertBefore(b):c.append(a);a.getParent()&&a.getParent().equals(this.endContainer)&&this.endOffset++;this.setStartBefore(a)},moveToPosition:function(a,c){this.setStartAt(a,c);this.collapse(!0)},moveToRange:function(a){this.setStart(a.startContainer,a.startOffset);this.setEnd(a.endContainer,a.endOffset)},selectNodeContents:function(a){this.setStart(a,0);this.setEnd(a,a.type==CKEDITOR.NODE_TEXT?a.getLength():a.getChildCount())},
setStart:function(f,c){f.type==CKEDITOR.NODE_ELEMENT&&CKEDITOR.dtd.$empty[f.getName()]&&(c=f.getIndex(),f=f.getParent());this._setStartContainer(f);this.startOffset=c;this.endContainer||(this._setEndContainer(f),this.endOffset=c);a(this)},setEnd:function(f,c){f.type==CKEDITOR.NODE_ELEMENT&&CKEDITOR.dtd.$empty[f.getName()]&&(c=f.getIndex()+1,f=f.getParent());this._setEndContainer(f);this.endOffset=c;this.startContainer||(this._setStartContainer(f),this.startOffset=c);a(this)},setStartAfter:function(a){this.setStart(a.getParent(),
a.getIndex()+1)},setStartBefore:function(a){this.setStart(a.getParent(),a.getIndex())},setEndAfter:function(a){this.setEnd(a.getParent(),a.getIndex()+1)},setEndBefore:function(a){this.setEnd(a.getParent(),a.getIndex())},setStartAt:function(f,c){switch(c){case CKEDITOR.POSITION_AFTER_START:this.setStart(f,0);break;case CKEDITOR.POSITION_BEFORE_END:f.type==CKEDITOR.NODE_TEXT?this.setStart(f,f.getLength()):this.setStart(f,f.getChildCount());break;case CKEDITOR.POSITION_BEFORE_START:this.setStartBefore(f);
break;case CKEDITOR.POSITION_AFTER_END:this.setStartAfter(f)}a(this)},setEndAt:function(f,c){switch(c){case CKEDITOR.POSITION_AFTER_START:this.setEnd(f,0);break;case CKEDITOR.POSITION_BEFORE_END:f.type==CKEDITOR.NODE_TEXT?this.setEnd(f,f.getLength()):this.setEnd(f,f.getChildCount());break;case CKEDITOR.POSITION_BEFORE_START:this.setEndBefore(f);break;case CKEDITOR.POSITION_AFTER_END:this.setEndAfter(f)}a(this)},fixBlock:function(a,c){var b=this.createBookmark(),d=this.document.createElement(c);this.collapse(a);
this.enlarge(CKEDITOR.ENLARGE_BLOCK_CONTENTS);this.extractContents().appendTo(d);d.trim();this.insertNode(d);var g=d.getBogus();g&&g.remove();d.appendBogus();this.moveToBookmark(b);return d},splitBlock:function(a,c){var b=new CKEDITOR.dom.elementPath(this.startContainer,this.root),d=new CKEDITOR.dom.elementPath(this.endContainer,this.root),g=b.block,e=d.block,k=null;if(!b.blockLimit.equals(d.blockLimit))return null;"br"!=a&&(g||(g=this.fixBlock(!0,a),e=(new CKEDITOR.dom.elementPath(this.endContainer,
this.root)).block),e||(e=this.fixBlock(!1,a)));b=g&&this.checkStartOfBlock();d=e&&this.checkEndOfBlock();this.deleteContents();g&&g.equals(e)&&(d?(k=new CKEDITOR.dom.elementPath(this.startContainer,this.root),this.moveToPosition(e,CKEDITOR.POSITION_AFTER_END),e=null):b?(k=new CKEDITOR.dom.elementPath(this.startContainer,this.root),this.moveToPosition(g,CKEDITOR.POSITION_BEFORE_START),g=null):(e=this.splitElement(g,c||!1),g.is("ul","ol")||g.appendBogus()));return{previousBlock:g,nextBlock:e,wasStartOfBlock:b,
wasEndOfBlock:d,elementPath:k}},splitElement:function(a,c){if(!this.collapsed)return null;this.setEndAt(a,CKEDITOR.POSITION_BEFORE_END);var b=this.extractContents(!1,c||!1),d=a.clone(!1,c||!1);b.appendTo(d);d.insertAfter(a);this.moveToPosition(a,CKEDITOR.POSITION_AFTER_END);return d},removeEmptyBlocksAtEnd:function(){function a(f){return function(a){return c(a)||b(a)||a.type==CKEDITOR.NODE_ELEMENT&&a.isEmptyInlineRemoveable()||f.is("table")&&a.is("caption")?!1:!0}}var c=CKEDITOR.dom.walker.whitespaces(),
b=CKEDITOR.dom.walker.bookmark(!1);return function(c){for(var b=this.createBookmark(),d=this[c?"endPath":"startPath"](),g=d.block||d.blockLimit,e;g&&!g.equals(d.root)&&!g.getFirst(a(g));)e=g.getParent(),this[c?"setEndAt":"setStartAt"](g,CKEDITOR.POSITION_AFTER_END),g.remove(1),g=e;this.moveToBookmark(b)}}(),startPath:function(){return new CKEDITOR.dom.elementPath(this.startContainer,this.root)},endPath:function(){return new CKEDITOR.dom.elementPath(this.endContainer,this.root)},checkBoundaryOfElement:function(a,
c){var b=c==CKEDITOR.START,d=this.clone();d.collapse(b);d[b?"setStartAt":"setEndAt"](a,b?CKEDITOR.POSITION_AFTER_START:CKEDITOR.POSITION_BEFORE_END);d=new CKEDITOR.dom.walker(d);d.evaluator=g(b);return d[b?"checkBackward":"checkForward"]()},checkStartOfBlock:function(){var a=this.startContainer,c=this.startOffset;CKEDITOR.env.ie&&c&&a.type==CKEDITOR.NODE_TEXT&&(a=CKEDITOR.tools.ltrim(a.substring(0,c)),h.test(a)&&this.trim(0,1));this.trim();a=new CKEDITOR.dom.elementPath(this.startContainer,this.root);
c=this.clone();c.collapse(!0);c.setStartAt(a.block||a.blockLimit,CKEDITOR.POSITION_AFTER_START);a=new CKEDITOR.dom.walker(c);a.evaluator=d();return a.checkBackward()},checkEndOfBlock:function(){var a=this.endContainer,c=this.endOffset;CKEDITOR.env.ie&&a.type==CKEDITOR.NODE_TEXT&&(a=CKEDITOR.tools.rtrim(a.substring(c)),h.test(a)&&this.trim(1,0));this.trim();a=new CKEDITOR.dom.elementPath(this.endContainer,this.root);c=this.clone();c.collapse(!1);c.setEndAt(a.block||a.blockLimit,CKEDITOR.POSITION_BEFORE_END);
a=new CKEDITOR.dom.walker(c);a.evaluator=d();return a.checkForward()},getPreviousNode:function(a,c,b){var d=this.clone();d.collapse(1);d.setStartAt(b||this.root,CKEDITOR.POSITION_AFTER_START);b=new CKEDITOR.dom.walker(d);b.evaluator=a;b.guard=c;return b.previous()},getNextNode:function(a,c,b){var d=this.clone();d.collapse();d.setEndAt(b||this.root,CKEDITOR.POSITION_BEFORE_END);b=new CKEDITOR.dom.walker(d);b.evaluator=a;b.guard=c;return b.next()},checkReadOnly:function(){function a(c,f){for(;c;){if(c.type==
CKEDITOR.NODE_ELEMENT){if("false"==c.getAttribute("contentEditable")&&!c.data("cke-editable"))return 0;if(c.is("html")||"true"==c.getAttribute("contentEditable")&&(c.contains(f)||c.equals(f)))break}c=c.getParent()}return 1}return function(){var c=this.startContainer,b=this.endContainer;return!(a(c,b)&&a(b,c))}}(),moveToElementEditablePosition:function(a,b){if(a.type==CKEDITOR.NODE_ELEMENT&&!a.isEditable(!1))return this.moveToPosition(a,b?CKEDITOR.POSITION_AFTER_END:CKEDITOR.POSITION_BEFORE_START),
!0;for(var d=0;a;){if(a.type==CKEDITOR.NODE_TEXT){b&&this.endContainer&&this.checkEndOfBlock()&&h.test(a.getText())?this.moveToPosition(a,CKEDITOR.POSITION_BEFORE_START):this.moveToPosition(a,b?CKEDITOR.POSITION_AFTER_END:CKEDITOR.POSITION_BEFORE_START);d=1;break}if(a.type==CKEDITOR.NODE_ELEMENT)if(a.isEditable())this.moveToPosition(a,b?CKEDITOR.POSITION_BEFORE_END:CKEDITOR.POSITION_AFTER_START),d=1;else if(b&&a.is("br")&&this.endContainer&&this.checkEndOfBlock())this.moveToPosition(a,CKEDITOR.POSITION_BEFORE_START);
else if("false"==a.getAttribute("contenteditable")&&a.is(CKEDITOR.dtd.$block))return this.setStartBefore(a),this.setEndAfter(a),!0;var g=a,e=d,u=void 0;g.type==CKEDITOR.NODE_ELEMENT&&g.isEditable(!1)&&(u=g[b?"getLast":"getFirst"](c));e||u||(u=g[b?"getPrevious":"getNext"](c));a=u}return!!d},moveToClosestEditablePosition:function(a,c){var b,d=0,g,e,k=[CKEDITOR.POSITION_AFTER_END,CKEDITOR.POSITION_BEFORE_START];a?(b=new CKEDITOR.dom.range(this.root),b.moveToPosition(a,k[c?0:1])):b=this.clone();if(a&&
!a.is(CKEDITOR.dtd.$block))d=1;else if(g=b[c?"getNextEditableNode":"getPreviousEditableNode"]())d=1,(e=g.type==CKEDITOR.NODE_ELEMENT)&&g.is(CKEDITOR.dtd.$block)&&"false"==g.getAttribute("contenteditable")?(b.setStartAt(g,CKEDITOR.POSITION_BEFORE_START),b.setEndAt(g,CKEDITOR.POSITION_AFTER_END)):!CKEDITOR.env.needsBrFiller&&e&&g.is(CKEDITOR.dom.walker.validEmptyBlockContainers)?(b.setEnd(g,0),b.collapse()):b.moveToPosition(g,k[c?1:0]);d&&this.moveToRange(b);return!!d},moveToElementEditStart:function(a){return this.moveToElementEditablePosition(a)},
moveToElementEditEnd:function(a){return this.moveToElementEditablePosition(a,!0)},getEnclosedNode:function(){var a=this.clone();a.optimize();if(a.startContainer.type!=CKEDITOR.NODE_ELEMENT||a.endContainer.type!=CKEDITOR.NODE_ELEMENT)return null;var a=new CKEDITOR.dom.walker(a),c=CKEDITOR.dom.walker.bookmark(!1,!0),b=CKEDITOR.dom.walker.whitespaces(!0);a.evaluator=function(a){return b(a)&&c(a)};var d=a.next();a.reset();return d&&d.equals(a.previous())?d:null},getTouchedStartNode:function(){var a=this.startContainer;
return this.collapsed||a.type!=CKEDITOR.NODE_ELEMENT?a:a.getChild(this.startOffset)||a},getTouchedEndNode:function(){var a=this.endContainer;return this.collapsed||a.type!=CKEDITOR.NODE_ELEMENT?a:a.getChild(this.endOffset-1)||a},getNextEditableNode:l(),getPreviousEditableNode:l(1),scrollIntoView:function(){var a=new CKEDITOR.dom.element.createFromHtml("\x3cspan\x3e\x26nbsp;\x3c/span\x3e",this.document),c,b,d,g=this.clone();g.optimize();(d=g.startContainer.type==CKEDITOR.NODE_TEXT)?(b=g.startContainer.getText(),
c=g.startContainer.split(g.startOffset),a.insertAfter(g.startContainer)):g.insertNode(a);a.scrollIntoView();d&&(g.startContainer.setText(b),c.remove());a.remove()},_setStartContainer:function(a){this.startContainer=a},_setEndContainer:function(a){this.endContainer=a},_find:function(a,c){var b=this.getCommonAncestor(),d=this.getBoundaryNodes(),g=[],e,k,h,l;if(b&&b.find)for(k=b.find(a),e=0;e<k.count();e++)if(b=k.getItem(e),c||!b.isReadOnly())h=b.getPosition(d.startNode)&CKEDITOR.POSITION_FOLLOWING||
d.startNode.equals(b),l=b.getPosition(d.endNode)&CKEDITOR.POSITION_PRECEDING+CKEDITOR.POSITION_IS_CONTAINED,h&&l&&g.push(b);return g}}}(),CKEDITOR.POSITION_AFTER_START=1,CKEDITOR.POSITION_BEFORE_END=2,CKEDITOR.POSITION_BEFORE_START=3,CKEDITOR.POSITION_AFTER_END=4,CKEDITOR.ENLARGE_ELEMENT=1,CKEDITOR.ENLARGE_BLOCK_CONTENTS=2,CKEDITOR.ENLARGE_LIST_ITEM_CONTENTS=3,CKEDITOR.ENLARGE_INLINE=4,CKEDITOR.START=1,CKEDITOR.END=2,CKEDITOR.SHRINK_ELEMENT=1,CKEDITOR.SHRINK_TEXT=2,"use strict",function(){function a(a){1>
arguments.length||(this.range=a,this.forceBrBreak=0,this.enlargeBr=1,this.enforceRealBlocks=0,this._||(this._={}))}function e(a){var b=[];a.forEach(function(a){if("true"==a.getAttribute("contenteditable"))return b.push(a),!1},CKEDITOR.NODE_ELEMENT,!0);return b}function d(a,b,g,k){a:{null==k&&(k=e(g));for(var h;h=k.shift();)if(h.getDtd().p){k={element:h,remaining:k};break a}k=null}if(!k)return 0;if((h=CKEDITOR.filter.instances[k.element.data("cke-filter")])&&!h.check(b))return d(a,b,g,k.remaining);
b=new CKEDITOR.dom.range(k.element);b.selectNodeContents(k.element);b=b.createIterator();b.enlargeBr=a.enlargeBr;b.enforceRealBlocks=a.enforceRealBlocks;b.activeFilter=b.filter=h;a._.nestedEditable={element:k.element,container:g,remaining:k.remaining,iterator:b};return 1}function g(a,b,d){if(!b)return!1;a=a.clone();a.collapse(!d);return a.checkBoundaryOfElement(b,d?CKEDITOR.START:CKEDITOR.END)}var l=/^[\r\n\t ]+$/,k=CKEDITOR.dom.walker.bookmark(!1,!0),m=CKEDITOR.dom.walker.whitespaces(!0),h=function(a){return k(a)&&
m(a)},b={dd:1,dt:1,li:1};a.prototype={getNextParagraph:function(a){var f,e,m,x,t;a=a||"p";if(this._.nestedEditable){if(f=this._.nestedEditable.iterator.getNextParagraph(a))return this.activeFilter=this._.nestedEditable.iterator.activeFilter,f;this.activeFilter=this.filter;if(d(this,a,this._.nestedEditable.container,this._.nestedEditable.remaining))return this.activeFilter=this._.nestedEditable.iterator.activeFilter,this._.nestedEditable.iterator.getNextParagraph(a);this._.nestedEditable=null}if(!this.range.root.getDtd()[a])return null;
if(!this._.started){var u=this.range.clone();e=u.startPath();var y=u.endPath(),H=!u.collapsed&&g(u,e.block),w=!u.collapsed&&g(u,y.block,1);u.shrink(CKEDITOR.SHRINK_ELEMENT,!0);H&&u.setStartAt(e.block,CKEDITOR.POSITION_BEFORE_END);w&&u.setEndAt(y.block,CKEDITOR.POSITION_AFTER_START);e=u.endContainer.hasAscendant("pre",!0)||u.startContainer.hasAscendant("pre",!0);u.enlarge(this.forceBrBreak&&!e||!this.enlargeBr?CKEDITOR.ENLARGE_LIST_ITEM_CONTENTS:CKEDITOR.ENLARGE_BLOCK_CONTENTS);u.collapsed||(e=new CKEDITOR.dom.walker(u.clone()),
y=CKEDITOR.dom.walker.bookmark(!0,!0),e.evaluator=y,this._.nextNode=e.next(),e=new CKEDITOR.dom.walker(u.clone()),e.evaluator=y,e=e.previous(),this._.lastNode=e.getNextSourceNode(!0,null,u.root),this._.lastNode&&this._.lastNode.type==CKEDITOR.NODE_TEXT&&!CKEDITOR.tools.trim(this._.lastNode.getText())&&this._.lastNode.getParent().isBlockBoundary()&&(y=this.range.clone(),y.moveToPosition(this._.lastNode,CKEDITOR.POSITION_AFTER_END),y.checkEndOfBlock()&&(y=new CKEDITOR.dom.elementPath(y.endContainer,
y.root),this._.lastNode=(y.block||y.blockLimit).getNextSourceNode(!0))),this._.lastNode&&u.root.contains(this._.lastNode)||(this._.lastNode=this._.docEndMarker=u.document.createText(""),this._.lastNode.insertAfter(e)),u=null);this._.started=1;e=u}y=this._.nextNode;u=this._.lastNode;for(this._.nextNode=null;y;){var H=0,w=y.hasAscendant("pre"),F=y.type!=CKEDITOR.NODE_ELEMENT,n=0;if(F)y.type==CKEDITOR.NODE_TEXT&&l.test(y.getText())&&(F=0);else{var r=y.getName();if(CKEDITOR.dtd.$block[r]&&"false"==y.getAttribute("contenteditable")){f=
y;d(this,a,f);break}else if(y.isBlockBoundary(this.forceBrBreak&&!w&&{br:1})){if("br"==r)F=1;else if(!e&&!y.getChildCount()&&"hr"!=r){f=y;m=y.equals(u);break}e&&(e.setEndAt(y,CKEDITOR.POSITION_BEFORE_START),"br"!=r&&(this._.nextNode=y));H=1}else{if(y.getFirst()){e||(e=this.range.clone(),e.setStartAt(y,CKEDITOR.POSITION_BEFORE_START));y=y.getFirst();continue}F=1}}F&&!e&&(e=this.range.clone(),e.setStartAt(y,CKEDITOR.POSITION_BEFORE_START));m=(!H||F)&&y.equals(u);if(e&&!H)for(;!y.getNext(h)&&!m;){r=
y.getParent();if(r.isBlockBoundary(this.forceBrBreak&&!w&&{br:1})){H=1;F=0;m||r.equals(u);e.setEndAt(r,CKEDITOR.POSITION_BEFORE_END);break}y=r;F=1;m=y.equals(u);n=1}F&&e.setEndAt(y,CKEDITOR.POSITION_AFTER_END);y=this._getNextSourceNode(y,n,u);if((m=!y)||H&&e)break}if(!f){if(!e)return this._.docEndMarker&&this._.docEndMarker.remove(),this._.nextNode=null;f=new CKEDITOR.dom.elementPath(e.startContainer,e.root);y=f.blockLimit;H={div:1,th:1,td:1};f=f.block;!f&&y&&!this.enforceRealBlocks&&H[y.getName()]&&
e.checkStartOfBlock()&&e.checkEndOfBlock()&&!y.equals(e.root)?f=y:!f||this.enforceRealBlocks&&f.is(b)?(f=this.range.document.createElement(a),e.extractContents().appendTo(f),f.trim(),e.insertNode(f),x=t=!0):"li"!=f.getName()?e.checkStartOfBlock()&&e.checkEndOfBlock()||(f=f.clone(!1),e.extractContents().appendTo(f),f.trim(),t=e.splitBlock(),x=!t.wasStartOfBlock,t=!t.wasEndOfBlock,e.insertNode(f)):m||(this._.nextNode=f.equals(u)?null:this._getNextSourceNode(e.getBoundaryNodes().endNode,1,u))}x&&(x=
f.getPrevious())&&x.type==CKEDITOR.NODE_ELEMENT&&("br"==x.getName()?x.remove():x.getLast()&&"br"==x.getLast().$.nodeName.toLowerCase()&&x.getLast().remove());t&&(x=f.getLast())&&x.type==CKEDITOR.NODE_ELEMENT&&"br"==x.getName()&&(!CKEDITOR.env.needsBrFiller||x.getPrevious(k)||x.getNext(k))&&x.remove();this._.nextNode||(this._.nextNode=m||f.equals(u)||!u?null:this._getNextSourceNode(f,1,u));return f},_getNextSourceNode:function(a,b,d){function g(a){return!(a.equals(d)||a.equals(e))}var e=this.range.root;
for(a=a.getNextSourceNode(b,null,g);!k(a);)a=a.getNextSourceNode(b,null,g);return a}};CKEDITOR.dom.range.prototype.createIterator=function(){return new a(this)}}(),CKEDITOR.command=function(a,e){this.uiItems=[];this.exec=function(d){if(this.state==CKEDITOR.TRISTATE_DISABLED||!this.checkAllowed())return!1;this.editorFocus&&a.focus();return!1===this.fire("exec")?!0:!1!==e.exec.call(this,a,d)};this.refresh=function(a,d){if(!this.readOnly&&a.readOnly)return!0;if(this.context&&!d.isContextFor(this.context)||
!this.checkAllowed(!0))return this.disable(),!0;this.startDisabled||this.enable();this.modes&&!this.modes[a.mode]&&this.disable();return!1===this.fire("refresh",{editor:a,path:d})?!0:e.refresh&&!1!==e.refresh.apply(this,arguments)};var d;this.checkAllowed=function(g){return g||"boolean"!=typeof d?d=a.activeFilter.checkFeature(this):d};CKEDITOR.tools.extend(this,e,{modes:{wysiwyg:1},editorFocus:1,contextSensitive:!!e.context,state:CKEDITOR.TRISTATE_DISABLED});CKEDITOR.event.call(this)},CKEDITOR.command.prototype=
{enable:function(){this.state==CKEDITOR.TRISTATE_DISABLED&&this.checkAllowed()&&this.setState(this.preserveState&&"undefined"!=typeof this.previousState?this.previousState:CKEDITOR.TRISTATE_OFF)},disable:function(){this.setState(CKEDITOR.TRISTATE_DISABLED)},setState:function(a){if(this.state==a||a!=CKEDITOR.TRISTATE_DISABLED&&!this.checkAllowed())return!1;this.previousState=this.state;this.state=a;this.fire("state");return!0},toggleState:function(){this.state==CKEDITOR.TRISTATE_OFF?this.setState(CKEDITOR.TRISTATE_ON):
this.state==CKEDITOR.TRISTATE_ON&&this.setState(CKEDITOR.TRISTATE_OFF)}},CKEDITOR.event.implementOn(CKEDITOR.command.prototype),CKEDITOR.ENTER_P=1,CKEDITOR.ENTER_BR=2,CKEDITOR.ENTER_DIV=3,CKEDITOR.config={customConfig:"config.js",autoUpdateElement:!0,language:"",defaultLanguage:"en",contentsLangDirection:"",enterMode:CKEDITOR.ENTER_P,forceEnterMode:!1,shiftEnterMode:CKEDITOR.ENTER_BR,docType:"\x3c!DOCTYPE html\x3e",bodyId:"",bodyClass:"",fullPage:!1,height:200,contentsCss:CKEDITOR.getUrl("contents.css"),
extraPlugins:"",removePlugins:"",protectedSource:[],tabIndex:0,width:"",baseFloatZIndex:1E4,blockedKeystrokes:[CKEDITOR.CTRL+66,CKEDITOR.CTRL+73,CKEDITOR.CTRL+85]},function(){function a(a,b,c,f,d){var g,e;a=[];for(g in b){e=b[g];e="boolean"==typeof e?{}:"function"==typeof e?{match:e}:P(e);"$"!=g.charAt(0)&&(e.elements=g);c&&(e.featureName=c.toLowerCase());var n=e;n.elements=m(n.elements,/\s+/)||null;n.propertiesOnly=n.propertiesOnly||!0===n.elements;var q=/\s*,\s*/,r=void 0;for(r in S){n[r]=m(n[r],
q)||null;var G=n,k=v[r],C=m(n[v[r]],q),u=n[r],p=[],h=!0,D=void 0;C?h=!1:C={};for(D in u)"!"==D.charAt(0)&&(D=D.slice(1),p.push(D),C[D]=!0,h=!1);for(;D=p.pop();)u[D]=u["!"+D],delete u["!"+D];G[k]=(h?!1:C)||null}n.match=n.match||null;f.push(e);a.push(e)}b=d.elements;d=d.generic;var l;c=0;for(f=a.length;c<f;++c){g=P(a[c]);e=!0===g.classes||!0===g.styles||!0===g.attributes;n=g;r=k=q=void 0;for(q in S)n[q]=H(n[q]);G=!0;for(r in v){q=v[r];k=n[q];C=[];u=void 0;for(u in k)-1<u.indexOf("*")?C.push(new RegExp("^"+
u.replace(/\*/g,".*")+"$")):C.push(u);k=C;k.length&&(n[q]=k,G=!1)}n.nothingRequired=G;n.noProperties=!(n.attributes||n.classes||n.styles);if(!0===g.elements||null===g.elements)d[e?"unshift":"push"](g);else for(l in n=g.elements,delete g.elements,n)if(b[l])b[l][e?"unshift":"push"](g);else b[l]=[g]}}function e(a,b,c,f){if(!a.match||a.match(b))if(f||h(a,b))if(a.propertiesOnly||(c.valid=!0),c.allAttributes||(c.allAttributes=d(a.attributes,b.attributes,c.validAttributes)),c.allStyles||(c.allStyles=d(a.styles,
b.styles,c.validStyles)),!c.allClasses){a=a.classes;b=b.classes;f=c.validClasses;if(a)if(!0===a)a=!0;else{for(var g=0,e=b.length,n;g<e;++g)n=b[g],f[n]||(f[n]=a(n));a=!1}else a=!1;c.allClasses=a}}function d(a,b,c){if(!a)return!1;if(!0===a)return!0;for(var f in b)c[f]||(c[f]=a(f));return!1}function g(a,b,c){if(!a.match||a.match(b)){if(a.noProperties)return!1;c.hadInvalidAttribute=l(a.attributes,b.attributes)||c.hadInvalidAttribute;c.hadInvalidStyle=l(a.styles,b.styles)||c.hadInvalidStyle;a=a.classes;
b=b.classes;if(a){for(var f=!1,d=!0===a,g=b.length;g--;)if(d||a(b[g]))b.splice(g,1),f=!0;a=f}else a=!1;c.hadInvalidClass=a||c.hadInvalidClass}}function l(a,b){if(!a)return!1;var c=!1,f=!0===a,d;for(d in b)if(f||a(d))delete b[d],c=!0;return c}function k(a,b,c){if(a.disabled||a.customConfig&&!c||!b)return!1;a._.cachedChecks={};return!0}function m(a,b){if(!a)return!1;if(!0===a)return a;if("string"==typeof a)return a=L(a),"*"==a?!0:CKEDITOR.tools.convertArrayToObject(a.split(b));if(CKEDITOR.tools.isArray(a))return a.length?
CKEDITOR.tools.convertArrayToObject(a):!1;var c={},f=0,d;for(d in a)c[d]=a[d],f++;return f?c:!1}function h(a,c){if(a.nothingRequired)return!0;var f,d,g,e;if(g=a.requiredClasses)for(e=c.classes,f=0;f<g.length;++f)if(d=g[f],"string"==typeof d){if(-1==CKEDITOR.tools.indexOf(e,d))return!1}else if(!CKEDITOR.tools.checkIfAnyArrayItemMatches(e,d))return!1;return b(c.styles,a.requiredStyles)&&b(c.attributes,a.requiredAttributes)}function b(a,b){if(!b)return!0;for(var c=0,f;c<b.length;++c)if(f=b[c],"string"==
typeof f){if(!(f in a))return!1}else if(!CKEDITOR.tools.checkIfAnyObjectPropertyMatches(a,f))return!1;return!0}function c(a){if(!a)return{};a=a.split(/\s*,\s*/).sort();for(var b={};a.length;)b[a.shift()]="cke-test";return b}function f(a){var b,c,f,d,g={},e=1;for(a=L(a);b=a.match(q);)(c=b[2])?(f=p(c,"styles"),d=p(c,"attrs"),c=p(c,"classes")):f=d=c=null,g["$"+e++]={elements:b[1],classes:c,styles:f,attributes:d},a=a.slice(b[0].length);return g}function p(a,b){var c=a.match(N[b]);return c?L(c[1]):null}
function B(a){var b=a.styleBackup=a.attributes.style,c=a.classBackup=a.attributes["class"];a.styles||(a.styles=CKEDITOR.tools.parseCssText(b||"",1));a.classes||(a.classes=c?c.split(/\s+/):[])}function x(a,b,c,f){var d=0,n;f.toHtml&&(b.name=b.name.replace(G,"$1"));if(f.doCallbacks&&a.elementCallbacks){a:{n=a.elementCallbacks;for(var q=0,v=n.length,k;q<v;++q)if(k=n[q](b)){n=k;break a}n=void 0}if(n)return n}if(f.doTransform&&(n=a._.transformations[b.name])){B(b);for(q=0;q<n.length;++q)r(a,b,n[q]);u(b)}if(f.doFilter){a:{q=
b.name;v=a._;a=v.allowedRules.elements[q];n=v.allowedRules.generic;q=v.disallowedRules.elements[q];v=v.disallowedRules.generic;k=f.skipRequired;var C={valid:!1,validAttributes:{},validClasses:{},validStyles:{},allAttributes:!1,allClasses:!1,allStyles:!1,hadInvalidAttribute:!1,hadInvalidClass:!1,hadInvalidStyle:!1},p,h;if(a||n){B(b);if(q)for(p=0,h=q.length;p<h;++p)if(!1===g(q[p],b,C)){a=null;break a}if(v)for(p=0,h=v.length;p<h;++p)g(v[p],b,C);if(a)for(p=0,h=a.length;p<h;++p)e(a[p],b,C,k);if(n)for(p=
0,h=n.length;p<h;++p)e(n[p],b,C,k);a=C}else a=null}if(!a||!a.valid)return c.push(b),1;h=a.validAttributes;var D=a.validStyles;n=a.validClasses;var q=b.attributes,l=b.styles,v=b.classes;k=b.classBackup;var N=b.styleBackup,z,m,R=[],C=[],K=/^data-cke-/;p=!1;delete q.style;delete q["class"];delete b.classBackup;delete b.styleBackup;if(!a.allAttributes)for(z in q)h[z]||(K.test(z)?z==(m=z.replace(/^data-cke-saved-/,""))||h[m]||(delete q[z],p=!0):(delete q[z],p=!0));if(!a.allStyles||a.hadInvalidStyle){for(z in l)a.allStyles||
D[z]?R.push(z+":"+l[z]):p=!0;R.length&&(q.style=R.sort().join("; "))}else N&&(q.style=N);if(!a.allClasses||a.hadInvalidClass){for(z=0;z<v.length;++z)(a.allClasses||n[v[z]])&&C.push(v[z]);C.length&&(q["class"]=C.sort().join(" "));k&&C.length<k.split(/\s+/).length&&(p=!0)}else k&&(q["class"]=k);p&&(d=1);if(!f.skipFinalValidation&&!y(b))return c.push(b),1}f.toHtml&&(b.name=b.name.replace(X,"cke:$1"));return d}function t(a){var b=[],c;for(c in a)-1<c.indexOf("*")&&b.push(c.replace(/\*/g,".*"));return b.length?
new RegExp("^(?:"+b.join("|")+")$"):null}function u(a){var b=a.attributes,c;delete b.style;delete b["class"];if(c=CKEDITOR.tools.writeCssText(a.styles,!0))b.style=c;a.classes.length&&(b["class"]=a.classes.sort().join(" "))}function y(a){switch(a.name){case "a":if(!(a.children.length||a.attributes.name||a.attributes.id))return!1;break;case "img":if(!a.attributes.src)return!1}return!0}function H(a){if(!a)return!1;if(!0===a)return!0;var b=t(a);return function(c){return c in a||b&&c.match(b)}}function w(){return new CKEDITOR.htmlParser.element("br")}
function F(a){return a.type==CKEDITOR.NODE_ELEMENT&&("br"==a.name||J.$block[a.name])}function n(a,b,c){var f=a.name;if(J.$empty[f]||!a.children.length)"hr"==f&&"br"==b?a.replaceWith(w()):(a.parent&&c.push({check:"it",el:a.parent}),a.remove());else if(J.$block[f]||"tr"==f)if("br"==b)a.previous&&!F(a.previous)&&(b=w(),b.insertBefore(a)),a.next&&!F(a.next)&&(b=w(),b.insertAfter(a)),a.replaceWithChildren();else{var f=a.children,d;b:{d=J[b];for(var g=0,e=f.length,n;g<e;++g)if(n=f[g],n.type==CKEDITOR.NODE_ELEMENT&&
!d[n.name]){d=!1;break b}d=!0}if(d)a.name=b,a.attributes={},c.push({check:"parent-down",el:a});else{d=a.parent;for(var g=d.type==CKEDITOR.NODE_DOCUMENT_FRAGMENT||"body"==d.name,q,r,e=f.length;0<e;)n=f[--e],g&&(n.type==CKEDITOR.NODE_TEXT||n.type==CKEDITOR.NODE_ELEMENT&&J.$inline[n.name])?(q||(q=new CKEDITOR.htmlParser.element(b),q.insertAfter(a),c.push({check:"parent-down",el:q})),q.add(n,0)):(q=null,r=J[d.name]||J.span,n.insertAfter(a),d.type==CKEDITOR.NODE_DOCUMENT_FRAGMENT||n.type!=CKEDITOR.NODE_ELEMENT||
r[n.name]||c.push({check:"el-up",el:n}));a.remove()}}else f in{style:1,script:1}?a.remove():(a.parent&&c.push({check:"it",el:a.parent}),a.replaceWithChildren())}function r(a,b,c){var f,d;for(f=0;f<c.length;++f)if(d=c[f],!(d.check&&!a.check(d.check,!1)||d.left&&!d.left(b))){d.right(b,R);break}}function C(a,b){var c=b.getDefinition(),f=c.attributes,d=c.styles,g,e,n,q;if(a.name!=c.element)return!1;for(g in f)if("class"==g)for(c=f[g].split(/\s+/),n=a.classes.join("|");q=c.pop();){if(-1==n.indexOf(q))return!1}else if(a.attributes[g]!=
f[g])return!1;for(e in d)if(a.styles[e]!=d[e])return!1;return!0}function D(a,b){var c,f;"string"==typeof a?c=a:a instanceof CKEDITOR.style?f=a:(c=a[0],f=a[1]);return[{element:c,left:f,right:function(a,c){c.transform(a,b)}}]}function z(a){return function(b){return C(b,a)}}function K(a){return function(b,c){c[a](b)}}var J=CKEDITOR.dtd,P=CKEDITOR.tools.copy,L=CKEDITOR.tools.trim,O=["","p","br","div"];CKEDITOR.FILTER_SKIP_TREE=2;CKEDITOR.filter=function(a){this.allowedContent=[];this.disallowedContent=
[];this.elementCallbacks=null;this.disabled=!1;this.editor=null;this.id=CKEDITOR.tools.getNextNumber();this._={allowedRules:{elements:{},generic:[]},disallowedRules:{elements:{},generic:[]},transformations:{},cachedTests:{}};CKEDITOR.filter.instances[this.id]=this;if(a instanceof CKEDITOR.editor){a=this.editor=a;this.customConfig=!0;var b=a.config.allowedContent;!0===b?this.disabled=!0:(b||(this.customConfig=!1),this.allow(b,"config",1),this.allow(a.config.extraAllowedContent,"extra",1),this.allow(O[a.enterMode]+
" "+O[a.shiftEnterMode],"default",1),this.disallow(a.config.disallowedContent))}else this.customConfig=!1,this.allow(a,"default",1)};CKEDITOR.filter.instances={};CKEDITOR.filter.prototype={allow:function(b,c,d){if(!k(this,b,d))return!1;var g,e;if("string"==typeof b)b=f(b);else if(b instanceof CKEDITOR.style){if(b.toAllowedContentRules)return this.allow(b.toAllowedContentRules(this.editor),c,d);g=b.getDefinition();b={};d=g.attributes;b[g.element]=g={styles:g.styles,requiredStyles:g.styles&&CKEDITOR.tools.objectKeys(g.styles)};
d&&(d=P(d),g.classes=d["class"]?d["class"].split(/\s+/):null,g.requiredClasses=g.classes,delete d["class"],g.attributes=d,g.requiredAttributes=d&&CKEDITOR.tools.objectKeys(d))}else if(CKEDITOR.tools.isArray(b)){for(g=0;g<b.length;++g)e=this.allow(b[g],c,d);return e}a(this,b,c,this.allowedContent,this._.allowedRules);return!0},applyTo:function(a,b,c,f){if(this.disabled)return!1;var d=this,g=[],e=this.editor&&this.editor.config.protectedSource,q,r=!1,v={doFilter:!c,doTransform:!0,doCallbacks:!0,toHtml:b};
a.forEach(function(a){if(a.type==CKEDITOR.NODE_ELEMENT){if("off"==a.attributes["data-cke-filter"])return!1;if(!b||"span"!=a.name||!~CKEDITOR.tools.objectKeys(a.attributes).join("|").indexOf("data-cke-"))if(q=x(d,a,g,v),q&1)r=!0;else if(q&2)return!1}else if(a.type==CKEDITOR.NODE_COMMENT&&a.value.match(/^\{cke_protected\}(?!\{C\})/)){var c;a:{var f=decodeURIComponent(a.value.replace(/^\{cke_protected\}/,""));c=[];var n,G,k;if(e)for(G=0;G<e.length;++G)if((k=f.match(e[G]))&&k[0].length==f.length){c=!0;
break a}f=CKEDITOR.htmlParser.fragment.fromHtml(f);1==f.children.length&&(n=f.children[0]).type==CKEDITOR.NODE_ELEMENT&&x(d,n,c,v);c=!c.length}c||g.push(a)}},null,!0);g.length&&(r=!0);var G;a=[];f=O[f||(this.editor?this.editor.enterMode:CKEDITOR.ENTER_P)];for(var k;c=g.pop();)c.type==CKEDITOR.NODE_ELEMENT?n(c,f,a):c.remove();for(;G=a.pop();)if(c=G.el,c.parent)switch(k=J[c.parent.name]||J.span,G.check){case "it":J.$removeEmpty[c.name]&&!c.children.length?n(c,f,a):y(c)||n(c,f,a);break;case "el-up":c.parent.type==
CKEDITOR.NODE_DOCUMENT_FRAGMENT||k[c.name]||n(c,f,a);break;case "parent-down":c.parent.type==CKEDITOR.NODE_DOCUMENT_FRAGMENT||k[c.name]||n(c.parent,f,a)}return r},checkFeature:function(a){if(this.disabled||!a)return!0;a.toFeature&&(a=a.toFeature(this.editor));return!a.requiredContent||this.check(a.requiredContent)},disable:function(){this.disabled=!0},disallow:function(b){if(!k(this,b,!0))return!1;"string"==typeof b&&(b=f(b));a(this,b,null,this.disallowedContent,this._.disallowedRules);return!0},
addContentForms:function(a){if(!this.disabled&&a){var b,c,f=[],d;for(b=0;b<a.length&&!d;++b)c=a[b],("string"==typeof c||c instanceof CKEDITOR.style)&&this.check(c)&&(d=c);if(d){for(b=0;b<a.length;++b)f.push(D(a[b],d));this.addTransformations(f)}}},addElementCallback:function(a){this.elementCallbacks||(this.elementCallbacks=[]);this.elementCallbacks.push(a)},addFeature:function(a){if(this.disabled||!a)return!0;a.toFeature&&(a=a.toFeature(this.editor));this.allow(a.allowedContent,a.name);this.addTransformations(a.contentTransformations);
this.addContentForms(a.contentForms);return a.requiredContent&&(this.customConfig||this.disallowedContent.length)?this.check(a.requiredContent):!0},addTransformations:function(a){var b,c;if(!this.disabled&&a){var f=this._.transformations,d;for(d=0;d<a.length;++d){b=a[d];var g=void 0,e=void 0,n=void 0,q=void 0,r=void 0,v=void 0;c=[];for(e=0;e<b.length;++e)n=b[e],"string"==typeof n?(n=n.split(/\s*:\s*/),q=n[0],r=null,v=n[1]):(q=n.check,r=n.left,v=n.right),g||(g=n,g=g.element?g.element:q?q.match(/^([a-z0-9]+)/i)[0]:
g.left.getDefinition().element),r instanceof CKEDITOR.style&&(r=z(r)),c.push({check:q==g?null:q,left:r,right:"string"==typeof v?K(v):v});b=g;f[b]||(f[b]=[]);f[b].push(c)}}},check:function(a,b,d){if(this.disabled)return!0;if(CKEDITOR.tools.isArray(a)){for(var g=a.length;g--;)if(this.check(a[g],b,d))return!0;return!1}var e,n;if("string"==typeof a){n=a+"\x3c"+(!1===b?"0":"1")+(d?"1":"0")+"\x3e";if(n in this._.cachedChecks)return this._.cachedChecks[n];g=f(a).$1;e=g.styles;var q=g.classes;g.name=g.elements;
g.classes=q=q?q.split(/\s*,\s*/):[];g.styles=c(e);g.attributes=c(g.attributes);g.children=[];q.length&&(g.attributes["class"]=q.join(" "));e&&(g.attributes.style=CKEDITOR.tools.writeCssText(g.styles));e=g}else g=a.getDefinition(),e=g.styles,q=g.attributes||{},e&&!CKEDITOR.tools.isEmpty(e)?(e=P(e),q.style=CKEDITOR.tools.writeCssText(e,!0)):e={},e={name:g.element,attributes:q,classes:q["class"]?q["class"].split(/\s+/):[],styles:e,children:[]};var q=CKEDITOR.tools.clone(e),v=[],G;if(!1!==b&&(G=this._.transformations[e.name])){for(g=
0;g<G.length;++g)r(this,e,G[g]);u(e)}x(this,q,v,{doFilter:!0,doTransform:!1!==b,skipRequired:!d,skipFinalValidation:!d});b=0<v.length?!1:CKEDITOR.tools.objectCompare(e.attributes,q.attributes,!0)?!0:!1;"string"==typeof a&&(this._.cachedChecks[n]=b);return b},getAllowedEnterMode:function(){var a=["p","div","br"],b={p:CKEDITOR.ENTER_P,div:CKEDITOR.ENTER_DIV,br:CKEDITOR.ENTER_BR};return function(c,f){var d=a.slice(),g;if(this.check(O[c]))return c;for(f||(d=d.reverse());g=d.pop();)if(this.check(g))return b[g];
return CKEDITOR.ENTER_BR}}(),destroy:function(){delete CKEDITOR.filter.instances[this.id];delete this._;delete this.allowedContent;delete this.disallowedContent}};var S={styles:1,attributes:1,classes:1},v={styles:"requiredStyles",attributes:"requiredAttributes",classes:"requiredClasses"},q=/^([a-z0-9\-*\s]+)((?:\s*\{[!\w\-,\s\*]+\}\s*|\s*\[[!\w\-,\s\*]+\]\s*|\s*\([!\w\-,\s\*]+\)\s*){0,3})(?:;\s*|$)/i,N={styles:/{([^}]+)}/,attrs:/\[([^\]]+)\]/,classes:/\(([^\)]+)\)/},G=/^cke:(object|embed|param)$/,
X=/^(object|embed|param)$/,R;R=CKEDITOR.filter.transformationsTools={sizeToStyle:function(a){this.lengthToStyle(a,"width");this.lengthToStyle(a,"height")},sizeToAttribute:function(a){this.lengthToAttribute(a,"width");this.lengthToAttribute(a,"height")},lengthToStyle:function(a,b,c){c=c||b;if(!(c in a.styles)){var f=a.attributes[b];f&&(/^\d+$/.test(f)&&(f+="px"),a.styles[c]=f)}delete a.attributes[b]},lengthToAttribute:function(a,b,c){c=c||b;if(!(c in a.attributes)){var f=a.styles[b],d=f&&f.match(/^(\d+)(?:\.\d*)?px$/);
d?a.attributes[c]=d[1]:"cke-test"==f&&(a.attributes[c]="cke-test")}delete a.styles[b]},alignmentToStyle:function(a){if(!("float"in a.styles)){var b=a.attributes.align;if("left"==b||"right"==b)a.styles["float"]=b}delete a.attributes.align},alignmentToAttribute:function(a){if(!("align"in a.attributes)){var b=a.styles["float"];if("left"==b||"right"==b)a.attributes.align=b}delete a.styles["float"]},splitBorderShorthand:function(a){function b(f){a.styles["border-top-width"]=c[f[0]];a.styles["border-right-width"]=
c[f[1]];a.styles["border-bottom-width"]=c[f[2]];a.styles["border-left-width"]=c[f[3]]}if(a.styles.border){var c=a.styles.border.match(/([\.\d]+\w+)/g)||["0px"];switch(c.length){case 1:a.styles["border-width"]=c[0];break;case 2:b([0,1,0,1]);break;case 3:b([0,1,2,1]);break;case 4:b([0,1,2,3])}a.styles["border-style"]=a.styles["border-style"]||(a.styles.border.match(/(none|hidden|dotted|dashed|solid|double|groove|ridge|inset|outset|initial|inherit)/)||[])[0];a.styles["border-style"]||delete a.styles["border-style"];
delete a.styles.border}},listTypeToStyle:function(a){if(a.attributes.type)switch(a.attributes.type){case "a":a.styles["list-style-type"]="lower-alpha";break;case "A":a.styles["list-style-type"]="upper-alpha";break;case "i":a.styles["list-style-type"]="lower-roman";break;case "I":a.styles["list-style-type"]="upper-roman";break;case "1":a.styles["list-style-type"]="decimal";break;default:a.styles["list-style-type"]=a.attributes.type}},splitMarginShorthand:function(a){function b(f){a.styles["margin-top"]=
c[f[0]];a.styles["margin-right"]=c[f[1]];a.styles["margin-bottom"]=c[f[2]];a.styles["margin-left"]=c[f[3]]}if(a.styles.margin){var c=a.styles.margin.match(/(\-?[\.\d]+\w+)/g)||["0px"];switch(c.length){case 1:a.styles.margin=c[0];break;case 2:b([0,1,0,1]);break;case 3:b([0,1,2,1]);break;case 4:b([0,1,2,3])}delete a.styles.margin}},matchesStyle:C,transform:function(a,b){if("string"==typeof b)a.name=b;else{var c=b.getDefinition(),f=c.styles,d=c.attributes,g,e,n,q;a.name=c.element;for(g in d)if("class"==
g)for(c=a.classes.join("|"),n=d[g].split(/\s+/);q=n.pop();)-1==c.indexOf(q)&&a.classes.push(q);else a.attributes[g]=d[g];for(e in f)a.styles[e]=f[e]}}}}(),function(){CKEDITOR.focusManager=function(a){if(a.focusManager)return a.focusManager;this.hasFocus=!1;this.currentActive=null;this._={editor:a};return this};CKEDITOR.focusManager._={blurDelay:200};CKEDITOR.focusManager.prototype={focus:function(a){this._.timer&&clearTimeout(this._.timer);a&&(this.currentActive=a);this.hasFocus||this._.locked||((a=
CKEDITOR.currentInstance)&&a.focusManager.blur(1),this.hasFocus=!0,(a=this._.editor.container)&&a.addClass("cke_focus"),this._.editor.fire("focus"))},lock:function(){this._.locked=1},unlock:function(){delete this._.locked},blur:function(a){function e(){if(this.hasFocus){this.hasFocus=!1;var a=this._.editor.container;a&&a.removeClass("cke_focus");this._.editor.fire("blur")}}if(!this._.locked){this._.timer&&clearTimeout(this._.timer);var d=CKEDITOR.focusManager._.blurDelay;a||!d?e.call(this):this._.timer=
CKEDITOR.tools.setTimeout(function(){delete this._.timer;e.call(this)},d,this)}},add:function(a,e){var d=a.getCustomData("focusmanager");if(!d||d!=this){d&&d.remove(a);var d="focus",g="blur";e&&(CKEDITOR.env.ie?(d="focusin",g="focusout"):CKEDITOR.event.useCapture=1);var l={blur:function(){a.equals(this.currentActive)&&this.blur()},focus:function(){this.focus(a)}};a.on(d,l.focus,this);a.on(g,l.blur,this);e&&(CKEDITOR.event.useCapture=0);a.setCustomData("focusmanager",this);a.setCustomData("focusmanager_handlers",
l)}},remove:function(a){a.removeCustomData("focusmanager");var e=a.removeCustomData("focusmanager_handlers");a.removeListener("blur",e.blur);a.removeListener("focus",e.focus)}}}(),CKEDITOR.keystrokeHandler=function(a){if(a.keystrokeHandler)return a.keystrokeHandler;this.keystrokes={};this.blockedKeystrokes={};this._={editor:a};return this},function(){var a,e=function(d){d=d.data;var e=d.getKeystroke(),k=this.keystrokes[e],m=this._.editor;a=!1===m.fire("key",{keyCode:e,domEvent:d});a||(k&&(a=!1!==
m.execCommand(k,{from:"keystrokeHandler"})),a||(a=!!this.blockedKeystrokes[e]));a&&d.preventDefault(!0);return!a},d=function(d){a&&(a=!1,d.data.preventDefault(!0))};CKEDITOR.keystrokeHandler.prototype={attach:function(a){a.on("keydown",e,this);if(CKEDITOR.env.gecko&&CKEDITOR.env.mac)a.on("keypress",d,this)}}}(),function(){CKEDITOR.lang={languages:{af:1,ar:1,bg:1,bn:1,bs:1,ca:1,cs:1,cy:1,da:1,de:1,"de-ch":1,el:1,"en-au":1,"en-ca":1,"en-gb":1,en:1,eo:1,es:1,et:1,eu:1,fa:1,fi:1,fo:1,"fr-ca":1,fr:1,gl:1,
gu:1,he:1,hi:1,hr:1,hu:1,id:1,is:1,it:1,ja:1,ka:1,km:1,ko:1,ku:1,lt:1,lv:1,mk:1,mn:1,ms:1,nb:1,nl:1,no:1,oc:1,pl:1,"pt-br":1,pt:1,ro:1,ru:1,si:1,sk:1,sl:1,sq:1,"sr-latn":1,sr:1,sv:1,th:1,tr:1,tt:1,ug:1,uk:1,vi:1,"zh-cn":1,zh:1},rtl:{ar:1,fa:1,he:1,ku:1,ug:1},load:function(a,e,d){a&&CKEDITOR.lang.languages[a]||(a=this.detect(e,a));var g=this;e=function(){g[a].dir=g.rtl[a]?"rtl":"ltr";d(a,g[a])};this[a]?e():CKEDITOR.scriptLoader.load(CKEDITOR.getUrl("lang/"+a+".js"),e,this)},detect:function(a,e){var d=
this.languages;e=e||navigator.userLanguage||navigator.language||a;var g=e.toLowerCase().match(/([a-z]+)(?:-([a-z]+))?/),l=g[1],g=g[2];d[l+"-"+g]?l=l+"-"+g:d[l]||(l=null);CKEDITOR.lang.detect=l?function(){return l}:function(a){return a};return l||a}}}(),CKEDITOR.scriptLoader=function(){var a={},e={};return{load:function(d,g,l,k){var m="string"==typeof d;m&&(d=[d]);l||(l=CKEDITOR);var h=d.length,b=[],c=[],f=function(a){g&&(m?g.call(l,a):g.call(l,b,c))};if(0===h)f(!0);else{var p=function(a,d){(d?b:c).push(a);
0>=--h&&(k&&CKEDITOR.document.getDocumentElement().removeStyle("cursor"),f(d))},B=function(b,c){a[b]=1;var f=e[b];delete e[b];for(var d=0;d<f.length;d++)f[d](b,c)},x=function(b){if(a[b])p(b,!0);else{var c=e[b]||(e[b]=[]);c.push(p);if(!(1<c.length)){var f=new CKEDITOR.dom.element("script");f.setAttributes({type:"text/javascript",src:b});g&&(CKEDITOR.env.ie&&(8>=CKEDITOR.env.version||CKEDITOR.env.ie9Compat)?f.$.onreadystatechange=function(){if("loaded"==f.$.readyState||"complete"==f.$.readyState)f.$.onreadystatechange=
null,B(b,!0)}:(f.$.onload=function(){setTimeout(function(){B(b,!0)},0)},f.$.onerror=function(){B(b,!1)}));f.appendTo(CKEDITOR.document.getHead())}}};k&&CKEDITOR.document.getDocumentElement().setStyle("cursor","wait");for(var t=0;t<h;t++)x(d[t])}},queue:function(){function a(){var d;(d=g[0])&&this.load(d.scriptUrl,d.callback,CKEDITOR,0)}var g=[];return function(e,k){var m=this;g.push({scriptUrl:e,callback:function(){k&&k.apply(this,arguments);g.shift();a.call(m)}});1==g.length&&a.call(this)}}()}}(),
CKEDITOR.resourceManager=function(a,e){this.basePath=a;this.fileName=e;this.registered={};this.loaded={};this.externals={};this._={waitingList:{}}},CKEDITOR.resourceManager.prototype={add:function(a,e){if(this.registered[a])throw Error('[CKEDITOR.resourceManager.add] The resource name "'+a+'" is already registered.');var d=this.registered[a]=e||{};d.name=a;d.path=this.getPath(a);CKEDITOR.fire(a+CKEDITOR.tools.capitalize(this.fileName)+"Ready",d);return this.get(a)},get:function(a){return this.registered[a]||
null},getPath:function(a){var e=this.externals[a];return CKEDITOR.getUrl(e&&e.dir||this.basePath+a+"/")},getFilePath:function(a){var e=this.externals[a];return CKEDITOR.getUrl(this.getPath(a)+(e?e.file:this.fileName+".js"))},addExternal:function(a,e,d){a=a.split(",");for(var g=0;g<a.length;g++){var l=a[g];d||(e=e.replace(/[^\/]+$/,function(a){d=a;return""}));this.externals[l]={dir:e,file:d||this.fileName+".js"}}},load:function(a,e,d){CKEDITOR.tools.isArray(a)||(a=a?[a]:[]);for(var g=this.loaded,l=
this.registered,k=[],m={},h={},b=0;b<a.length;b++){var c=a[b];if(c)if(g[c]||l[c])h[c]=this.get(c);else{var f=this.getFilePath(c);k.push(f);f in m||(m[f]=[]);m[f].push(c)}}CKEDITOR.scriptLoader.load(k,function(a,b){if(b.length)throw Error('[CKEDITOR.resourceManager.load] Resource name "'+m[b[0]].join(",")+'" was not found at "'+b[0]+'".');for(var c=0;c<a.length;c++)for(var f=m[a[c]],k=0;k<f.length;k++){var l=f[k];h[l]=this.get(l);g[l]=1}e.call(d,h)},this)}},CKEDITOR.plugins=new CKEDITOR.resourceManager("plugins/",
"plugin"),CKEDITOR.plugins.load=CKEDITOR.tools.override(CKEDITOR.plugins.load,function(a){var e={};return function(d,g,l){var k={},m=function(d){a.call(this,d,function(a){CKEDITOR.tools.extend(k,a);var c=[],f;for(f in a){var d=a[f],h=d&&d.requires;if(!e[f]){if(d.icons)for(var x=d.icons.split(","),t=x.length;t--;)CKEDITOR.skin.addIcon(x[t],d.path+"icons/"+(CKEDITOR.env.hidpi&&d.hidpi?"hidpi/":"")+x[t]+".png");e[f]=1}if(h)for(h.split&&(h=h.split(",")),d=0;d<h.length;d++)k[h[d]]||c.push(h[d])}if(c.length)m.call(this,
c);else{for(f in k)d=k[f],d.onLoad&&!d.onLoad._called&&(!1===d.onLoad()&&delete k[f],d.onLoad._called=1);g&&g.call(l||window,k)}},this)};m.call(this,d)}}),CKEDITOR.plugins.setLang=function(a,e,d){var g=this.get(a);a=g.langEntries||(g.langEntries={});g=g.lang||(g.lang=[]);g.split&&(g=g.split(","));-1==CKEDITOR.tools.indexOf(g,e)&&g.push(e);a[e]=d},CKEDITOR.ui=function(a){if(a.ui)return a.ui;this.items={};this.instances={};this.editor=a;this._={handlers:{}};return this},CKEDITOR.ui.prototype={add:function(a,
e,d){d.name=a.toLowerCase();var g=this.items[a]={type:e,command:d.command||null,args:Array.prototype.slice.call(arguments,2)};CKEDITOR.tools.extend(g,d)},get:function(a){return this.instances[a]},create:function(a){var e=this.items[a],d=e&&this._.handlers[e.type],g=e&&e.command&&this.editor.getCommand(e.command),d=d&&d.create.apply(this,e.args);this.instances[a]=d;g&&g.uiItems.push(d);d&&!d.type&&(d.type=e.type);return d},addHandler:function(a,e){this._.handlers[a]=e},space:function(a){return CKEDITOR.document.getById(this.spaceId(a))},
spaceId:function(a){return this.editor.id+"_"+a}},CKEDITOR.event.implementOn(CKEDITOR.ui),function(){function a(a,b,c){CKEDITOR.event.call(this);a=a&&CKEDITOR.tools.clone(a);if(void 0!==b){if(!(b instanceof CKEDITOR.dom.element))throw Error("Expect element of type CKEDITOR.dom.element.");if(!c)throw Error("One of the element modes must be specified.");if(CKEDITOR.env.ie&&CKEDITOR.env.quirks&&c==CKEDITOR.ELEMENT_MODE_INLINE)throw Error("Inline element mode is not supported on IE quirks.");if(!d(b,
c))throw Error('The specified element mode is not supported on element: "'+b.getName()+'".');this.element=b;this.elementMode=c;this.name=this.elementMode!=CKEDITOR.ELEMENT_MODE_APPENDTO&&(b.getId()||b.getNameAtt())}else this.elementMode=CKEDITOR.ELEMENT_MODE_NONE;this._={};this.commands={};this.templates={};this.name=this.name||e();this.id=CKEDITOR.tools.getNextId();this.status="unloaded";this.config=CKEDITOR.tools.prototypedCopy(CKEDITOR.config);this.ui=new CKEDITOR.ui(this);this.focusManager=new CKEDITOR.focusManager(this);
this.keystrokeHandler=new CKEDITOR.keystrokeHandler(this);this.on("readOnly",g);this.on("selectionChange",function(a){k(this,a.data.path)});this.on("activeFilterChange",function(){k(this,this.elementPath(),!0)});this.on("mode",g);this.on("instanceReady",function(){this.config.startupFocus&&this.focus()});CKEDITOR.fire("instanceCreated",null,this);CKEDITOR.add(this);CKEDITOR.tools.setTimeout(function(){"destroyed"!==this.status?h(this,a):CKEDITOR.warn("editor-incorrect-destroy")},0,this)}function e(){do var a=
"editor"+ ++x;while(CKEDITOR.instances[a]);return a}function d(a,b){return b==CKEDITOR.ELEMENT_MODE_INLINE?a.is(CKEDITOR.dtd.$editable)||a.is("textarea"):b==CKEDITOR.ELEMENT_MODE_REPLACE?!a.is(CKEDITOR.dtd.$nonBodyContent):1}function g(){var a=this.commands,b;for(b in a)l(this,a[b])}function l(a,b){b[b.startDisabled?"disable":a.readOnly&&!b.readOnly?"disable":b.modes[a.mode]?"enable":"disable"]()}function k(a,b,c){if(b){var f,d,g=a.commands;for(d in g)f=g[d],(c||f.contextSensitive)&&f.refresh(a,b)}}
function m(a){var b=a.config.customConfig;if(!b)return!1;var b=CKEDITOR.getUrl(b),c=t[b]||(t[b]={});c.fn?(c.fn.call(a,a.config),CKEDITOR.getUrl(a.config.customConfig)!=b&&m(a)||a.fireOnce("customConfigLoaded")):CKEDITOR.scriptLoader.queue(b,function(){c.fn=CKEDITOR.editorConfig?CKEDITOR.editorConfig:function(){};m(a)});return!0}function h(a,c){a.on("customConfigLoaded",function(){if(c){if(c.on)for(var f in c.on)a.on(f,c.on[f]);CKEDITOR.tools.extend(a.config,c,!0);delete a.config.on}f=a.config;a.readOnly=
f.readOnly?!0:a.elementMode==CKEDITOR.ELEMENT_MODE_INLINE?a.element.is("textarea")?a.element.hasAttribute("disabled")||a.element.hasAttribute("readonly"):a.element.isReadOnly():a.elementMode==CKEDITOR.ELEMENT_MODE_REPLACE?a.element.hasAttribute("disabled")||a.element.hasAttribute("readonly"):!1;a.blockless=a.elementMode==CKEDITOR.ELEMENT_MODE_INLINE?!(a.element.is("textarea")||CKEDITOR.dtd[a.element.getName()].p):!1;a.tabIndex=f.tabIndex||a.element&&a.element.getAttribute("tabindex")||0;a.activeEnterMode=
a.enterMode=a.blockless?CKEDITOR.ENTER_BR:f.enterMode;a.activeShiftEnterMode=a.shiftEnterMode=a.blockless?CKEDITOR.ENTER_BR:f.shiftEnterMode;f.skin&&(CKEDITOR.skinName=f.skin);a.fireOnce("configLoaded");a.dataProcessor=new CKEDITOR.htmlDataProcessor(a);a.filter=a.activeFilter=new CKEDITOR.filter(a);b(a)});c&&null!=c.customConfig&&(a.config.customConfig=c.customConfig);m(a)||a.fireOnce("customConfigLoaded")}function b(a){CKEDITOR.skin.loadPart("editor",function(){c(a)})}function c(a){CKEDITOR.lang.load(a.config.language,
a.config.defaultLanguage,function(b,c){var d=a.config.title;a.langCode=b;a.lang=CKEDITOR.tools.prototypedCopy(c);a.title="string"==typeof d||!1===d?d:[a.lang.editor,a.name].join(", ");a.config.contentsLangDirection||(a.config.contentsLangDirection=a.elementMode==CKEDITOR.ELEMENT_MODE_INLINE?a.element.getDirection(1):a.lang.dir);a.fire("langLoaded");f(a)})}function f(a){a.getStylesSet(function(b){a.once("loaded",function(){a.fire("stylesSet",{styles:b})},null,null,1);p(a)})}function p(a){var b=a.config,
c=b.plugins,f=b.extraPlugins,d=b.removePlugins;if(f)var g=new RegExp("(?:^|,)(?:"+f.replace(/\s*,\s*/g,"|")+")(?\x3d,|$)","g"),c=c.replace(g,""),c=c+(","+f);if(d)var e=new RegExp("(?:^|,)(?:"+d.replace(/\s*,\s*/g,"|")+")(?\x3d,|$)","g"),c=c.replace(e,"");CKEDITOR.env.air&&(c+=",adobeair");CKEDITOR.plugins.load(c.split(","),function(c){var f=[],d=[],g=[];a.plugins=c;for(var n in c){var k=c[n],h=k.lang,p=null,l=k.requires,v;CKEDITOR.tools.isArray(l)&&(l=l.join(","));if(l&&(v=l.match(e)))for(;l=v.pop();)CKEDITOR.error("editor-plugin-required",
{plugin:l.replace(",",""),requiredBy:n});h&&!a.lang[n]&&(h.split&&(h=h.split(",")),0<=CKEDITOR.tools.indexOf(h,a.langCode)?p=a.langCode:(p=a.langCode.replace(/-.*/,""),p=p!=a.langCode&&0<=CKEDITOR.tools.indexOf(h,p)?p:0<=CKEDITOR.tools.indexOf(h,"en")?"en":h[0]),k.langEntries&&k.langEntries[p]?(a.lang[n]=k.langEntries[p],p=null):g.push(CKEDITOR.getUrl(k.path+"lang/"+p+".js")));d.push(p);f.push(k)}CKEDITOR.scriptLoader.load(g,function(){for(var c=["beforeInit","init","afterInit"],g=0;g<c.length;g++)for(var e=
0;e<f.length;e++){var n=f[e];0===g&&d[e]&&n.lang&&n.langEntries&&(a.lang[n.name]=n.langEntries[d[e]]);if(n[c[g]])n[c[g]](a)}a.fireOnce("pluginsLoaded");b.keystrokes&&a.setKeystroke(a.config.keystrokes);for(e=0;e<a.config.blockedKeystrokes.length;e++)a.keystrokeHandler.blockedKeystrokes[a.config.blockedKeystrokes[e]]=1;a.status="loaded";a.fireOnce("loaded");CKEDITOR.fire("instanceLoaded",null,a)})})}function B(){var a=this.element;if(a&&this.elementMode!=CKEDITOR.ELEMENT_MODE_APPENDTO){var b=this.getData();
this.config.htmlEncodeOutput&&(b=CKEDITOR.tools.htmlEncode(b));a.is("textarea")?a.setValue(b):a.setHtml(b);return!0}return!1}a.prototype=CKEDITOR.editor.prototype;CKEDITOR.editor=a;var x=0,t={};CKEDITOR.tools.extend(CKEDITOR.editor.prototype,{addCommand:function(a,b){b.name=a.toLowerCase();var c=new CKEDITOR.command(this,b);this.mode&&l(this,c);return this.commands[a]=c},_attachToForm:function(){function a(b){c.updateElement();c._.required&&!f.getValue()&&!1===c.fire("required")&&b.data.preventDefault()}
function b(a){return!!(a&&a.call&&a.apply)}var c=this,f=c.element,d=new CKEDITOR.dom.element(f.$.form);f.is("textarea")&&d&&(d.on("submit",a),b(d.$.submit)&&(d.$.submit=CKEDITOR.tools.override(d.$.submit,function(b){return function(){a();b.apply?b.apply(this):b()}})),c.on("destroy",function(){d.removeListener("submit",a)}))},destroy:function(a){this.fire("beforeDestroy");!a&&B.call(this);this.editable(null);this.filter&&(this.filter.destroy(),delete this.filter);delete this.activeFilter;this.status=
"destroyed";this.fire("destroy");this.removeAllListeners();CKEDITOR.remove(this);CKEDITOR.fire("instanceDestroyed",null,this)},elementPath:function(a){if(!a){a=this.getSelection();if(!a)return null;a=a.getStartElement()}return a?new CKEDITOR.dom.elementPath(a,this.editable()):null},createRange:function(){var a=this.editable();return a?new CKEDITOR.dom.range(a):null},execCommand:function(a,b){var c=this.getCommand(a),f={name:a,commandData:b,command:c};return c&&c.state!=CKEDITOR.TRISTATE_DISABLED&&
!1!==this.fire("beforeCommandExec",f)&&(f.returnValue=c.exec(f.commandData),!c.async&&!1!==this.fire("afterCommandExec",f))?f.returnValue:!1},getCommand:function(a){return this.commands[a]},getData:function(a){!a&&this.fire("beforeGetData");var b=this._.data;"string"!=typeof b&&(b=(b=this.element)&&this.elementMode==CKEDITOR.ELEMENT_MODE_REPLACE?b.is("textarea")?b.getValue():b.getHtml():"");b={dataValue:b};!a&&this.fire("getData",b);return b.dataValue},getSnapshot:function(){var a=this.fire("getSnapshot");
"string"!=typeof a&&(a=(a=this.element)&&this.elementMode==CKEDITOR.ELEMENT_MODE_REPLACE?a.is("textarea")?a.getValue():a.getHtml():"");return a},loadSnapshot:function(a){this.fire("loadSnapshot",a)},setData:function(a,b,c){var f=!0,d=b;b&&"object"==typeof b&&(c=b.internal,d=b.callback,f=!b.noSnapshot);!c&&f&&this.fire("saveSnapshot");if(d||!c)this.once("dataReady",function(a){!c&&f&&this.fire("saveSnapshot");d&&d.call(a.editor)});a={dataValue:a};!c&&this.fire("setData",a);this._.data=a.dataValue;
!c&&this.fire("afterSetData",a)},setReadOnly:function(a){a=null==a||a;this.readOnly!=a&&(this.readOnly=a,this.keystrokeHandler.blockedKeystrokes[8]=+a,this.editable().setReadOnly(a),this.fire("readOnly"))},insertHtml:function(a,b,c){this.fire("insertHtml",{dataValue:a,mode:b,range:c})},insertText:function(a){this.fire("insertText",a)},insertElement:function(a){this.fire("insertElement",a)},getSelectedHtml:function(a){var b=this.editable(),c=this.getSelection(),c=c&&c.getRanges();if(!b||!c||0===c.length)return null;
for(var f=new CKEDITOR.dom.documentFragment,d,g,e,k=0;k<c.length;k++){var h=c[k],p=h.startContainer;p.getName&&"tr"==p.getName()?(d||(d=p.getAscendant("table").clone(),d.append(p.getAscendant("tbody").clone()),f.append(d),d=d.findOne("tbody")),g&&g.equals(p)||(g=p,e=p.clone(),d.append(e)),e.append(h.cloneContents())):f.append(h.cloneContents())}b=d?f:b.getHtmlFromRange(c[0]);return a?b.getHtml():b},extractSelectedHtml:function(a,b){var c=this.editable(),f=this.getSelection().getRanges();if(!c||0===
f.length)return null;f=f[0];c=c.extractHtmlFromRange(f,b);b||this.getSelection().selectRanges([f]);return a?c.getHtml():c},focus:function(){this.fire("beforeFocus")},checkDirty:function(){return"ready"==this.status&&this._.previousValue!==this.getSnapshot()},resetDirty:function(){this._.previousValue=this.getSnapshot()},updateElement:function(){return B.call(this)},setKeystroke:function(){for(var a=this.keystrokeHandler.keystrokes,b=CKEDITOR.tools.isArray(arguments[0])?arguments[0]:[[].slice.call(arguments,
0)],c,f,d=b.length;d--;)c=b[d],f=0,CKEDITOR.tools.isArray(c)&&(f=c[1],c=c[0]),f?a[c]=f:delete a[c]},getCommandKeystroke:function(a){var b=a.name,c=this.keystrokeHandler.keystrokes,f;if(a.fakeKeystroke)return a.fakeKeystroke;for(f in c)if(c.hasOwnProperty(f)&&c[f]==b)return f;return null},addFeature:function(a){return this.filter.addFeature(a)},setActiveFilter:function(a){a||(a=this.filter);this.activeFilter!==a&&(this.activeFilter=a,this.fire("activeFilterChange"),a===this.filter?this.setActiveEnterMode(null,
null):this.setActiveEnterMode(a.getAllowedEnterMode(this.enterMode),a.getAllowedEnterMode(this.shiftEnterMode,!0)))},setActiveEnterMode:function(a,b){a=a?this.blockless?CKEDITOR.ENTER_BR:a:this.enterMode;b=b?this.blockless?CKEDITOR.ENTER_BR:b:this.shiftEnterMode;if(this.activeEnterMode!=a||this.activeShiftEnterMode!=b)this.activeEnterMode=a,this.activeShiftEnterMode=b,this.fire("activeEnterModeChange")},showNotification:function(a){alert(a)}})}(),CKEDITOR.ELEMENT_MODE_NONE=0,CKEDITOR.ELEMENT_MODE_REPLACE=
1,CKEDITOR.ELEMENT_MODE_APPENDTO=2,CKEDITOR.ELEMENT_MODE_INLINE=3,CKEDITOR.htmlParser=function(){this._={htmlPartsRegex:/<(?:(?:\/([^>]+)>)|(?:!--([\S|\s]*?)--\x3e)|(?:([^\/\s>]+)((?:\s+[\w\-:.]+(?:\s*=\s*?(?:(?:"[^"]*")|(?:'[^']*')|[^\s"'\/>]+))?)*)[\S\s]*?(\/?)>))/g}},function(){var a=/([\w\-:.]+)(?:(?:\s*=\s*(?:(?:"([^"]*)")|(?:'([^']*)')|([^\s>]+)))|(?=\s|$))/g,e={checked:1,compact:1,declare:1,defer:1,disabled:1,ismap:1,multiple:1,nohref:1,noresize:1,noshade:1,nowrap:1,readonly:1,selected:1};
CKEDITOR.htmlParser.prototype={onTagOpen:function(){},onTagClose:function(){},onText:function(){},onCDATA:function(){},onComment:function(){},parse:function(d){for(var g,l,k=0,m;g=this._.htmlPartsRegex.exec(d);){l=g.index;if(l>k)if(k=d.substring(k,l),m)m.push(k);else this.onText(k);k=this._.htmlPartsRegex.lastIndex;if(l=g[1])if(l=l.toLowerCase(),m&&CKEDITOR.dtd.$cdata[l]&&(this.onCDATA(m.join("")),m=null),!m){this.onTagClose(l);continue}if(m)m.push(g[0]);else if(l=g[3]){if(l=l.toLowerCase(),!/="/.test(l)){var h=
{},b,c=g[4];g=!!g[5];if(c)for(;b=a.exec(c);){var f=b[1].toLowerCase();b=b[2]||b[3]||b[4]||"";h[f]=!b&&e[f]?f:CKEDITOR.tools.htmlDecodeAttr(b)}this.onTagOpen(l,h,g);!m&&CKEDITOR.dtd.$cdata[l]&&(m=[])}}else if(l=g[2])this.onComment(l)}if(d.length>k)this.onText(d.substring(k,d.length))}}}(),CKEDITOR.htmlParser.basicWriter=CKEDITOR.tools.createClass({$:function(){this._={output:[]}},proto:{openTag:function(a){this._.output.push("\x3c",a)},openTagClose:function(a,e){e?this._.output.push(" /\x3e"):this._.output.push("\x3e")},
attribute:function(a,e){"string"==typeof e&&(e=CKEDITOR.tools.htmlEncodeAttr(e));this._.output.push(" ",a,'\x3d"',e,'"')},closeTag:function(a){this._.output.push("\x3c/",a,"\x3e")},text:function(a){this._.output.push(a)},comment:function(a){this._.output.push("\x3c!--",a,"--\x3e")},write:function(a){this._.output.push(a)},reset:function(){this._.output=[];this._.indent=!1},getHtml:function(a){var e=this._.output.join("");a&&this.reset();return e}}}),"use strict",function(){CKEDITOR.htmlParser.node=
function(){};CKEDITOR.htmlParser.node.prototype={remove:function(){var a=this.parent.children,e=CKEDITOR.tools.indexOf(a,this),d=this.previous,g=this.next;d&&(d.next=g);g&&(g.previous=d);a.splice(e,1);this.parent=null},replaceWith:function(a){var e=this.parent.children,d=CKEDITOR.tools.indexOf(e,this),g=a.previous=this.previous,l=a.next=this.next;g&&(g.next=a);l&&(l.previous=a);e[d]=a;a.parent=this.parent;this.parent=null},insertAfter:function(a){var e=a.parent.children,d=CKEDITOR.tools.indexOf(e,
a),g=a.next;e.splice(d+1,0,this);this.next=a.next;this.previous=a;a.next=this;g&&(g.previous=this);this.parent=a.parent},insertBefore:function(a){var e=a.parent.children,d=CKEDITOR.tools.indexOf(e,a);e.splice(d,0,this);this.next=a;(this.previous=a.previous)&&(a.previous.next=this);a.previous=this;this.parent=a.parent},getAscendant:function(a){var e="function"==typeof a?a:"string"==typeof a?function(d){return d.name==a}:function(d){return d.name in a},d=this.parent;for(;d&&d.type==CKEDITOR.NODE_ELEMENT;){if(e(d))return d;
d=d.parent}return null},wrapWith:function(a){this.replaceWith(a);a.add(this);return a},getIndex:function(){return CKEDITOR.tools.indexOf(this.parent.children,this)},getFilterContext:function(a){return a||{}}}}(),"use strict",CKEDITOR.htmlParser.comment=function(a){this.value=a;this._={isBlockLike:!1}},CKEDITOR.htmlParser.comment.prototype=CKEDITOR.tools.extend(new CKEDITOR.htmlParser.node,{type:CKEDITOR.NODE_COMMENT,filter:function(a,e){var d=this.value;if(!(d=a.onComment(e,d,this)))return this.remove(),
!1;if("string"!=typeof d)return this.replaceWith(d),!1;this.value=d;return!0},writeHtml:function(a,e){e&&this.filter(e);a.comment(this.value)}}),"use strict",function(){CKEDITOR.htmlParser.text=function(a){this.value=a;this._={isBlockLike:!1}};CKEDITOR.htmlParser.text.prototype=CKEDITOR.tools.extend(new CKEDITOR.htmlParser.node,{type:CKEDITOR.NODE_TEXT,filter:function(a,e){if(!(this.value=a.onText(e,this.value,this)))return this.remove(),!1},writeHtml:function(a,e){e&&this.filter(e);a.text(this.value)}})}(),
"use strict",function(){CKEDITOR.htmlParser.cdata=function(a){this.value=a};CKEDITOR.htmlParser.cdata.prototype=CKEDITOR.tools.extend(new CKEDITOR.htmlParser.node,{type:CKEDITOR.NODE_TEXT,filter:function(){},writeHtml:function(a){a.write(this.value)}})}(),"use strict",CKEDITOR.htmlParser.fragment=function(){this.children=[];this.parent=null;this._={isBlockLike:!0,hasInlineStarted:!1}},function(){function a(a){return a.attributes["data-cke-survive"]?!1:"a"==a.name&&a.attributes.href||CKEDITOR.dtd.$removeEmpty[a.name]}
var e=CKEDITOR.tools.extend({table:1,ul:1,ol:1,dl:1},CKEDITOR.dtd.table,CKEDITOR.dtd.ul,CKEDITOR.dtd.ol,CKEDITOR.dtd.dl),d={ol:1,ul:1},g=CKEDITOR.tools.extend({},{html:1},CKEDITOR.dtd.html,CKEDITOR.dtd.body,CKEDITOR.dtd.head,{style:1,script:1}),l={ul:"li",ol:"li",dl:"dd",table:"tbody",tbody:"tr",thead:"tr",tfoot:"tr",tr:"td"};CKEDITOR.htmlParser.fragment.fromHtml=function(k,m,h){function b(a){var b;if(0<y.length)for(var f=0;f<y.length;f++){var d=y[f],g=d.name,e=CKEDITOR.dtd[g],n=w.name&&CKEDITOR.dtd[w.name];
n&&!n[g]||a&&e&&!e[a]&&CKEDITOR.dtd[a]?g==w.name&&(p(w,w.parent,1),f--):(b||(c(),b=1),d=d.clone(),d.parent=w,w=d,y.splice(f,1),f--)}}function c(){for(;H.length;)p(H.shift(),w)}function f(a){if(a._.isBlockLike&&"pre"!=a.name&&"textarea"!=a.name){var b=a.children.length,c=a.children[b-1],f;c&&c.type==CKEDITOR.NODE_TEXT&&((f=CKEDITOR.tools.rtrim(c.value))?c.value=f:a.children.length=b-1)}}function p(b,c,d){c=c||w||u;var g=w;void 0===b.previous&&(B(c,b)&&(w=c,t.onTagOpen(h,{}),b.returnPoint=c=w),f(b),
a(b)&&!b.children.length||c.add(b),"pre"==b.name&&(n=!1),"textarea"==b.name&&(F=!1));b.returnPoint?(w=b.returnPoint,delete b.returnPoint):w=d?c:g}function B(a,b){if((a==u||"body"==a.name)&&h&&(!a.name||CKEDITOR.dtd[a.name][h])){var c,f;return(c=b.attributes&&(f=b.attributes["data-cke-real-element-type"])?f:b.name)&&c in CKEDITOR.dtd.$inline&&!(c in CKEDITOR.dtd.head)&&!b.isOrphan||b.type==CKEDITOR.NODE_TEXT}}function x(a,b){return a in CKEDITOR.dtd.$listItem||a in CKEDITOR.dtd.$tableContent?a==b||
"dt"==a&&"dd"==b||"dd"==a&&"dt"==b:!1}var t=new CKEDITOR.htmlParser,u=m instanceof CKEDITOR.htmlParser.element?m:"string"==typeof m?new CKEDITOR.htmlParser.element(m):new CKEDITOR.htmlParser.fragment,y=[],H=[],w=u,F="textarea"==u.name,n="pre"==u.name;t.onTagOpen=function(f,k,h,l){k=new CKEDITOR.htmlParser.element(f,k);k.isUnknown&&h&&(k.isEmpty=!0);k.isOptionalClose=l;if(a(k))y.push(k);else{if("pre"==f)n=!0;else{if("br"==f&&n){w.add(new CKEDITOR.htmlParser.text("\n"));return}"textarea"==f&&(F=!0)}if("br"==
f)H.push(k);else{for(;!(l=(h=w.name)?CKEDITOR.dtd[h]||(w._.isBlockLike?CKEDITOR.dtd.div:CKEDITOR.dtd.span):g,k.isUnknown||w.isUnknown||l[f]);)if(w.isOptionalClose)t.onTagClose(h);else if(f in d&&h in d)h=w.children,(h=h[h.length-1])&&"li"==h.name||p(h=new CKEDITOR.htmlParser.element("li"),w),!k.returnPoint&&(k.returnPoint=w),w=h;else if(f in CKEDITOR.dtd.$listItem&&!x(f,h))t.onTagOpen("li"==f?"ul":"dl",{},0,1);else if(h in e&&!x(f,h))!k.returnPoint&&(k.returnPoint=w),w=w.parent;else if(h in CKEDITOR.dtd.$inline&&
y.unshift(w),w.parent)p(w,w.parent,1);else{k.isOrphan=1;break}b(f);c();k.parent=w;k.isEmpty?p(k):w=k}}};t.onTagClose=function(a){for(var b=y.length-1;0<=b;b--)if(a==y[b].name){y.splice(b,1);return}for(var f=[],d=[],g=w;g!=u&&g.name!=a;)g._.isBlockLike||d.unshift(g),f.push(g),g=g.returnPoint||g.parent;if(g!=u){for(b=0;b<f.length;b++){var e=f[b];p(e,e.parent)}w=g;g._.isBlockLike&&c();p(g,g.parent);g==w&&(w=w.parent);y=y.concat(d)}"body"==a&&(h=!1)};t.onText=function(a){if(!(w._.hasInlineStarted&&!H.length||
n||F)&&(a=CKEDITOR.tools.ltrim(a),0===a.length))return;var f=w.name,d=f?CKEDITOR.dtd[f]||(w._.isBlockLike?CKEDITOR.dtd.div:CKEDITOR.dtd.span):g;if(!F&&!d["#"]&&f in e)t.onTagOpen(l[f]||""),t.onText(a);else{c();b();n||F||(a=a.replace(/[\t\r\n ]{2,}|[\t\r\n]/g," "));a=new CKEDITOR.htmlParser.text(a);if(B(w,a))this.onTagOpen(h,{},0,1);w.add(a)}};t.onCDATA=function(a){w.add(new CKEDITOR.htmlParser.cdata(a))};t.onComment=function(a){c();b();w.add(new CKEDITOR.htmlParser.comment(a))};t.parse(k);for(c();w!=
u;)p(w,w.parent,1);f(u);return u};CKEDITOR.htmlParser.fragment.prototype={type:CKEDITOR.NODE_DOCUMENT_FRAGMENT,add:function(a,d){isNaN(d)&&(d=this.children.length);var g=0<d?this.children[d-1]:null;if(g){if(a._.isBlockLike&&g.type==CKEDITOR.NODE_TEXT&&(g.value=CKEDITOR.tools.rtrim(g.value),0===g.value.length)){this.children.pop();this.add(a);return}g.next=a}a.previous=g;a.parent=this;this.children.splice(d,0,a);this._.hasInlineStarted||(this._.hasInlineStarted=a.type==CKEDITOR.NODE_TEXT||a.type==
CKEDITOR.NODE_ELEMENT&&!a._.isBlockLike)},filter:function(a,d){d=this.getFilterContext(d);a.onRoot(d,this);this.filterChildren(a,!1,d)},filterChildren:function(a,d,g){if(this.childrenFilteredBy!=a.id){g=this.getFilterContext(g);if(d&&!this.parent)a.onRoot(g,this);this.childrenFilteredBy=a.id;for(d=0;d<this.children.length;d++)!1===this.children[d].filter(a,g)&&d--}},writeHtml:function(a,d){d&&this.filter(d);this.writeChildrenHtml(a)},writeChildrenHtml:function(a,d,g){var b=this.getFilterContext();
if(g&&!this.parent&&d)d.onRoot(b,this);d&&this.filterChildren(d,!1,b);d=0;g=this.children;for(b=g.length;d<b;d++)g[d].writeHtml(a)},forEach:function(a,d,g){if(!(g||d&&this.type!=d))var b=a(this);if(!1!==b){g=this.children;for(var c=0;c<g.length;c++)b=g[c],b.type==CKEDITOR.NODE_ELEMENT?b.forEach(a,d):d&&b.type!=d||a(b)}},getFilterContext:function(a){return a||{}}}}(),"use strict",function(){function a(){this.rules=[]}function e(d,g,e,k){var m,h;for(m in g)(h=d[m])||(h=d[m]=new a),h.add(g[m],e,k)}CKEDITOR.htmlParser.filter=
CKEDITOR.tools.createClass({$:function(d){this.id=CKEDITOR.tools.getNextNumber();this.elementNameRules=new a;this.attributeNameRules=new a;this.elementsRules={};this.attributesRules={};this.textRules=new a;this.commentRules=new a;this.rootRules=new a;d&&this.addRules(d,10)},proto:{addRules:function(a,g){var l;"number"==typeof g?l=g:g&&"priority"in g&&(l=g.priority);"number"!=typeof l&&(l=10);"object"!=typeof g&&(g={});a.elementNames&&this.elementNameRules.addMany(a.elementNames,l,g);a.attributeNames&&
this.attributeNameRules.addMany(a.attributeNames,l,g);a.elements&&e(this.elementsRules,a.elements,l,g);a.attributes&&e(this.attributesRules,a.attributes,l,g);a.text&&this.textRules.add(a.text,l,g);a.comment&&this.commentRules.add(a.comment,l,g);a.root&&this.rootRules.add(a.root,l,g)},applyTo:function(a){a.filter(this)},onElementName:function(a,g){return this.elementNameRules.execOnName(a,g)},onAttributeName:function(a,g){return this.attributeNameRules.execOnName(a,g)},onText:function(a,g,e){return this.textRules.exec(a,
g,e)},onComment:function(a,g,e){return this.commentRules.exec(a,g,e)},onRoot:function(a,g){return this.rootRules.exec(a,g)},onElement:function(a,g){for(var e=[this.elementsRules["^"],this.elementsRules[g.name],this.elementsRules.$],k,m=0;3>m;m++)if(k=e[m]){k=k.exec(a,g,this);if(!1===k)return null;if(k&&k!=g)return this.onNode(a,k);if(g.parent&&!g.name)break}return g},onNode:function(a,g){var e=g.type;return e==CKEDITOR.NODE_ELEMENT?this.onElement(a,g):e==CKEDITOR.NODE_TEXT?new CKEDITOR.htmlParser.text(this.onText(a,
g.value)):e==CKEDITOR.NODE_COMMENT?new CKEDITOR.htmlParser.comment(this.onComment(a,g.value)):null},onAttribute:function(a,g,e,k){return(e=this.attributesRules[e])?e.exec(a,k,g,this):k}}});CKEDITOR.htmlParser.filterRulesGroup=a;a.prototype={add:function(a,g,e){this.rules.splice(this.findIndex(g),0,{value:a,priority:g,options:e})},addMany:function(a,g,e){for(var k=[this.findIndex(g),0],m=0,h=a.length;m<h;m++)k.push({value:a[m],priority:g,options:e});this.rules.splice.apply(this.rules,k)},findIndex:function(a){for(var g=
this.rules,e=g.length-1;0<=e&&a<g[e].priority;)e--;return e+1},exec:function(a,g){var e=g instanceof CKEDITOR.htmlParser.node||g instanceof CKEDITOR.htmlParser.fragment,k=Array.prototype.slice.call(arguments,1),m=this.rules,h=m.length,b,c,f,p;for(p=0;p<h;p++)if(e&&(b=g.type,c=g.name),f=m[p],!(a.nonEditable&&!f.options.applyToAll||a.nestedEditable&&f.options.excludeNestedEditable)){f=f.value.apply(null,k);if(!1===f||e&&f&&(f.name!=c||f.type!=b))return f;null!=f&&(k[0]=g=f)}return g},execOnName:function(a,
g){for(var e=0,k=this.rules,m=k.length,h;g&&e<m;e++)h=k[e],a.nonEditable&&!h.options.applyToAll||a.nestedEditable&&h.options.excludeNestedEditable||(g=g.replace(h.value[0],h.value[1]));return g}}}(),function(){function a(a,b){function c(a){return a||CKEDITOR.env.needsNbspFiller?new CKEDITOR.htmlParser.text(" "):new CKEDITOR.htmlParser.element("br",{"data-cke-bogus":1})}function f(a,b){return function(f){if(f.type!=CKEDITOR.NODE_DOCUMENT_FRAGMENT){var n=[],q=d(f),E,G;if(q)for(e(q,1)&&n.push(q);q;)k(q)&&
(E=g(q))&&e(E)&&((G=g(E))&&!k(G)?n.push(E):(c(v).insertAfter(E),E.remove())),q=q.previous;for(q=0;q<n.length;q++)n[q].remove();if(n=!a||!1!==("function"==typeof b?b(f):b))v||CKEDITOR.env.needsBrFiller||f.type!=CKEDITOR.NODE_DOCUMENT_FRAGMENT?v||CKEDITOR.env.needsBrFiller||!(7<document.documentMode||f.name in CKEDITOR.dtd.tr||f.name in CKEDITOR.dtd.$listItem)?(n=d(f),n=!n||"form"==f.name&&"input"==n.name):n=!1:n=!1;n&&f.add(c(a))}}}function e(a,b){if((!v||CKEDITOR.env.needsBrFiller)&&a.type==CKEDITOR.NODE_ELEMENT&&
"br"==a.name&&!a.attributes["data-cke-eol"])return!0;var c;return a.type==CKEDITOR.NODE_TEXT&&(c=a.value.match(y))&&(c.index&&((new CKEDITOR.htmlParser.text(a.value.substring(0,c.index))).insertBefore(a),a.value=c[0]),!CKEDITOR.env.needsBrFiller&&v&&(!b||a.parent.name in r)||!v&&((c=a.previous)&&"br"==c.name||!c||k(c)))?!0:!1}var q={elements:{}},v="html"==b,r=CKEDITOR.tools.extend({},n),E;for(E in r)"#"in w[E]||delete r[E];for(E in r)q.elements[E]=f(v,a.config.fillEmptyBlocks);q.root=f(v,!1);q.elements.br=
function(a){return function(b){if(b.parent.type!=CKEDITOR.NODE_DOCUMENT_FRAGMENT){var f=b.attributes;if("data-cke-bogus"in f||"data-cke-eol"in f)delete f["data-cke-bogus"];else{for(f=b.next;f&&l(f);)f=f.next;var d=g(b);!f&&k(b.parent)?m(b.parent,c(a)):k(f)&&d&&!k(d)&&c(a).insertBefore(f)}}}}(v);return q}function e(a,b){return a!=CKEDITOR.ENTER_BR&&!1!==b?a==CKEDITOR.ENTER_DIV?"div":"p":!1}function d(a){for(a=a.children[a.children.length-1];a&&l(a);)a=a.previous;return a}function g(a){for(a=a.previous;a&&
l(a);)a=a.previous;return a}function l(a){return a.type==CKEDITOR.NODE_TEXT&&!CKEDITOR.tools.trim(a.value)||a.type==CKEDITOR.NODE_ELEMENT&&a.attributes["data-cke-bookmark"]}function k(a){return a&&(a.type==CKEDITOR.NODE_ELEMENT&&a.name in n||a.type==CKEDITOR.NODE_DOCUMENT_FRAGMENT)}function m(a,b){var c=a.children[a.children.length-1];a.children.push(b);b.parent=a;c&&(c.next=b,b.previous=c)}function h(a){a=a.attributes;"false"!=a.contenteditable&&(a["data-cke-editable"]=a.contenteditable?"true":1);
a.contenteditable="false"}function b(a){a=a.attributes;switch(a["data-cke-editable"]){case "true":a.contenteditable="true";break;case "1":delete a.contenteditable}}function c(a){return a.replace(K,function(a,b,c){return"\x3c"+b+c.replace(J,function(a,b){return P.test(b)&&-1==c.indexOf("data-cke-saved-"+b)?" data-cke-saved-"+a+" data-cke-"+CKEDITOR.rnd+"-"+a:a})+"\x3e"})}function f(a,b){return a.replace(b,function(a,b,c){0===a.indexOf("\x3ctextarea")&&(a=b+x(c).replace(/</g,"\x26lt;").replace(/>/g,
"\x26gt;")+"\x3c/textarea\x3e");return"\x3ccke:encoded\x3e"+encodeURIComponent(a)+"\x3c/cke:encoded\x3e"})}function p(a){return a.replace(S,function(a,b){return decodeURIComponent(b)})}function B(a){return a.replace(/\x3c!--(?!{cke_protected})[\s\S]+?--\x3e/g,function(a){return"\x3c!--"+H+"{C}"+encodeURIComponent(a).replace(/--/g,"%2D%2D")+"--\x3e"})}function x(a){return a.replace(/\x3c!--\{cke_protected\}\{C\}([\s\S]+?)--\x3e/g,function(a,b){return decodeURIComponent(b)})}function t(a,b){var c=b._.dataStore;
return a.replace(/\x3c!--\{cke_protected\}([\s\S]+?)--\x3e/g,function(a,b){return decodeURIComponent(b)}).replace(/\{cke_protected_(\d+)\}/g,function(a,b){return c&&c[b]||""})}function u(a,b){var c=[],f=b.config.protectedSource,d=b._.dataStore||(b._.dataStore={id:1}),g=/<\!--\{cke_temp(comment)?\}(\d*?)--\x3e/g,f=[/<script[\s\S]*?(<\/script>|$)/gi,/<noscript[\s\S]*?<\/noscript>/gi,/<meta[\s\S]*?\/?>/gi].concat(f);a=a.replace(/\x3c!--[\s\S]*?--\x3e/g,function(a){return"\x3c!--{cke_tempcomment}"+(c.push(a)-
1)+"--\x3e"});for(var e=0;e<f.length;e++)a=a.replace(f[e],function(a){a=a.replace(g,function(a,b,f){return c[f]});return/cke_temp(comment)?/.test(a)?a:"\x3c!--{cke_temp}"+(c.push(a)-1)+"--\x3e"});a=a.replace(g,function(a,b,f){return"\x3c!--"+H+(b?"{C}":"")+encodeURIComponent(c[f]).replace(/--/g,"%2D%2D")+"--\x3e"});a=a.replace(/<\w+(?:\s+(?:(?:[^\s=>]+\s*=\s*(?:[^'"\s>]+|'[^']*'|"[^"]*"))|[^\s=\/>]+))+\s*\/?>/g,function(a){return a.replace(/\x3c!--\{cke_protected\}([^>]*)--\x3e/g,function(a,b){d[d.id]=
decodeURIComponent(b);return"{cke_protected_"+d.id++ +"}"})});return a=a.replace(/<(title|iframe|textarea)([^>]*)>([\s\S]*?)<\/\1>/g,function(a,c,f,d){return"\x3c"+c+f+"\x3e"+t(x(d),b)+"\x3c/"+c+"\x3e"})}CKEDITOR.htmlDataProcessor=function(b){var d,g,n=this;this.editor=b;this.dataFilter=d=new CKEDITOR.htmlParser.filter;this.htmlFilter=g=new CKEDITOR.htmlParser.filter;this.writer=new CKEDITOR.htmlParser.basicWriter;d.addRules(r);d.addRules(C,{applyToAll:!0});d.addRules(a(b,"data"),{applyToAll:!0});
g.addRules(D);g.addRules(z,{applyToAll:!0});g.addRules(a(b,"html"),{applyToAll:!0});b.on("toHtml",function(a){a=a.data;var d=a.dataValue,g,d=u(d,b),d=f(d,O),d=c(d),d=f(d,L),d=d.replace(v,"$1cke:$2"),d=d.replace(N,"\x3ccke:$1$2\x3e\x3c/cke:$1\x3e"),d=d.replace(/(<pre\b[^>]*>)(\r\n|\n)/g,"$1$2$2"),d=d.replace(/([^a-z0-9<\-])(on\w{3,})(?!>)/gi,"$1data-cke-"+CKEDITOR.rnd+"-$2");g=a.context||b.editable().getName();var n;CKEDITOR.env.ie&&9>CKEDITOR.env.version&&"pre"==g&&(g="div",d="\x3cpre\x3e"+d+"\x3c/pre\x3e",
n=1);g=b.document.createElement(g);g.setHtml("a"+d);d=g.getHtml().substr(1);d=d.replace(new RegExp("data-cke-"+CKEDITOR.rnd+"-","ig"),"");n&&(d=d.replace(/^<pre>|<\/pre>$/gi,""));d=d.replace(q,"$1$2");d=p(d);d=x(d);g=!1===a.fixForBody?!1:e(a.enterMode,b.config.autoParagraph);d=CKEDITOR.htmlParser.fragment.fromHtml(d,a.context,g);g&&(n=d,!n.children.length&&CKEDITOR.dtd[n.name][g]&&(g=new CKEDITOR.htmlParser.element(g),n.add(g)));a.dataValue=d},null,null,5);b.on("toHtml",function(a){a.data.filter.applyTo(a.data.dataValue,
!0,a.data.dontFilter,a.data.enterMode)&&b.fire("dataFiltered")},null,null,6);b.on("toHtml",function(a){a.data.dataValue.filterChildren(n.dataFilter,!0)},null,null,10);b.on("toHtml",function(a){a=a.data;var b=a.dataValue,c=new CKEDITOR.htmlParser.basicWriter;b.writeChildrenHtml(c);b=c.getHtml(!0);a.dataValue=B(b)},null,null,15);b.on("toDataFormat",function(a){var c=a.data.dataValue;a.data.enterMode!=CKEDITOR.ENTER_BR&&(c=c.replace(/^<br *\/?>/i,""));a.data.dataValue=CKEDITOR.htmlParser.fragment.fromHtml(c,
a.data.context,e(a.data.enterMode,b.config.autoParagraph))},null,null,5);b.on("toDataFormat",function(a){a.data.dataValue.filterChildren(n.htmlFilter,!0)},null,null,10);b.on("toDataFormat",function(a){a.data.filter.applyTo(a.data.dataValue,!1,!0)},null,null,11);b.on("toDataFormat",function(a){var c=a.data.dataValue,f=n.writer;f.reset();c.writeChildrenHtml(f);c=f.getHtml(!0);c=x(c);c=t(c,b);a.data.dataValue=c},null,null,15)};CKEDITOR.htmlDataProcessor.prototype={toHtml:function(a,b,c,f){var d=this.editor,
g,e,n,q;b&&"object"==typeof b?(g=b.context,c=b.fixForBody,f=b.dontFilter,e=b.filter,n=b.enterMode,q=b.protectedWhitespaces):g=b;g||null===g||(g=d.editable().getName());return d.fire("toHtml",{dataValue:a,context:g,fixForBody:c,dontFilter:f,filter:e||d.filter,enterMode:n||d.enterMode,protectedWhitespaces:q}).dataValue},toDataFormat:function(a,b){var c,f,d;b&&(c=b.context,f=b.filter,d=b.enterMode);c||null===c||(c=this.editor.editable().getName());return this.editor.fire("toDataFormat",{dataValue:a,
filter:f||this.editor.filter,context:c,enterMode:d||this.editor.enterMode}).dataValue}};var y=/(?:&nbsp;|\xa0)$/,H="{cke_protected}",w=CKEDITOR.dtd,F="caption colgroup col thead tfoot tbody".split(" "),n=CKEDITOR.tools.extend({},w.$blockLimit,w.$block),r={elements:{input:h,textarea:h}},C={attributeNames:[[/^on/,"data-cke-pa-on"],[/^data-cke-expando$/,""]]},D={elements:{embed:function(a){var b=a.parent;if(b&&"object"==b.name){var c=b.attributes.width,b=b.attributes.height;c&&(a.attributes.width=c);
b&&(a.attributes.height=b)}},a:function(a){var b=a.attributes;if(!(a.children.length||b.name||b.id||a.attributes["data-cke-saved-name"]))return!1}}},z={elementNames:[[/^cke:/,""],[/^\?xml:namespace$/,""]],attributeNames:[[/^data-cke-(saved|pa)-/,""],[/^data-cke-.*/,""],["hidefocus",""]],elements:{$:function(a){var b=a.attributes;if(b){if(b["data-cke-temp"])return!1;for(var c=["name","href","src"],f,d=0;d<c.length;d++)f="data-cke-saved-"+c[d],f in b&&delete b[c[d]]}return a},table:function(a){a.children.slice(0).sort(function(a,
b){var c,f;a.type==CKEDITOR.NODE_ELEMENT&&b.type==a.type&&(c=CKEDITOR.tools.indexOf(F,a.name),f=CKEDITOR.tools.indexOf(F,b.name));-1<c&&-1<f&&c!=f||(c=a.parent?a.getIndex():-1,f=b.parent?b.getIndex():-1);return c>f?1:-1})},param:function(a){a.children=[];a.isEmpty=!0;return a},span:function(a){"Apple-style-span"==a.attributes["class"]&&delete a.name},html:function(a){delete a.attributes.contenteditable;delete a.attributes["class"]},body:function(a){delete a.attributes.spellcheck;delete a.attributes.contenteditable},
style:function(a){var b=a.children[0];b&&b.value&&(b.value=CKEDITOR.tools.trim(b.value));a.attributes.type||(a.attributes.type="text/css")},title:function(a){var b=a.children[0];!b&&m(a,b=new CKEDITOR.htmlParser.text);b.value=a.attributes["data-cke-title"]||""},input:b,textarea:b},attributes:{"class":function(a){return CKEDITOR.tools.ltrim(a.replace(/(?:^|\s+)cke_[^\s]*/g,""))||!1}}};CKEDITOR.env.ie&&(z.attributes.style=function(a){return a.replace(/(^|;)([^\:]+)/g,function(a){return a.toLowerCase()})});
var K=/<(a|area|img|input|source)\b([^>]*)>/gi,J=/([\w-:]+)\s*=\s*(?:(?:"[^"]*")|(?:'[^']*')|(?:[^ "'>]+))/gi,P=/^(href|src|name)$/i,L=/(?:<style(?=[ >])[^>]*>[\s\S]*?<\/style>)|(?:<(:?link|meta|base)[^>]*>)/gi,O=/(<textarea(?=[ >])[^>]*>)([\s\S]*?)(?:<\/textarea>)/gi,S=/<cke:encoded>([^<]*)<\/cke:encoded>/gi,v=/(<\/?)((?:object|embed|param|html|body|head|title)[^>]*>)/gi,q=/(<\/?)cke:((?:html|body|head|title)[^>]*>)/gi,N=/<cke:(param|embed)([^>]*?)\/?>(?!\s*<\/cke:\1)/gi}(),"use strict",CKEDITOR.htmlParser.element=
function(a,e){this.name=a;this.attributes=e||{};this.children=[];var d=a||"",g=d.match(/^cke:(.*)/);g&&(d=g[1]);d=!!(CKEDITOR.dtd.$nonBodyContent[d]||CKEDITOR.dtd.$block[d]||CKEDITOR.dtd.$listItem[d]||CKEDITOR.dtd.$tableContent[d]||CKEDITOR.dtd.$nonEditable[d]||"br"==d);this.isEmpty=!!CKEDITOR.dtd.$empty[a];this.isUnknown=!CKEDITOR.dtd[a];this._={isBlockLike:d,hasInlineStarted:this.isEmpty||!d}},CKEDITOR.htmlParser.cssStyle=function(a){var e={};((a instanceof CKEDITOR.htmlParser.element?a.attributes.style:
a)||"").replace(/&quot;/g,'"').replace(/\s*([^ :;]+)\s*:\s*([^;]+)\s*(?=;|$)/g,function(a,g,l){"font-family"==g&&(l=l.replace(/["']/g,""));e[g.toLowerCase()]=l});return{rules:e,populate:function(a){var g=this.toString();g&&(a instanceof CKEDITOR.dom.element?a.setAttribute("style",g):a instanceof CKEDITOR.htmlParser.element?a.attributes.style=g:a.style=g)},toString:function(){var a=[],g;for(g in e)e[g]&&a.push(g,":",e[g],";");return a.join("")}}},function(){function a(a){return function(d){return d.type==
CKEDITOR.NODE_ELEMENT&&("string"==typeof a?d.name==a:d.name in a)}}var e=function(a,d){a=a[0];d=d[0];return a<d?-1:a>d?1:0},d=CKEDITOR.htmlParser.fragment.prototype;CKEDITOR.htmlParser.element.prototype=CKEDITOR.tools.extend(new CKEDITOR.htmlParser.node,{type:CKEDITOR.NODE_ELEMENT,add:d.add,clone:function(){return new CKEDITOR.htmlParser.element(this.name,this.attributes)},filter:function(a,d){var e=this,m,h;d=e.getFilterContext(d);if(d.off)return!0;if(!e.parent)a.onRoot(d,e);for(;;){m=e.name;if(!(h=
a.onElementName(d,m)))return this.remove(),!1;e.name=h;if(!(e=a.onElement(d,e)))return this.remove(),!1;if(e!==this)return this.replaceWith(e),!1;if(e.name==m)break;if(e.type!=CKEDITOR.NODE_ELEMENT)return this.replaceWith(e),!1;if(!e.name)return this.replaceWithChildren(),!1}m=e.attributes;var b,c;for(b in m){for(h=m[b];;)if(c=a.onAttributeName(d,b))if(c!=b)delete m[b],b=c;else break;else{delete m[b];break}c&&(!1===(h=a.onAttribute(d,e,c,h))?delete m[c]:m[c]=h)}e.isEmpty||this.filterChildren(a,!1,
d);return!0},filterChildren:d.filterChildren,writeHtml:function(a,d){d&&this.filter(d);var k=this.name,m=[],h=this.attributes,b,c;a.openTag(k,h);for(b in h)m.push([b,h[b]]);a.sortAttributes&&m.sort(e);b=0;for(c=m.length;b<c;b++)h=m[b],a.attribute(h[0],h[1]);a.openTagClose(k,this.isEmpty);this.writeChildrenHtml(a);this.isEmpty||a.closeTag(k)},writeChildrenHtml:d.writeChildrenHtml,replaceWithChildren:function(){for(var a=this.children,d=a.length;d;)a[--d].insertAfter(this);this.remove()},forEach:d.forEach,
getFirst:function(d){if(!d)return this.children.length?this.children[0]:null;"function"!=typeof d&&(d=a(d));for(var e=0,k=this.children.length;e<k;++e)if(d(this.children[e]))return this.children[e];return null},getHtml:function(){var a=new CKEDITOR.htmlParser.basicWriter;this.writeChildrenHtml(a);return a.getHtml()},setHtml:function(a){a=this.children=CKEDITOR.htmlParser.fragment.fromHtml(a).children;for(var d=0,e=a.length;d<e;++d)a[d].parent=this},getOuterHtml:function(){var a=new CKEDITOR.htmlParser.basicWriter;
this.writeHtml(a);return a.getHtml()},split:function(a){for(var d=this.children.splice(a,this.children.length-a),e=this.clone(),m=0;m<d.length;++m)d[m].parent=e;e.children=d;d[0]&&(d[0].previous=null);0<a&&(this.children[a-1].next=null);this.parent.add(e,this.getIndex()+1);return e},find:function(a,d){void 0===d&&(d=!1);var e=[],m;for(m=0;m<this.children.length;m++){var h=this.children[m];"function"==typeof a&&a(h)?e.push(h):"string"==typeof a&&h.name===a&&e.push(h);d&&h.find&&(e=e.concat(h.find(a,
d)))}return e},addClass:function(a){if(!this.hasClass(a)){var d=this.attributes["class"]||"";this.attributes["class"]=d+(d?" ":"")+a}},removeClass:function(a){var d=this.attributes["class"];d&&((d=CKEDITOR.tools.trim(d.replace(new RegExp("(?:\\s+|^)"+a+"(?:\\s+|$)")," ")))?this.attributes["class"]=d:delete this.attributes["class"])},hasClass:function(a){var d=this.attributes["class"];return d?(new RegExp("(?:^|\\s)"+a+"(?\x3d\\s|$)")).test(d):!1},getFilterContext:function(a){var d=[];a||(a={off:!1,
nonEditable:!1,nestedEditable:!1});a.off||"off"!=this.attributes["data-cke-processor"]||d.push("off",!0);a.nonEditable||"false"!=this.attributes.contenteditable?a.nonEditable&&!a.nestedEditable&&"true"==this.attributes.contenteditable&&d.push("nestedEditable",!0):d.push("nonEditable",!0);if(d.length){a=CKEDITOR.tools.copy(a);for(var e=0;e<d.length;e+=2)a[d[e]]=d[e+1]}return a}},!0)}(),function(){var a={},e=/{([^}]+)}/g,d=/([\\'])/g,g=/\n/g,l=/\r/g;CKEDITOR.template=function(k){if(a[k])this.output=
a[k];else{var m=k.replace(d,"\\$1").replace(g,"\\n").replace(l,"\\r").replace(e,function(a,b){return"',data['"+b+"']\x3d\x3dundefined?'{"+b+"}':data['"+b+"'],'"});this.output=a[k]=Function("data","buffer","return buffer?buffer.push('"+m+"'):['"+m+"'].join('');")}}}(),delete CKEDITOR.loadFullCore,CKEDITOR.instances={},CKEDITOR.document=new CKEDITOR.dom.document(document),CKEDITOR.add=function(a){CKEDITOR.instances[a.name]=a;a.on("focus",function(){CKEDITOR.currentInstance!=a&&(CKEDITOR.currentInstance=
a,CKEDITOR.fire("currentInstance"))});a.on("blur",function(){CKEDITOR.currentInstance==a&&(CKEDITOR.currentInstance=null,CKEDITOR.fire("currentInstance"))});CKEDITOR.fire("instance",null,a)},CKEDITOR.remove=function(a){delete CKEDITOR.instances[a.name]},function(){var a={};CKEDITOR.addTemplate=function(e,d){var g=a[e];if(g)return g;g={name:e,source:d};CKEDITOR.fire("template",g);return a[e]=new CKEDITOR.template(g.source)};CKEDITOR.getTemplate=function(e){return a[e]}}(),function(){var a=[];CKEDITOR.addCss=
function(e){a.push(e)};CKEDITOR.getCss=function(){return a.join("\n")}}(),CKEDITOR.on("instanceDestroyed",function(){CKEDITOR.tools.isEmpty(this.instances)&&CKEDITOR.fire("reset")}),CKEDITOR.TRISTATE_ON=1,CKEDITOR.TRISTATE_OFF=2,CKEDITOR.TRISTATE_DISABLED=0,function(){CKEDITOR.inline=function(a,e){if(!CKEDITOR.env.isCompatible)return null;a=CKEDITOR.dom.element.get(a);if(a.getEditor())throw'The editor instance "'+a.getEditor().name+'" is already attached to the provided element.';var d=new CKEDITOR.editor(e,
a,CKEDITOR.ELEMENT_MODE_INLINE),g=a.is("textarea")?a:null;g?(d.setData(g.getValue(),null,!0),a=CKEDITOR.dom.element.createFromHtml('\x3cdiv contenteditable\x3d"'+!!d.readOnly+'" class\x3d"cke_textarea_inline"\x3e'+g.getValue()+"\x3c/div\x3e",CKEDITOR.document),a.insertAfter(g),g.hide(),g.$.form&&d._attachToForm()):d.setData(a.getHtml(),null,!0);d.on("loaded",function(){d.fire("uiReady");d.editable(a);d.container=a;d.ui.contentsElement=a;d.setData(d.getData(1));d.resetDirty();d.fire("contentDom");
d.mode="wysiwyg";d.fire("mode");d.status="ready";d.fireOnce("instanceReady");CKEDITOR.fire("instanceReady",null,d)},null,null,1E4);d.on("destroy",function(){g&&(d.container.clearCustomData(),d.container.remove(),g.show());d.element.clearCustomData();delete d.element});return d};CKEDITOR.inlineAll=function(){var a,e,d;for(d in CKEDITOR.dtd.$editable)for(var g=CKEDITOR.document.getElementsByTag(d),l=0,k=g.count();l<k;l++)a=g.getItem(l),"true"==a.getAttribute("contenteditable")&&(e={element:a,config:{}},
!1!==CKEDITOR.fire("inline",e)&&CKEDITOR.inline(a,e.config))};CKEDITOR.domReady(function(){!CKEDITOR.disableAutoInline&&CKEDITOR.inlineAll()})}(),CKEDITOR.replaceClass="ckeditor",function(){function a(a,l,k,m){if(!CKEDITOR.env.isCompatible)return null;a=CKEDITOR.dom.element.get(a);if(a.getEditor())throw'The editor instance "'+a.getEditor().name+'" is already attached to the provided element.';var h=new CKEDITOR.editor(l,a,m);m==CKEDITOR.ELEMENT_MODE_REPLACE&&(a.setStyle("visibility","hidden"),h._.required=
a.hasAttribute("required"),a.removeAttribute("required"));k&&h.setData(k,null,!0);h.on("loaded",function(){d(h);m==CKEDITOR.ELEMENT_MODE_REPLACE&&h.config.autoUpdateElement&&a.$.form&&h._attachToForm();h.setMode(h.config.startupMode,function(){h.resetDirty();h.status="ready";h.fireOnce("instanceReady");CKEDITOR.fire("instanceReady",null,h)})});h.on("destroy",e);return h}function e(){var a=this.container,d=this.element;a&&(a.clearCustomData(),a.remove());d&&(d.clearCustomData(),this.elementMode==CKEDITOR.ELEMENT_MODE_REPLACE&&
(d.show(),this._.required&&d.setAttribute("required","required")),delete this.element)}function d(a){var d=a.name,e=a.element,m=a.elementMode,h=a.fire("uiSpace",{space:"top",html:""}).html,b=a.fire("uiSpace",{space:"bottom",html:""}).html,c=new CKEDITOR.template('\x3c{outerEl} id\x3d"cke_{name}" class\x3d"{id} cke cke_reset cke_chrome cke_editor_{name} cke_{langDir} '+CKEDITOR.env.cssClass+'"  dir\x3d"{langDir}" lang\x3d"{langCode}" role\x3d"application"'+(a.title?' aria-labelledby\x3d"cke_{name}_arialbl"':
"")+"\x3e"+(a.title?'\x3cspan id\x3d"cke_{name}_arialbl" class\x3d"cke_voice_label"\x3e{voiceLabel}\x3c/span\x3e':"")+'\x3c{outerEl} class\x3d"cke_inner cke_reset" role\x3d"presentation"\x3e{topHtml}\x3c{outerEl} id\x3d"{contentId}" class\x3d"cke_contents cke_reset" role\x3d"presentation"\x3e\x3c/{outerEl}\x3e{bottomHtml}\x3c/{outerEl}\x3e\x3c/{outerEl}\x3e'),d=CKEDITOR.dom.element.createFromHtml(c.output({id:a.id,name:d,langDir:a.lang.dir,langCode:a.langCode,voiceLabel:a.title,topHtml:h?'\x3cspan id\x3d"'+
a.ui.spaceId("top")+'" class\x3d"cke_top cke_reset_all" role\x3d"presentation" style\x3d"height:auto"\x3e'+h+"\x3c/span\x3e":"",contentId:a.ui.spaceId("contents"),bottomHtml:b?'\x3cspan id\x3d"'+a.ui.spaceId("bottom")+'" class\x3d"cke_bottom cke_reset_all" role\x3d"presentation"\x3e'+b+"\x3c/span\x3e":"",outerEl:CKEDITOR.env.ie?"span":"div"}));m==CKEDITOR.ELEMENT_MODE_REPLACE?(e.hide(),d.insertAfter(e)):e.append(d);a.container=d;a.ui.contentsElement=a.ui.space("contents");h&&a.ui.space("top").unselectable();
b&&a.ui.space("bottom").unselectable();e=a.config.width;m=a.config.height;e&&d.setStyle("width",CKEDITOR.tools.cssLength(e));m&&a.ui.space("contents").setStyle("height",CKEDITOR.tools.cssLength(m));d.disableContextMenu();CKEDITOR.env.webkit&&d.on("focus",function(){a.focus()});a.fireOnce("uiReady")}CKEDITOR.replace=function(d,e){return a(d,e,null,CKEDITOR.ELEMENT_MODE_REPLACE)};CKEDITOR.appendTo=function(d,e,k){return a(d,e,k,CKEDITOR.ELEMENT_MODE_APPENDTO)};CKEDITOR.replaceAll=function(){for(var a=
document.getElementsByTagName("textarea"),d=0;d<a.length;d++){var e=null,m=a[d];if(m.name||m.id){if("string"==typeof arguments[0]){if(!(new RegExp("(?:^|\\s)"+arguments[0]+"(?:$|\\s)")).test(m.className))continue}else if("function"==typeof arguments[0]&&(e={},!1===arguments[0](m,e)))continue;this.replace(m,e)}}};CKEDITOR.editor.prototype.addMode=function(a,d){(this._.modes||(this._.modes={}))[a]=d};CKEDITOR.editor.prototype.setMode=function(a,d){var e=this,m=this._.modes;if(a!=e.mode&&m&&m[a]){e.fire("beforeSetMode",
a);if(e.mode){var h=e.checkDirty(),m=e._.previousModeData,b,c=0;e.fire("beforeModeUnload");e.editable(0);e._.previousMode=e.mode;e._.previousModeData=b=e.getData(1);"source"==e.mode&&m==b&&(e.fire("lockSnapshot",{forceUpdate:!0}),c=1);e.ui.space("contents").setHtml("");e.mode=""}else e._.previousModeData=e.getData(1);this._.modes[a](function(){e.mode=a;void 0!==h&&!h&&e.resetDirty();c?e.fire("unlockSnapshot"):"wysiwyg"==a&&e.fire("saveSnapshot");setTimeout(function(){e.fire("mode");d&&d.call(e)},
0)})}};CKEDITOR.editor.prototype.resize=function(a,d,e,m){var h=this.container,b=this.ui.space("contents"),c=CKEDITOR.env.webkit&&this.document&&this.document.getWindow().$.frameElement;m=m?this.container.getFirst(function(a){return a.type==CKEDITOR.NODE_ELEMENT&&a.hasClass("cke_inner")}):h;m.setSize("width",a,!0);c&&(c.style.width="1%");var f=(m.$.offsetHeight||0)-(b.$.clientHeight||0),h=Math.max(d-(e?0:f),0);d=e?d+f:d;b.setStyle("height",h+"px");c&&(c.style.width="100%");this.fire("resize",{outerHeight:d,
contentsHeight:h,outerWidth:a||m.getSize("width")})};CKEDITOR.editor.prototype.getResizable=function(a){return a?this.ui.space("contents"):this.container};CKEDITOR.domReady(function(){CKEDITOR.replaceClass&&CKEDITOR.replaceAll(CKEDITOR.replaceClass)})}(),CKEDITOR.config.startupMode="wysiwyg",function(){function a(a){var b=a.editor,c=a.data.path,d=c.blockLimit,f=a.data.selection,h=f.getRanges()[0],p;if(CKEDITOR.env.gecko||CKEDITOR.env.ie&&CKEDITOR.env.needsBrFiller)if(f=e(f,c))f.appendBogus(),p=CKEDITOR.env.ie;
m(b,c.block,d)&&h.collapsed&&!h.getCommonAncestor().isReadOnly()&&(c=h.clone(),c.enlarge(CKEDITOR.ENLARGE_BLOCK_CONTENTS),d=new CKEDITOR.dom.walker(c),d.guard=function(a){return!g(a)||a.type==CKEDITOR.NODE_COMMENT||a.isReadOnly()},!d.checkForward()||c.checkStartOfBlock()&&c.checkEndOfBlock())&&(b=h.fixBlock(!0,b.activeEnterMode==CKEDITOR.ENTER_DIV?"div":"p"),CKEDITOR.env.needsBrFiller||(b=b.getFirst(g))&&b.type==CKEDITOR.NODE_TEXT&&CKEDITOR.tools.trim(b.getText()).match(/^(?:&nbsp;|\xa0)$/)&&b.remove(),
p=1,a.cancel());p&&h.select()}function e(a,b){if(a.isFake)return 0;var c=b.block||b.blockLimit,d=c&&c.getLast(g);if(!(!c||!c.isBlockBoundary()||d&&d.type==CKEDITOR.NODE_ELEMENT&&d.isBlockBoundary()||c.is("pre")||c.getBogus()))return c}function d(a){var b=a.data.getTarget();b.is("input")&&(b=b.getAttribute("type"),"submit"!=b&&"reset"!=b||a.data.preventDefault())}function g(a){return f(a)&&p(a)}function l(a,b){return function(c){var d=c.data.$.toElement||c.data.$.fromElement||c.data.$.relatedTarget;
(d=d&&d.nodeType==CKEDITOR.NODE_ELEMENT?new CKEDITOR.dom.element(d):null)&&(b.equals(d)||b.contains(d))||a.call(this,c)}}function k(a){function b(a){return function(b,d){d&&b.type==CKEDITOR.NODE_ELEMENT&&b.is(f)&&(c=b);if(!(d||!g(b)||a&&x(b)))return!1}}var c,d=a.getRanges()[0];a=a.root;var f={table:1,ul:1,ol:1,dl:1};if(d.startPath().contains(f)){var e=d.clone();e.collapse(1);e.setStartAt(a,CKEDITOR.POSITION_AFTER_START);a=new CKEDITOR.dom.walker(e);a.guard=b();a.checkBackward();if(c)return e=d.clone(),
e.collapse(),e.setEndAt(c,CKEDITOR.POSITION_AFTER_END),a=new CKEDITOR.dom.walker(e),a.guard=b(!0),c=!1,a.checkForward(),c}return null}function m(a,b,c){return!1!==a.config.autoParagraph&&a.activeEnterMode!=CKEDITOR.ENTER_BR&&(a.editable().equals(c)&&!b||b&&"true"==b.getAttribute("contenteditable"))}function h(a){return a.activeEnterMode!=CKEDITOR.ENTER_BR&&!1!==a.config.autoParagraph?a.activeEnterMode==CKEDITOR.ENTER_DIV?"div":"p":!1}function b(a){var b=a.editor;b.getSelection().scrollIntoView();
setTimeout(function(){b.fire("saveSnapshot")},0)}function c(a,b,c){var d=a.getCommonAncestor(b);for(b=a=c?b:a;(a=a.getParent())&&!d.equals(a)&&1==a.getChildCount();)b=a;b.remove()}var f,p,B,x,t,u,y,H,w,F;CKEDITOR.editable=CKEDITOR.tools.createClass({base:CKEDITOR.dom.element,$:function(a,b){this.base(b.$||b);this.editor=a;this.status="unloaded";this.hasFocus=!1;this.setup()},proto:{focus:function(){var a;if(CKEDITOR.env.webkit&&!this.hasFocus&&(a=this.editor._.previousActive||this.getDocument().getActive(),
this.contains(a))){a.focus();return}CKEDITOR.env.edge&&14<CKEDITOR.env.version&&!this.hasFocus&&this.getDocument().equals(CKEDITOR.document)&&(this.editor._.previousScrollTop=this.$.scrollTop);try{!CKEDITOR.env.ie||CKEDITOR.env.edge&&14<CKEDITOR.env.version||!this.getDocument().equals(CKEDITOR.document)?this.$.focus():this.$.setActive()}catch(b){if(!CKEDITOR.env.ie)throw b;}CKEDITOR.env.safari&&!this.isInline()&&(a=CKEDITOR.document.getActive(),a.equals(this.getWindow().getFrame())||this.getWindow().focus())},
on:function(a,b){var c=Array.prototype.slice.call(arguments,0);CKEDITOR.env.ie&&/^focus|blur$/.exec(a)&&(a="focus"==a?"focusin":"focusout",b=l(b,this),c[0]=a,c[1]=b);return CKEDITOR.dom.element.prototype.on.apply(this,c)},attachListener:function(a){!this._.listeners&&(this._.listeners=[]);var b=Array.prototype.slice.call(arguments,1),b=a.on.apply(a,b);this._.listeners.push(b);return b},clearListeners:function(){var a=this._.listeners;try{for(;a.length;)a.pop().removeListener()}catch(b){}},restoreAttrs:function(){var a=
this._.attrChanges,b,c;for(c in a)a.hasOwnProperty(c)&&(b=a[c],null!==b?this.setAttribute(c,b):this.removeAttribute(c))},attachClass:function(a){var b=this.getCustomData("classes");this.hasClass(a)||(!b&&(b=[]),b.push(a),this.setCustomData("classes",b),this.addClass(a))},changeAttr:function(a,b){var c=this.getAttribute(a);b!==c&&(!this._.attrChanges&&(this._.attrChanges={}),a in this._.attrChanges||(this._.attrChanges[a]=c),this.setAttribute(a,b))},insertText:function(a){this.editor.focus();this.insertHtml(this.transformPlainTextToHtml(a),
"text")},transformPlainTextToHtml:function(a){var b=this.editor.getSelection().getStartElement().hasAscendant("pre",!0)?CKEDITOR.ENTER_BR:this.editor.activeEnterMode;return CKEDITOR.tools.transformPlainTextToHtml(a,b)},insertHtml:function(a,c,d){var f=this.editor;f.focus();f.fire("saveSnapshot");d||(d=f.getSelection().getRanges()[0]);u(this,c||"html",a,d);d.select();b(this);this.editor.fire("afterInsertHtml",{})},insertHtmlIntoRange:function(a,b,c){u(this,c||"html",a,b);this.editor.fire("afterInsertHtml",
{intoRange:b})},insertElement:function(a,c){var d=this.editor;d.focus();d.fire("saveSnapshot");var f=d.activeEnterMode,d=d.getSelection(),e=a.getName(),e=CKEDITOR.dtd.$block[e];c||(c=d.getRanges()[0]);this.insertElementIntoRange(a,c)&&(c.moveToPosition(a,CKEDITOR.POSITION_AFTER_END),e&&((e=a.getNext(function(a){return g(a)&&!x(a)}))&&e.type==CKEDITOR.NODE_ELEMENT&&e.is(CKEDITOR.dtd.$block)?e.getDtd()["#"]?c.moveToElementEditStart(e):c.moveToElementEditEnd(a):e||f==CKEDITOR.ENTER_BR||(e=c.fixBlock(!0,
f==CKEDITOR.ENTER_DIV?"div":"p"),c.moveToElementEditStart(e))));d.selectRanges([c]);b(this)},insertElementIntoSelection:function(a){this.insertElement(a)},insertElementIntoRange:function(a,b){var c=this.editor,d=c.config.enterMode,f=a.getName(),e=CKEDITOR.dtd.$block[f];if(b.checkReadOnly())return!1;b.deleteContents(1);b.startContainer.type==CKEDITOR.NODE_ELEMENT&&(b.startContainer.is({tr:1,table:1,tbody:1,thead:1,tfoot:1})?y(b):b.startContainer.is(CKEDITOR.dtd.$list)&&H(b));var g,h;if(e)for(;(g=b.getCommonAncestor(0,
1))&&(h=CKEDITOR.dtd[g.getName()])&&(!h||!h[f]);)g.getName()in CKEDITOR.dtd.span?b.splitElement(g):b.checkStartOfBlock()&&b.checkEndOfBlock()?(b.setStartBefore(g),b.collapse(!0),g.remove()):b.splitBlock(d==CKEDITOR.ENTER_DIV?"div":"p",c.editable());b.insertNode(a);return!0},setData:function(a,b){b||(a=this.editor.dataProcessor.toHtml(a));this.setHtml(a);this.fixInitialSelection();"unloaded"==this.status&&(this.status="ready");this.editor.fire("dataReady")},getData:function(a){var b=this.getHtml();
a||(b=this.editor.dataProcessor.toDataFormat(b));return b},setReadOnly:function(a){this.setAttribute("contenteditable",!a)},detach:function(){this.removeClass("cke_editable");this.status="detached";var a=this.editor;this._.detach();delete a.document;delete a.window},isInline:function(){return this.getDocument().equals(CKEDITOR.document)},fixInitialSelection:function(){function a(){var b=c.getDocument().$,d=b.getSelection(),f;a:if(d.anchorNode&&d.anchorNode==c.$)f=!0;else{if(CKEDITOR.env.webkit&&(f=
c.getDocument().getActive())&&f.equals(c)&&!d.anchorNode){f=!0;break a}f=void 0}f&&(f=new CKEDITOR.dom.range(c),f.moveToElementEditStart(c),b=b.createRange(),b.setStart(f.startContainer.$,f.startOffset),b.collapse(!0),d.removeAllRanges(),d.addRange(b))}function b(){var a=c.getDocument().$,d=a.selection,f=c.getDocument().getActive();"None"==d.type&&f.equals(c)&&(d=new CKEDITOR.dom.range(c),a=a.body.createTextRange(),d.moveToElementEditStart(c),d=d.startContainer,d.type!=CKEDITOR.NODE_ELEMENT&&(d=d.getParent()),
a.moveToElementText(d.$),a.collapse(!0),a.select())}var c=this;if(CKEDITOR.env.ie&&(9>CKEDITOR.env.version||CKEDITOR.env.quirks))this.hasFocus&&(this.focus(),b());else if(this.hasFocus)this.focus(),a();else this.once("focus",function(){a()},null,null,-999)},getHtmlFromRange:function(a){if(a.collapsed)return new CKEDITOR.dom.documentFragment(a.document);a={doc:this.getDocument(),range:a.clone()};w.eol.detect(a,this);w.bogus.exclude(a);w.cell.shrink(a);a.fragment=a.range.cloneContents();w.tree.rebuild(a,
this);w.eol.fix(a,this);return new CKEDITOR.dom.documentFragment(a.fragment.$)},extractHtmlFromRange:function(a,b){var c=F,d={range:a,doc:a.document},f=this.getHtmlFromRange(a);if(a.collapsed)return a.optimize(),f;a.enlarge(CKEDITOR.ENLARGE_INLINE,1);c.table.detectPurge(d);d.bookmark=a.createBookmark();delete d.range;var e=this.editor.createRange();e.moveToPosition(d.bookmark.startNode,CKEDITOR.POSITION_BEFORE_START);d.targetBookmark=e.createBookmark();c.list.detectMerge(d,this);c.table.detectRanges(d,
this);c.block.detectMerge(d,this);d.tableContentsRanges?(c.table.deleteRanges(d),a.moveToBookmark(d.bookmark),d.range=a):(a.moveToBookmark(d.bookmark),d.range=a,a.extractContents(c.detectExtractMerge(d)));a.moveToBookmark(d.targetBookmark);a.optimize();c.fixUneditableRangePosition(a);c.list.merge(d,this);c.table.purge(d,this);c.block.merge(d,this);if(b){c=a.startPath();if(d=a.checkStartOfBlock()&&a.checkEndOfBlock()&&c.block&&!a.root.equals(c.block)){a:{var d=c.block.getElementsByTag("span"),e=0,
g;if(d)for(;g=d.getItem(e++);)if(!p(g)){d=!0;break a}d=!1}d=!d}d&&(a.moveToPosition(c.block,CKEDITOR.POSITION_BEFORE_START),c.block.remove())}else c.autoParagraph(this.editor,a),B(a.startContainer)&&a.startContainer.appendBogus();a.startContainer.mergeSiblings();return f},setup:function(){var a=this.editor;this.attachListener(a,"beforeGetData",function(){var b=this.getData();this.is("textarea")||!1!==a.config.ignoreEmptyParagraph&&(b=b.replace(t,function(a,b){return b}));a.setData(b,null,1)},this);
this.attachListener(a,"getSnapshot",function(a){a.data=this.getData(1)},this);this.attachListener(a,"afterSetData",function(){this.setData(a.getData(1))},this);this.attachListener(a,"loadSnapshot",function(a){this.setData(a.data,1)},this);this.attachListener(a,"beforeFocus",function(){var b=a.getSelection();(b=b&&b.getNative())&&"Control"==b.type||this.focus()},this);this.attachListener(a,"insertHtml",function(a){this.insertHtml(a.data.dataValue,a.data.mode,a.data.range)},this);this.attachListener(a,
"insertElement",function(a){this.insertElement(a.data)},this);this.attachListener(a,"insertText",function(a){this.insertText(a.data)},this);this.setReadOnly(a.readOnly);this.attachClass("cke_editable");a.elementMode==CKEDITOR.ELEMENT_MODE_INLINE?this.attachClass("cke_editable_inline"):a.elementMode!=CKEDITOR.ELEMENT_MODE_REPLACE&&a.elementMode!=CKEDITOR.ELEMENT_MODE_APPENDTO||this.attachClass("cke_editable_themed");this.attachClass("cke_contents_"+a.config.contentsLangDirection);a.keystrokeHandler.blockedKeystrokes[8]=
+a.readOnly;a.keystrokeHandler.attach(this);this.on("blur",function(){this.hasFocus=!1},null,null,-1);this.on("focus",function(){this.hasFocus=!0},null,null,-1);if(CKEDITOR.env.webkit)this.on("scroll",function(){a._.previousScrollTop=a.editable().$.scrollTop},null,null,-1);if(CKEDITOR.env.edge&&14<CKEDITOR.env.version){var b=function(){var c=a.editable();null!=a._.previousScrollTop&&c.getDocument().equals(CKEDITOR.document)&&(c.$.scrollTop=a._.previousScrollTop,a._.previousScrollTop=null,this.removeListener("scroll",
b))};this.on("scroll",b)}a.focusManager.add(this);this.equals(CKEDITOR.document.getActive())&&(this.hasFocus=!0,a.once("contentDom",function(){a.focusManager.focus(this)},this));this.isInline()&&this.changeAttr("tabindex",a.tabIndex);if(!this.is("textarea")){a.document=this.getDocument();a.window=this.getWindow();var e=a.document;this.changeAttr("spellcheck",!a.config.disableNativeSpellChecker);var h=a.config.contentsLangDirection;this.getDirection(1)!=h&&this.changeAttr("dir",h);var p=CKEDITOR.getCss();
if(p){var h=e.getHead(),m=h.getCustomData("stylesheet");m?p!=m.getText()&&(CKEDITOR.env.ie&&9>CKEDITOR.env.version?m.$.styleSheet.cssText=p:m.setText(p)):(p=e.appendStyleText(p),p=new CKEDITOR.dom.element(p.ownerNode||p.owningElement),h.setCustomData("stylesheet",p),p.data("cke-temp",1))}h=e.getCustomData("stylesheet_ref")||0;e.setCustomData("stylesheet_ref",h+1);this.setCustomData("cke_includeReadonly",!a.config.disableReadonlyStyling);this.attachListener(this,"click",function(a){a=a.data;var b=
(new CKEDITOR.dom.elementPath(a.getTarget(),this)).contains("a");b&&2!=a.$.button&&b.isReadOnly()&&a.preventDefault()});var l={8:1,46:1};this.attachListener(a,"key",function(b){if(a.readOnly)return!0;var c=b.data.domEvent.getKey(),d;if(c in l){b=a.getSelection();var e,g=b.getRanges()[0],q=g.startPath(),h,p,r,c=8==c;CKEDITOR.env.ie&&11>CKEDITOR.env.version&&(e=b.getSelectedElement())||(e=k(b))?(a.fire("saveSnapshot"),g.moveToPosition(e,CKEDITOR.POSITION_BEFORE_START),e.remove(),g.select(),a.fire("saveSnapshot"),
d=1):g.collapsed&&((h=q.block)&&(r=h[c?"getPrevious":"getNext"](f))&&r.type==CKEDITOR.NODE_ELEMENT&&r.is("table")&&g[c?"checkStartOfBlock":"checkEndOfBlock"]()?(a.fire("saveSnapshot"),g[c?"checkEndOfBlock":"checkStartOfBlock"]()&&h.remove(),g["moveToElementEdit"+(c?"End":"Start")](r),g.select(),a.fire("saveSnapshot"),d=1):q.blockLimit&&q.blockLimit.is("td")&&(p=q.blockLimit.getAscendant("table"))&&g.checkBoundaryOfElement(p,c?CKEDITOR.START:CKEDITOR.END)&&(r=p[c?"getPrevious":"getNext"](f))?(a.fire("saveSnapshot"),
g["moveToElementEdit"+(c?"End":"Start")](r),g.checkStartOfBlock()&&g.checkEndOfBlock()?r.remove():g.select(),a.fire("saveSnapshot"),d=1):(p=q.contains(["td","th","caption"]))&&g.checkBoundaryOfElement(p,c?CKEDITOR.START:CKEDITOR.END)&&(d=1))}return!d});a.blockless&&CKEDITOR.env.ie&&CKEDITOR.env.needsBrFiller&&this.attachListener(this,"keyup",function(b){b.data.getKeystroke()in l&&!this.getFirst(g)&&(this.appendBogus(),b=a.createRange(),b.moveToPosition(this,CKEDITOR.POSITION_AFTER_START),b.select())});
this.attachListener(this,"dblclick",function(b){if(a.readOnly)return!1;b={element:b.data.getTarget()};a.fire("doubleclick",b)});CKEDITOR.env.ie&&this.attachListener(this,"click",d);CKEDITOR.env.ie&&!CKEDITOR.env.edge||this.attachListener(this,"mousedown",function(b){var c=b.data.getTarget();c.is("img","hr","input","textarea","select")&&!c.isReadOnly()&&(a.getSelection().selectElement(c),c.is("input","textarea","select")&&b.data.preventDefault())});CKEDITOR.env.edge&&this.attachListener(this,"mouseup",
function(b){(b=b.data.getTarget())&&b.is("img")&&a.getSelection().selectElement(b)});CKEDITOR.env.gecko&&this.attachListener(this,"mouseup",function(b){if(2==b.data.$.button&&(b=b.data.getTarget(),!b.getOuterHtml().replace(t,""))){var c=a.createRange();c.moveToElementEditStart(b);c.select(!0)}});CKEDITOR.env.webkit&&(this.attachListener(this,"click",function(a){a.data.getTarget().is("input","select")&&a.data.preventDefault()}),this.attachListener(this,"mouseup",function(a){a.data.getTarget().is("input",
"textarea")&&a.data.preventDefault()}));CKEDITOR.env.webkit&&this.attachListener(a,"key",function(b){if(a.readOnly)return!0;b=b.data.domEvent.getKey();if(b in l){var d=8==b,f=a.getSelection().getRanges()[0];b=f.startPath();if(f.collapsed)a:{var e=b.block;if(e&&f[d?"checkStartOfBlock":"checkEndOfBlock"]()&&f.moveToClosestEditablePosition(e,!d)&&f.collapsed){if(f.startContainer.type==CKEDITOR.NODE_ELEMENT){var g=f.startContainer.getChild(f.startOffset-(d?1:0));if(g&&g.type==CKEDITOR.NODE_ELEMENT&&g.is("hr")){a.fire("saveSnapshot");
g.remove();b=!0;break a}}f=f.startPath().block;if(!f||f&&f.contains(e))b=void 0;else{a.fire("saveSnapshot");var q;(q=(d?f:e).getBogus())&&q.remove();q=a.getSelection();g=q.createBookmarks();(d?e:f).moveChildren(d?f:e,!1);b.lastElement.mergeSiblings();c(e,f,!d);q.selectBookmarks(g);b=!0}}else b=!1}else d=f,q=b.block,f=d.endPath().block,q&&f&&!q.equals(f)?(a.fire("saveSnapshot"),(e=q.getBogus())&&e.remove(),d.enlarge(CKEDITOR.ENLARGE_INLINE),d.deleteContents(),f.getParent()&&(f.moveChildren(q,!1),b.lastElement.mergeSiblings(),
c(q,f,!0)),d=a.getSelection().getRanges()[0],d.collapse(1),d.optimize(),""===d.startContainer.getHtml()&&d.startContainer.appendBogus(),d.select(),b=!0):b=!1;if(!b)return;a.getSelection().scrollIntoView();a.fire("saveSnapshot");return!1}},this,null,100)}}},_:{detach:function(){this.editor.setData(this.editor.getData(),0,1);this.clearListeners();this.restoreAttrs();var a;if(a=this.removeCustomData("classes"))for(;a.length;)this.removeClass(a.pop());if(!this.is("textarea")){a=this.getDocument();var b=
a.getHead();if(b.getCustomData("stylesheet")){var c=a.getCustomData("stylesheet_ref");--c?a.setCustomData("stylesheet_ref",c):(a.removeCustomData("stylesheet_ref"),b.removeCustomData("stylesheet").remove())}}this.editor.fire("contentDomUnload");delete this.editor}}});CKEDITOR.editor.prototype.editable=function(a){var b=this._.editable;if(b&&a)return 0;arguments.length&&(b=this._.editable=a?a instanceof CKEDITOR.editable?a:new CKEDITOR.editable(this,a):(b&&b.detach(),null));return b};CKEDITOR.on("instanceLoaded",
function(b){var c=b.editor;c.on("insertElement",function(a){a=a.data;a.type==CKEDITOR.NODE_ELEMENT&&(a.is("input")||a.is("textarea"))&&("false"!=a.getAttribute("contentEditable")&&a.data("cke-editable",a.hasAttribute("contenteditable")?"true":"1"),a.setAttribute("contentEditable",!1))});c.on("selectionChange",function(b){if(!c.readOnly){var d=c.getSelection();d&&!d.isLocked&&(d=c.checkDirty(),c.fire("lockSnapshot"),a(b),c.fire("unlockSnapshot"),!d&&c.resetDirty())}})});CKEDITOR.on("instanceCreated",
function(a){var b=a.editor;b.on("mode",function(){var a=b.editable();if(a&&a.isInline()){var c=b.title;a.changeAttr("role","textbox");a.changeAttr("aria-label",c);c&&a.changeAttr("title",c);var d=b.fire("ariaEditorHelpLabel",{}).label;if(d&&(c=this.ui.space(this.elementMode==CKEDITOR.ELEMENT_MODE_INLINE?"top":"contents"))){var f=CKEDITOR.tools.getNextId(),d=CKEDITOR.dom.element.createFromHtml('\x3cspan id\x3d"'+f+'" class\x3d"cke_voice_label"\x3e'+d+"\x3c/span\x3e");c.append(d);a.changeAttr("aria-describedby",
f)}}})});CKEDITOR.addCss(".cke_editable{cursor:text}.cke_editable img,.cke_editable input,.cke_editable textarea{cursor:default}");f=CKEDITOR.dom.walker.whitespaces(!0);p=CKEDITOR.dom.walker.bookmark(!1,!0);B=CKEDITOR.dom.walker.empty();x=CKEDITOR.dom.walker.bogus();t=/(^|<body\b[^>]*>)\s*<(p|div|address|h\d|center|pre)[^>]*>\s*(?:<br[^>]*>|&nbsp;|\u00A0|&#160;)?\s*(:?<\/\2>)?\s*(?=$|<\/body>)/gi;u=function(){function a(b){return b.type==CKEDITOR.NODE_ELEMENT}function b(c,d){var f,e,g,h,p=[],m=d.range.startContainer;
f=d.range.startPath();for(var m=k[m.getName()],l=0,D=c.getChildren(),C=D.count(),E=-1,A=-1,M=0,I=f.contains(k.$list);l<C;++l)f=D.getItem(l),a(f)?(g=f.getName(),I&&g in CKEDITOR.dtd.$list?p=p.concat(b(f,d)):(h=!!m[g],"br"!=g||!f.data("cke-eol")||l&&l!=C-1||(M=(e=l?p[l-1].node:D.getItem(l+1))&&(!a(e)||!e.is("br")),e=e&&a(e)&&k.$block[e.getName()]),-1!=E||h||(E=l),h||(A=l),p.push({isElement:1,isLineBreak:M,isBlock:f.isBlockBoundary(),hasBlockSibling:e,node:f,name:g,allowed:h}),e=M=0)):p.push({isElement:0,
node:f,allowed:1});-1<E&&(p[E].firstNotAllowed=1);-1<A&&(p[A].lastNotAllowed=1);return p}function c(b,d){var f=[],e=b.getChildren(),g=e.count(),p,h=0,r=k[d],m=!b.is(k.$inline)||b.is("br");for(m&&f.push(" ");h<g;h++)p=e.getItem(h),a(p)&&!p.is(r)?f=f.concat(c(p,d)):f.push(p);m&&f.push(" ");return f}function d(b){return a(b.startContainer)&&b.startContainer.getChild(b.startOffset-1)}function f(b){return b&&a(b)&&(b.is(k.$removeEmpty)||b.is("a")&&!b.isBlockBoundary())}function e(b,c,d,f){var g=b.clone(),
p,h;g.setEndAt(c,CKEDITOR.POSITION_BEFORE_END);(p=(new CKEDITOR.dom.walker(g)).next())&&a(p)&&l[p.getName()]&&(h=p.getPrevious())&&a(h)&&!h.getParent().equals(b.startContainer)&&d.contains(h)&&f.contains(p)&&p.isIdentical(h)&&(p.moveChildren(h),p.remove(),e(b,c,d,f))}function p(b,c){function d(b,c){if(c.isBlock&&c.isElement&&!c.node.is("br")&&a(b)&&b.is("br"))return b.remove(),1}var f=c.endContainer.getChild(c.endOffset),e=c.endContainer.getChild(c.endOffset-1);f&&d(f,b[b.length-1]);e&&d(e,b[0])&&
(c.setEnd(c.endContainer,c.endOffset-1),c.collapse())}var k=CKEDITOR.dtd,l={p:1,div:1,h1:1,h2:1,h3:1,h4:1,h5:1,h6:1,ul:1,ol:1,li:1,pre:1,dl:1,blockquote:1},B={p:1,div:1,h1:1,h2:1,h3:1,h4:1,h5:1,h6:1},x=CKEDITOR.tools.extend({},k.$inline);delete x.br;return function(v,q,N,G){var l=v.editor,u=!1;"unfiltered_html"==q&&(q="html",u=!0);if(!G.checkReadOnly()){var Q=(new CKEDITOR.dom.elementPath(G.startContainer,G.root)).blockLimit||G.root;v={type:q,dontFilter:u,editable:v,editor:l,range:G,blockLimit:Q,
mergeCandidates:[],zombies:[]};q=v.range;G=v.mergeCandidates;var t,L;"text"==v.type&&q.shrink(CKEDITOR.SHRINK_ELEMENT,!0,!1)&&(t=CKEDITOR.dom.element.createFromHtml("\x3cspan\x3e\x26nbsp;\x3c/span\x3e",q.document),q.insertNode(t),q.setStartAfter(t));u=new CKEDITOR.dom.elementPath(q.startContainer);v.endPath=Q=new CKEDITOR.dom.elementPath(q.endContainer);if(!q.collapsed){var l=Q.block||Q.blockLimit,y=q.getCommonAncestor();l&&!l.equals(y)&&!l.contains(y)&&q.checkEndOfBlock()&&v.zombies.push(l);q.deleteContents()}for(;(L=
d(q))&&a(L)&&L.isBlockBoundary()&&u.contains(L);)q.moveToPosition(L,CKEDITOR.POSITION_BEFORE_END);e(q,v.blockLimit,u,Q);t&&(q.setEndBefore(t),q.collapse(),t.remove());t=q.startPath();if(l=t.contains(f,!1,1))q.splitElement(l),v.inlineStylesRoot=l,v.inlineStylesPeak=t.lastElement;t=q.createBookmark();(l=t.startNode.getPrevious(g))&&a(l)&&f(l)&&G.push(l);(l=t.startNode.getNext(g))&&a(l)&&f(l)&&G.push(l);for(l=t.startNode;(l=l.getParent())&&f(l);)G.push(l);q.moveToBookmark(t);if(t=N){t=v.range;if("text"==
v.type&&v.inlineStylesRoot){L=v.inlineStylesPeak;q=L.getDocument().createText("{cke-peak}");for(G=v.inlineStylesRoot.getParent();!L.equals(G);)q=q.appendTo(L.clone()),L=L.getParent();N=q.getOuterHtml().split("{cke-peak}").join(N)}L=v.blockLimit.getName();if(/^\s+|\s+$/.test(N)&&"span"in CKEDITOR.dtd[L]){var w='\x3cspan data-cke-marker\x3d"1"\x3e\x26nbsp;\x3c/span\x3e';N=w+N+w}N=v.editor.dataProcessor.toHtml(N,{context:null,fixForBody:!1,protectedWhitespaces:!!w,dontFilter:v.dontFilter,filter:v.editor.activeFilter,
enterMode:v.editor.activeEnterMode});L=t.document.createElement("body");L.setHtml(N);w&&(L.getFirst().remove(),L.getLast().remove());if((w=t.startPath().block)&&(1!=w.getChildCount()||!w.getBogus()))a:{var E;if(1==L.getChildCount()&&a(E=L.getFirst())&&E.is(B)&&!E.hasAttribute("contenteditable")){w=E.getElementsByTag("*");t=0;for(G=w.count();t<G;t++)if(q=w.getItem(t),!q.is(x))break a;E.moveChildren(E.getParent(1));E.remove()}}v.dataWrapper=L;t=N}if(t){E=v.range;t=E.document;var A;L=v.blockLimit;G=
0;var M,w=[],I,W;N=l=0;var T,aa;q=E.startContainer;var u=v.endPath.elements[0],U,Q=u.getPosition(q),y=!!u.getCommonAncestor(q)&&Q!=CKEDITOR.POSITION_IDENTICAL&&!(Q&CKEDITOR.POSITION_CONTAINS+CKEDITOR.POSITION_IS_CONTAINED);q=b(v.dataWrapper,v);for(p(q,E);G<q.length;G++){Q=q[G];if(A=Q.isLineBreak){A=E;T=L;var H=void 0,F=void 0;Q.hasBlockSibling?A=1:(H=A.startContainer.getAscendant(k.$block,1))&&H.is({div:1,p:1})?(F=H.getPosition(T),F==CKEDITOR.POSITION_IDENTICAL||F==CKEDITOR.POSITION_CONTAINS?A=0:
(T=A.splitElement(H),A.moveToPosition(T,CKEDITOR.POSITION_AFTER_START),A=1)):A=0}if(A)N=0<G;else{A=E.startPath();!Q.isBlock&&m(v.editor,A.block,A.blockLimit)&&(W=h(v.editor))&&(W=t.createElement(W),W.appendBogus(),E.insertNode(W),CKEDITOR.env.needsBrFiller&&(M=W.getBogus())&&M.remove(),E.moveToPosition(W,CKEDITOR.POSITION_BEFORE_END));if((A=E.startPath().block)&&!A.equals(I)){if(M=A.getBogus())M.remove(),w.push(A);I=A}Q.firstNotAllowed&&(l=1);if(l&&Q.isElement){A=E.startContainer;for(T=null;A&&!k[A.getName()][Q.name];){if(A.equals(L)){A=
null;break}T=A;A=A.getParent()}if(A)T&&(aa=E.splitElement(T),v.zombies.push(aa),v.zombies.push(T));else{T=L.getName();U=!G;A=G==q.length-1;T=c(Q.node,T);for(var H=[],F=T.length,da=0,ea=void 0,fa=0,ga=-1;da<F;da++)ea=T[da]," "==ea?(fa||U&&!da||(H.push(new CKEDITOR.dom.text(" ")),ga=H.length),fa=1):(H.push(ea),fa=0);A&&ga==H.length&&H.pop();U=H}}if(U){for(;A=U.pop();)E.insertNode(A);U=0}else E.insertNode(Q.node);Q.lastNotAllowed&&G<q.length-1&&((aa=y?u:aa)&&E.setEndAt(aa,CKEDITOR.POSITION_AFTER_START),
l=0);E.collapse()}}1!=q.length?M=!1:(M=q[0],M=M.isElement&&"false"==M.node.getAttribute("contenteditable"));M&&(N=!0,A=q[0].node,E.setStartAt(A,CKEDITOR.POSITION_BEFORE_START),E.setEndAt(A,CKEDITOR.POSITION_AFTER_END));v.dontMoveCaret=N;v.bogusNeededBlocks=w}M=v.range;var ba;aa=v.bogusNeededBlocks;for(U=M.createBookmark();I=v.zombies.pop();)I.getParent()&&(W=M.clone(),W.moveToElementEditStart(I),W.removeEmptyBlocksAtEnd());if(aa)for(;I=aa.pop();)CKEDITOR.env.needsBrFiller?I.appendBogus():I.append(M.document.createText(" "));
for(;I=v.mergeCandidates.pop();)I.mergeSiblings();M.moveToBookmark(U);if(!v.dontMoveCaret){for(I=d(M);I&&a(I)&&!I.is(k.$empty);){if(I.isBlockBoundary())M.moveToPosition(I,CKEDITOR.POSITION_BEFORE_END);else{if(f(I)&&I.getHtml().match(/(\s|&nbsp;)$/g)){ba=null;break}ba=M.clone();ba.moveToPosition(I,CKEDITOR.POSITION_BEFORE_END)}I=I.getLast(g)}ba&&M.moveToRange(ba)}}}}();y=function(){function a(b){b=new CKEDITOR.dom.walker(b);b.guard=function(a,b){if(b)return!1;if(a.type==CKEDITOR.NODE_ELEMENT)return a.is(CKEDITOR.dtd.$tableContent)};
b.evaluator=function(a){return a.type==CKEDITOR.NODE_ELEMENT};return b}function b(a,c,d){c=a.getDocument().createElement(c);a.append(c,d);return c}function c(a){var b=a.count(),d;for(b;0<b--;)d=a.getItem(b),CKEDITOR.tools.trim(d.getHtml())||(d.appendBogus(),CKEDITOR.env.ie&&9>CKEDITOR.env.version&&d.getChildCount()&&d.getFirst().remove())}return function(d){var f=d.startContainer,e=f.getAscendant("table",1),g=!1;c(e.getElementsByTag("td"));c(e.getElementsByTag("th"));e=d.clone();e.setStart(f,0);e=
a(e).lastBackward();e||(e=d.clone(),e.setEndAt(f,CKEDITOR.POSITION_BEFORE_END),e=a(e).lastForward(),g=!0);e||(e=f);e.is("table")?(d.setStartAt(e,CKEDITOR.POSITION_BEFORE_START),d.collapse(!0),e.remove()):(e.is({tbody:1,thead:1,tfoot:1})&&(e=b(e,"tr",g)),e.is("tr")&&(e=b(e,e.getParent().is("thead")?"th":"td",g)),(f=e.getBogus())&&f.remove(),d.moveToPosition(e,g?CKEDITOR.POSITION_AFTER_START:CKEDITOR.POSITION_BEFORE_END))}}();H=function(){function a(b){b=new CKEDITOR.dom.walker(b);b.guard=function(a,
b){if(b)return!1;if(a.type==CKEDITOR.NODE_ELEMENT)return a.is(CKEDITOR.dtd.$list)||a.is(CKEDITOR.dtd.$listItem)};b.evaluator=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&a.is(CKEDITOR.dtd.$listItem)};return b}return function(b){var c=b.startContainer,d=!1,f;f=b.clone();f.setStart(c,0);f=a(f).lastBackward();f||(f=b.clone(),f.setEndAt(c,CKEDITOR.POSITION_BEFORE_END),f=a(f).lastForward(),d=!0);f||(f=c);f.is(CKEDITOR.dtd.$list)?(b.setStartAt(f,CKEDITOR.POSITION_BEFORE_START),b.collapse(!0),f.remove()):
((c=f.getBogus())&&c.remove(),b.moveToPosition(f,d?CKEDITOR.POSITION_AFTER_START:CKEDITOR.POSITION_BEFORE_END),b.select())}}();w={eol:{detect:function(a,b){var c=a.range,d=c.clone(),f=c.clone(),e=new CKEDITOR.dom.elementPath(c.startContainer,b),g=new CKEDITOR.dom.elementPath(c.endContainer,b);d.collapse(1);f.collapse();e.block&&d.checkBoundaryOfElement(e.block,CKEDITOR.END)&&(c.setStartAfter(e.block),a.prependEolBr=1);g.block&&f.checkBoundaryOfElement(g.block,CKEDITOR.START)&&(c.setEndBefore(g.block),
a.appendEolBr=1)},fix:function(a,b){var c=b.getDocument(),d;a.appendEolBr&&(d=this.createEolBr(c),a.fragment.append(d));!a.prependEolBr||d&&!d.getPrevious()||a.fragment.append(this.createEolBr(c),1)},createEolBr:function(a){return a.createElement("br",{attributes:{"data-cke-eol":1}})}},bogus:{exclude:function(a){var b=a.range.getBoundaryNodes(),c=b.startNode,b=b.endNode;!b||!x(b)||c&&c.equals(b)||a.range.setEndBefore(b)}},tree:{rebuild:function(a,b){var c=a.range,d=c.getCommonAncestor(),f=new CKEDITOR.dom.elementPath(d,
b),e=new CKEDITOR.dom.elementPath(c.startContainer,b),c=new CKEDITOR.dom.elementPath(c.endContainer,b),g;d.type==CKEDITOR.NODE_TEXT&&(d=d.getParent());if(f.blockLimit.is({tr:1,table:1})){var p=f.contains("table").getParent();g=function(a){return!a.equals(p)}}else if(f.block&&f.block.is(CKEDITOR.dtd.$listItem)&&(e=e.contains(CKEDITOR.dtd.$list),c=c.contains(CKEDITOR.dtd.$list),!e.equals(c))){var h=f.contains(CKEDITOR.dtd.$list).getParent();g=function(a){return!a.equals(h)}}g||(g=function(a){return!a.equals(f.block)&&
!a.equals(f.blockLimit)});this.rebuildFragment(a,b,d,g)},rebuildFragment:function(a,b,c,d){for(var f;c&&!c.equals(b)&&d(c);)f=c.clone(0,1),a.fragment.appendTo(f),a.fragment=f,c=c.getParent()}},cell:{shrink:function(a){a=a.range;var b=a.startContainer,c=a.endContainer,d=a.startOffset,f=a.endOffset;b.type==CKEDITOR.NODE_ELEMENT&&b.equals(c)&&b.is("tr")&&++d==f&&a.shrink(CKEDITOR.SHRINK_TEXT)}}};F=function(){function a(b,c){var d=b.getParent();if(d.is(CKEDITOR.dtd.$inline))b[c?"insertBefore":"insertAfter"](d)}
function b(c,d,f){a(d);a(f,1);for(var e;e=f.getNext();)e.insertAfter(d),d=e;B(c)&&c.remove()}function c(a,b){var d=new CKEDITOR.dom.range(a);d.setStartAfter(b.startNode);d.setEndBefore(b.endNode);return d}return{list:{detectMerge:function(a,b){var d=c(b,a.bookmark),f=d.startPath(),e=d.endPath(),g=f.contains(CKEDITOR.dtd.$list),p=e.contains(CKEDITOR.dtd.$list);a.mergeList=g&&p&&g.getParent().equals(p.getParent())&&!g.equals(p);a.mergeListItems=f.block&&e.block&&f.block.is(CKEDITOR.dtd.$listItem)&&
e.block.is(CKEDITOR.dtd.$listItem);if(a.mergeList||a.mergeListItems)d=d.clone(),d.setStartBefore(a.bookmark.startNode),d.setEndAfter(a.bookmark.endNode),a.mergeListBookmark=d.createBookmark()},merge:function(a,c){if(a.mergeListBookmark){var d=a.mergeListBookmark.startNode,f=a.mergeListBookmark.endNode,e=new CKEDITOR.dom.elementPath(d,c),g=new CKEDITOR.dom.elementPath(f,c);if(a.mergeList){var p=e.contains(CKEDITOR.dtd.$list),h=g.contains(CKEDITOR.dtd.$list);p.equals(h)||(h.moveChildren(p),h.remove())}a.mergeListItems&&
(e=e.contains(CKEDITOR.dtd.$listItem),g=g.contains(CKEDITOR.dtd.$listItem),e.equals(g)||b(g,d,f));d.remove();f.remove()}}},block:{detectMerge:function(a,b){if(!a.tableContentsRanges&&!a.mergeListBookmark){var c=new CKEDITOR.dom.range(b);c.setStartBefore(a.bookmark.startNode);c.setEndAfter(a.bookmark.endNode);a.mergeBlockBookmark=c.createBookmark()}},merge:function(a,c){if(a.mergeBlockBookmark&&!a.purgeTableBookmark){var d=a.mergeBlockBookmark.startNode,f=a.mergeBlockBookmark.endNode,e=new CKEDITOR.dom.elementPath(d,
c),g=new CKEDITOR.dom.elementPath(f,c),e=e.block,g=g.block;e&&g&&!e.equals(g)&&b(g,d,f);d.remove();f.remove()}}},table:function(){function a(c){var f=[],e,g=new CKEDITOR.dom.walker(c),p=c.startPath().contains(d),h=c.endPath().contains(d),q={};g.guard=function(a,g){if(a.type==CKEDITOR.NODE_ELEMENT){var n="visited_"+(g?"out":"in");if(a.getCustomData(n))return;CKEDITOR.dom.element.setMarker(q,a,n,1)}if(g&&p&&a.equals(p))e=c.clone(),e.setEndAt(p,CKEDITOR.POSITION_BEFORE_END),f.push(e);else if(!g&&h&&
a.equals(h))e=c.clone(),e.setStartAt(h,CKEDITOR.POSITION_AFTER_START),f.push(e);else{if(n=!g)n=a.type==CKEDITOR.NODE_ELEMENT&&a.is(d)&&(!p||b(a,p))&&(!h||b(a,h));n&&(e=c.clone(),e.selectNodeContents(a),f.push(e))}};g.lastForward();CKEDITOR.dom.element.clearAllMarkers(q);return f}function b(a,c){var d=CKEDITOR.POSITION_CONTAINS+CKEDITOR.POSITION_IS_CONTAINED,f=a.getPosition(c);return f===CKEDITOR.POSITION_IDENTICAL?!1:0===(f&d)}var d={td:1,th:1,caption:1};return{detectPurge:function(a){var b=a.range,
c=b.clone();c.enlarge(CKEDITOR.ENLARGE_ELEMENT);var c=new CKEDITOR.dom.walker(c),f=0;c.evaluator=function(a){a.type==CKEDITOR.NODE_ELEMENT&&a.is(d)&&++f};c.checkForward();if(1<f){var c=b.startPath().contains("table"),e=b.endPath().contains("table");c&&e&&b.checkBoundaryOfElement(c,CKEDITOR.START)&&b.checkBoundaryOfElement(e,CKEDITOR.END)&&(b=a.range.clone(),b.setStartBefore(c),b.setEndAfter(e),a.purgeTableBookmark=b.createBookmark())}},detectRanges:function(f,e){var g=c(e,f.bookmark),p=g.clone(),
h,v,q=g.getCommonAncestor();q.is(CKEDITOR.dtd.$tableContent)&&!q.is(d)&&(q=q.getAscendant("table",!0));v=q;q=new CKEDITOR.dom.elementPath(g.startContainer,v);v=new CKEDITOR.dom.elementPath(g.endContainer,v);q=q.contains("table");v=v.contains("table");if(q||v)q&&v&&b(q,v)?(f.tableSurroundingRange=p,p.setStartAt(q,CKEDITOR.POSITION_AFTER_END),p.setEndAt(v,CKEDITOR.POSITION_BEFORE_START),p=g.clone(),p.setEndAt(q,CKEDITOR.POSITION_AFTER_END),h=g.clone(),h.setStartAt(v,CKEDITOR.POSITION_BEFORE_START),
h=a(p).concat(a(h))):q?v||(f.tableSurroundingRange=p,p.setStartAt(q,CKEDITOR.POSITION_AFTER_END),g.setEndAt(q,CKEDITOR.POSITION_AFTER_END)):(f.tableSurroundingRange=p,p.setEndAt(v,CKEDITOR.POSITION_BEFORE_START),g.setStartAt(v,CKEDITOR.POSITION_AFTER_START)),f.tableContentsRanges=h?h:a(g)},deleteRanges:function(a){for(var b;b=a.tableContentsRanges.pop();)b.extractContents(),B(b.startContainer)&&b.startContainer.appendBogus();a.tableSurroundingRange&&a.tableSurroundingRange.extractContents()},purge:function(a){if(a.purgeTableBookmark){var b=
a.doc,c=a.range.clone(),b=b.createElement("p");b.insertBefore(a.purgeTableBookmark.startNode);c.moveToBookmark(a.purgeTableBookmark);c.deleteContents();a.range.moveToPosition(b,CKEDITOR.POSITION_AFTER_START)}}}}(),detectExtractMerge:function(a){return!(a.range.startPath().contains(CKEDITOR.dtd.$listItem)&&a.range.endPath().contains(CKEDITOR.dtd.$listItem))},fixUneditableRangePosition:function(a){a.startContainer.getDtd()["#"]||a.moveToClosestEditablePosition(null,!0)},autoParagraph:function(a,b){var c=
b.startPath(),d;m(a,c.block,c.blockLimit)&&(d=h(a))&&(d=b.document.createElement(d),d.appendBogus(),b.insertNode(d),b.moveToPosition(d,CKEDITOR.POSITION_AFTER_START))}}}()}(),function(){function a(){var a=this._.fakeSelection,b;a&&(b=this.getSelection(1),b&&b.isHidden()||(a.reset(),a=0));if(!a&&(a=b||this.getSelection(1),!a||a.getType()==CKEDITOR.SELECTION_NONE))return;this.fire("selectionCheck",a);b=this.elementPath();if(!b.compare(this._.selectionPreviousPath)){var c=this._.selectionPreviousPath&&
this._.selectionPreviousPath.blockLimit.equals(b.blockLimit);CKEDITOR.env.webkit&&!c&&(this._.previousActive=this.document.getActive());this._.selectionPreviousPath=b;this.fire("selectionChange",{selection:a,path:b})}}function e(){y=!0;u||(d.call(this),u=CKEDITOR.tools.setTimeout(d,200,this))}function d(){u=null;y&&(CKEDITOR.tools.setTimeout(a,0,this),y=!1)}function g(a){return H(a)||a.type==CKEDITOR.NODE_ELEMENT&&!a.is(CKEDITOR.dtd.$empty)?!0:!1}function l(a){function b(c,d){return c&&c.type!=CKEDITOR.NODE_TEXT?
a.clone()["moveToElementEdit"+(d?"End":"Start")](c):!1}if(!(a.root instanceof CKEDITOR.editable))return!1;var c=a.startContainer,d=a.getPreviousNode(g,null,c),f=a.getNextNode(g,null,c);return b(d)||b(f,1)||!(d||f||c.type==CKEDITOR.NODE_ELEMENT&&c.isBlockBoundary()&&c.getBogus())?!0:!1}function k(a){m(a,!1);var b=a.getDocument().createText(x);a.setCustomData("cke-fillingChar",b);return b}function m(a,b){var c=a&&a.removeCustomData("cke-fillingChar");if(c){if(!1!==b){var d=a.getDocument().getSelection().getNative(),
f=d&&"None"!=d.type&&d.getRangeAt(0),e=x.length;if(c.getLength()>e&&f&&f.intersectsNode(c.$)){var g=[{node:d.anchorNode,offset:d.anchorOffset},{node:d.focusNode,offset:d.focusOffset}];d.anchorNode==c.$&&d.anchorOffset>e&&(g[0].offset-=e);d.focusNode==c.$&&d.focusOffset>e&&(g[1].offset-=e)}}c.setText(h(c.getText(),1));g&&(c=a.getDocument().$,d=c.getSelection(),c=c.createRange(),c.setStart(g[0].node,g[0].offset),c.collapse(!0),d.removeAllRanges(),d.addRange(c),d.extend(g[1].node,g[1].offset))}}function h(a,
b){return b?a.replace(t,function(a,b){return b?" ":""}):a.replace(x,"")}function b(a,b){var c=CKEDITOR.dom.element.createFromHtml('\x3cdiv data-cke-hidden-sel\x3d"1" data-cke-temp\x3d"1" style\x3d"'+(CKEDITOR.env.ie&&14>CKEDITOR.env.version?"display:none":"position:fixed;top:0;left:-1000px")+'"\x3e'+(b||"\x26nbsp;")+"\x3c/div\x3e",a.document);a.fire("lockSnapshot");a.editable().append(c);var d=a.getSelection(1),f=a.createRange(),e=d.root.on("selectionchange",function(a){a.cancel()},null,null,0);f.setStartAt(c,
CKEDITOR.POSITION_AFTER_START);f.setEndAt(c,CKEDITOR.POSITION_BEFORE_END);d.selectRanges([f]);e.removeListener();a.fire("unlockSnapshot");a._.hiddenSelectionContainer=c}function c(a){var b={35:1,36:1,2228259:1,2228260:1,2228261:1,2228262:1,2228263:1,2228264:1,1114149:1,1114151:1,3342373:1,3342375:1},c=CKEDITOR.tools.extend({8:1,37:1,39:1,46:1},b);return function(d){var f=d.data.getKeystroke();if(c[f]){var e=a.getSelection(),g=e.getRanges(),p=g[0];b[f]?e.isFake&&(f=d.data.getKey(),p.moveToClosestEditablePosition(d.selected,
36===f||37===f||38==f),p.select()):1==g.length&&p.collapsed&&(p=p[38>f?"getPreviousEditableNode":"getNextEditableNode"]())&&p.type==CKEDITOR.NODE_ELEMENT&&"false"==p.getAttribute("contenteditable")&&(a.getSelection().fake(p),d.data.preventDefault(),d.cancel())}}}function f(a){for(var b=0;b<a.length;b++){var c=a[b];c.getCommonAncestor().isReadOnly()&&a.splice(b,1);if(!c.collapsed){if(c.startContainer.isReadOnly())for(var d=c.startContainer,f;d&&!((f=d.type==CKEDITOR.NODE_ELEMENT)&&d.is("body")||!d.isReadOnly());)f&&
"false"==d.getAttribute("contentEditable")&&c.setStartAfter(d),d=d.getParent();d=c.startContainer;f=c.endContainer;var e=c.startOffset,g=c.endOffset,p=c.clone();d&&d.type==CKEDITOR.NODE_TEXT&&(e>=d.getLength()?p.setStartAfter(d):p.setStartBefore(d));f&&f.type==CKEDITOR.NODE_TEXT&&(g?p.setEndAfter(f):p.setEndBefore(f));d=new CKEDITOR.dom.walker(p);d.evaluator=function(d){if(d.type==CKEDITOR.NODE_ELEMENT&&d.isReadOnly()){var f=c.clone();c.setEndBefore(d);c.collapsed&&a.splice(b--,1);d.getPosition(p.endContainer)&
CKEDITOR.POSITION_CONTAINS||(f.setStartAfter(d),f.collapsed||a.splice(b+1,0,f));return!0}return!1};d.next()}}return a}var p="function"!=typeof window.getSelection,B=1,x=CKEDITOR.tools.repeat("​",7),t=new RegExp(x+"( )?","g"),u,y,H=CKEDITOR.dom.walker.invisible(1),w=function(){function a(b){return function(a){var c=a.editor.createRange();c.moveToClosestEditablePosition(a.selected,b)&&a.editor.getSelection().selectRanges([c]);return!1}}function b(a){return function(b){var c=b.editor,d=c.createRange(),
f;(f=d.moveToClosestEditablePosition(b.selected,a))||(f=d.moveToClosestEditablePosition(b.selected,!a));f&&c.getSelection().selectRanges([d]);c.fire("saveSnapshot");b.selected.remove();f||(d.moveToElementEditablePosition(c.editable()),c.getSelection().selectRanges([d]));c.fire("saveSnapshot");return!1}}var c=a(),d=a(1);return{37:c,38:c,39:d,40:d,8:b(),46:b(1)}}();CKEDITOR.on("instanceCreated",function(b){function d(){var a=f.getSelection();a&&a.removeAllRanges()}var f=b.editor;f.on("contentDom",function(){function b(){q=
new CKEDITOR.dom.selection(f.getSelection());q.lock()}function d(){h.removeListener("mouseup",d);l.removeListener("mouseup",d);var a=CKEDITOR.document.$.selection,b=a.createRange();"None"!=a.type&&b.parentElement().ownerDocument==g.$&&b.select()}var g=f.document,h=CKEDITOR.document,n=f.editable(),k=g.getBody(),l=g.getDocumentElement(),B=n.isInline(),v,q;CKEDITOR.env.gecko&&n.attachListener(n,"focus",function(a){a.removeListener();0!==v&&(a=f.getSelection().getNative())&&a.isCollapsed&&a.anchorNode==
n.$&&(a=f.createRange(),a.moveToElementEditStart(n),a.select())},null,null,-2);n.attachListener(n,CKEDITOR.env.webkit?"DOMFocusIn":"focus",function(){v&&CKEDITOR.env.webkit&&(v=f._.previousActive&&f._.previousActive.equals(g.getActive()))&&null!=f._.previousScrollTop&&f._.previousScrollTop!=n.$.scrollTop&&(n.$.scrollTop=f._.previousScrollTop);f.unlockSelection(v);v=0},null,null,-1);n.attachListener(n,"mousedown",function(){v=0});if(CKEDITOR.env.ie||B)p?n.attachListener(n,"beforedeactivate",b,null,
null,-1):n.attachListener(f,"selectionCheck",b,null,null,-1),n.attachListener(n,CKEDITOR.env.webkit?"DOMFocusOut":"blur",function(){f.lockSelection(q);v=1},null,null,-1),n.attachListener(n,"mousedown",function(){v=0});if(CKEDITOR.env.ie&&!B){var N;n.attachListener(n,"mousedown",function(a){2==a.data.$.button&&((a=f.document.getSelection())&&a.getType()!=CKEDITOR.SELECTION_NONE||(N=f.window.getScrollPosition()))});n.attachListener(n,"mouseup",function(a){2==a.data.$.button&&N&&(f.document.$.documentElement.scrollLeft=
N.x,f.document.$.documentElement.scrollTop=N.y);N=null});if("BackCompat"!=g.$.compatMode){if(CKEDITOR.env.ie7Compat||CKEDITOR.env.ie6Compat){var G,x;l.on("mousedown",function(a){function b(a){a=a.data.$;if(G){var c=k.$.createTextRange();try{c.moveToPoint(a.clientX,a.clientY)}catch(d){}G.setEndPoint(0>x.compareEndPoints("StartToStart",c)?"EndToEnd":"StartToStart",c);G.select()}}function c(){l.removeListener("mousemove",b);h.removeListener("mouseup",c);l.removeListener("mouseup",c);G.select()}a=a.data;
if(a.getTarget().is("html")&&a.$.y<l.$.clientHeight&&a.$.x<l.$.clientWidth){G=k.$.createTextRange();try{G.moveToPoint(a.$.clientX,a.$.clientY)}catch(d){}x=G.duplicate();l.on("mousemove",b);h.on("mouseup",c);l.on("mouseup",c)}})}if(7<CKEDITOR.env.version&&11>CKEDITOR.env.version)l.on("mousedown",function(a){a.data.getTarget().is("html")&&(h.on("mouseup",d),l.on("mouseup",d))})}}n.attachListener(n,"selectionchange",a,f);n.attachListener(n,"keyup",e,f);n.attachListener(n,CKEDITOR.env.webkit?"DOMFocusIn":
"focus",function(){f.forceNextSelectionCheck();f.selectionChange(1)});if(B&&(CKEDITOR.env.webkit||CKEDITOR.env.gecko)){var r;n.attachListener(n,"mousedown",function(){r=1});n.attachListener(g.getDocumentElement(),"mouseup",function(){r&&e.call(f);r=0})}else n.attachListener(CKEDITOR.env.ie?n:g.getDocumentElement(),"mouseup",e,f);CKEDITOR.env.webkit&&n.attachListener(g,"keydown",function(a){switch(a.data.getKey()){case 13:case 33:case 34:case 35:case 36:case 37:case 39:case 8:case 45:case 46:m(n)}},
null,null,-1);n.attachListener(n,"keydown",c(f),null,null,-1)});f.on("setData",function(){f.unlockSelection();CKEDITOR.env.webkit&&d()});f.on("contentDomUnload",function(){f.unlockSelection()});if(CKEDITOR.env.ie9Compat)f.on("beforeDestroy",d,null,null,9);f.on("dataReady",function(){delete f._.fakeSelection;delete f._.hiddenSelectionContainer;f.selectionChange(1)});f.on("loadSnapshot",function(){var a=CKEDITOR.dom.walker.nodeType(CKEDITOR.NODE_ELEMENT),b=f.editable().getLast(a);b&&b.hasAttribute("data-cke-hidden-sel")&&
(b.remove(),CKEDITOR.env.gecko&&(a=f.editable().getFirst(a))&&a.is("br")&&a.getAttribute("_moz_editor_bogus_node")&&a.remove())},null,null,100);f.on("key",function(a){if("wysiwyg"==f.mode){var b=f.getSelection();if(b.isFake){var c=w[a.data.keyCode];if(c)return c({editor:f,selected:b.getSelectedElement(),selection:b,keyEvent:a})}}})});if(CKEDITOR.env.webkit)CKEDITOR.on("instanceReady",function(a){var b=a.editor;b.on("selectionChange",function(){var a=b.editable(),c=a.getCustomData("cke-fillingChar");
c&&(c.getCustomData("ready")?m(a):c.setCustomData("ready",1))},null,null,-1);b.on("beforeSetMode",function(){m(b.editable())},null,null,-1);b.on("getSnapshot",function(a){a.data&&(a.data=h(a.data))},b,null,20);b.on("toDataFormat",function(a){a.data.dataValue=h(a.data.dataValue)},null,null,0)});CKEDITOR.editor.prototype.selectionChange=function(b){(b?a:e).call(this)};CKEDITOR.editor.prototype.getSelection=function(a){return!this._.savedSelection&&!this._.fakeSelection||a?(a=this.editable())&&"wysiwyg"==
this.mode?new CKEDITOR.dom.selection(a):null:this._.savedSelection||this._.fakeSelection};CKEDITOR.editor.prototype.lockSelection=function(a){a=a||this.getSelection(1);return a.getType()!=CKEDITOR.SELECTION_NONE?(!a.isLocked&&a.lock(),this._.savedSelection=a,!0):!1};CKEDITOR.editor.prototype.unlockSelection=function(a){var b=this._.savedSelection;return b?(b.unlock(a),delete this._.savedSelection,!0):!1};CKEDITOR.editor.prototype.forceNextSelectionCheck=function(){delete this._.selectionPreviousPath};
CKEDITOR.dom.document.prototype.getSelection=function(){return new CKEDITOR.dom.selection(this)};CKEDITOR.dom.range.prototype.select=function(){var a=this.root instanceof CKEDITOR.editable?this.root.editor.getSelection():new CKEDITOR.dom.selection(this.root);a.selectRanges([this]);return a};CKEDITOR.SELECTION_NONE=1;CKEDITOR.SELECTION_TEXT=2;CKEDITOR.SELECTION_ELEMENT=3;CKEDITOR.dom.selection=function(a){if(a instanceof CKEDITOR.dom.selection){var b=a;a=a.root}var c=a instanceof CKEDITOR.dom.element;
this.rev=b?b.rev:B++;this.document=a instanceof CKEDITOR.dom.document?a:a.getDocument();this.root=c?a:this.document.getBody();this.isLocked=0;this._={cache:{}};if(b)return CKEDITOR.tools.extend(this._.cache,b._.cache),this.isFake=b.isFake,this.isLocked=b.isLocked,this;a=this.getNative();var d,f;if(a)if(a.getRangeAt)d=(f=a.rangeCount&&a.getRangeAt(0))&&new CKEDITOR.dom.node(f.commonAncestorContainer);else{try{f=a.createRange()}catch(e){}d=f&&CKEDITOR.dom.element.get(f.item&&f.item(0)||f.parentElement())}if(!d||
d.type!=CKEDITOR.NODE_ELEMENT&&d.type!=CKEDITOR.NODE_TEXT||!this.root.equals(d)&&!this.root.contains(d))this._.cache.type=CKEDITOR.SELECTION_NONE,this._.cache.startElement=null,this._.cache.selectedElement=null,this._.cache.selectedText="",this._.cache.ranges=new CKEDITOR.dom.rangeList;return this};var F={img:1,hr:1,li:1,table:1,tr:1,td:1,th:1,embed:1,object:1,ol:1,ul:1,a:1,input:1,form:1,select:1,textarea:1,button:1,fieldset:1,thead:1,tfoot:1};CKEDITOR.tools.extend(CKEDITOR.dom.selection,{_removeFillingCharSequenceString:h,
_createFillingCharSequenceNode:k,FILLING_CHAR_SEQUENCE:x});CKEDITOR.dom.selection.prototype={getNative:function(){return void 0!==this._.cache.nativeSel?this._.cache.nativeSel:this._.cache.nativeSel=p?this.document.$.selection:this.document.getWindow().$.getSelection()},getType:p?function(){var a=this._.cache;if(a.type)return a.type;var b=CKEDITOR.SELECTION_NONE;try{var c=this.getNative(),d=c.type;"Text"==d&&(b=CKEDITOR.SELECTION_TEXT);"Control"==d&&(b=CKEDITOR.SELECTION_ELEMENT);c.createRange().parentElement()&&
(b=CKEDITOR.SELECTION_TEXT)}catch(f){}return a.type=b}:function(){var a=this._.cache;if(a.type)return a.type;var b=CKEDITOR.SELECTION_TEXT,c=this.getNative();if(!c||!c.rangeCount)b=CKEDITOR.SELECTION_NONE;else if(1==c.rangeCount){var c=c.getRangeAt(0),d=c.startContainer;d==c.endContainer&&1==d.nodeType&&1==c.endOffset-c.startOffset&&F[d.childNodes[c.startOffset].nodeName.toLowerCase()]&&(b=CKEDITOR.SELECTION_ELEMENT)}return a.type=b},getRanges:function(){var a=p?function(){function a(b){return(new CKEDITOR.dom.node(b)).getIndex()}
var b=function(b,c){b=b.duplicate();b.collapse(c);var d=b.parentElement();if(!d.hasChildNodes())return{container:d,offset:0};for(var f=d.children,e,g,p=b.duplicate(),h=0,v=f.length-1,q=-1,k,n;h<=v;)if(q=Math.floor((h+v)/2),e=f[q],p.moveToElementText(e),k=p.compareEndPoints("StartToStart",b),0<k)v=q-1;else if(0>k)h=q+1;else return{container:d,offset:a(e)};if(-1==q||q==f.length-1&&0>k){p.moveToElementText(d);p.setEndPoint("StartToStart",b);p=p.text.replace(/(\r\n|\r)/g,"\n").length;f=d.childNodes;if(!p)return e=
f[f.length-1],e.nodeType!=CKEDITOR.NODE_TEXT?{container:d,offset:f.length}:{container:e,offset:e.nodeValue.length};for(d=f.length;0<p&&0<d;)g=f[--d],g.nodeType==CKEDITOR.NODE_TEXT&&(n=g,p-=g.nodeValue.length);return{container:n,offset:-p}}p.collapse(0<k?!0:!1);p.setEndPoint(0<k?"StartToStart":"EndToStart",b);p=p.text.replace(/(\r\n|\r)/g,"\n").length;if(!p)return{container:d,offset:a(e)+(0<k?0:1)};for(;0<p;)try{g=e[0<k?"previousSibling":"nextSibling"],g.nodeType==CKEDITOR.NODE_TEXT&&(p-=g.nodeValue.length,
n=g),e=g}catch(l){return{container:d,offset:a(e)}}return{container:n,offset:0<k?-p:n.nodeValue.length+p}};return function(){var a=this.getNative(),c=a&&a.createRange(),d=this.getType();if(!a)return[];if(d==CKEDITOR.SELECTION_TEXT)return a=new CKEDITOR.dom.range(this.root),d=b(c,!0),a.setStart(new CKEDITOR.dom.node(d.container),d.offset),d=b(c),a.setEnd(new CKEDITOR.dom.node(d.container),d.offset),a.endContainer.getPosition(a.startContainer)&CKEDITOR.POSITION_PRECEDING&&a.endOffset<=a.startContainer.getIndex()&&
a.collapse(),[a];if(d==CKEDITOR.SELECTION_ELEMENT){for(var d=[],f=0;f<c.length;f++){for(var e=c.item(f),g=e.parentNode,p=0,a=new CKEDITOR.dom.range(this.root);p<g.childNodes.length&&g.childNodes[p]!=e;p++);a.setStart(new CKEDITOR.dom.node(g),p);a.setEnd(new CKEDITOR.dom.node(g),p+1);d.push(a)}return d}return[]}}():function(){var a=[],b,c=this.getNative();if(!c)return a;for(var d=0;d<c.rangeCount;d++){var f=c.getRangeAt(d);b=new CKEDITOR.dom.range(this.root);b.setStart(new CKEDITOR.dom.node(f.startContainer),
f.startOffset);b.setEnd(new CKEDITOR.dom.node(f.endContainer),f.endOffset);a.push(b)}return a};return function(b){var c=this._.cache,d=c.ranges;d||(c.ranges=d=new CKEDITOR.dom.rangeList(a.call(this)));return b?f(new CKEDITOR.dom.rangeList(d.slice())):d}}(),getStartElement:function(){var a=this._.cache;if(void 0!==a.startElement)return a.startElement;var b;switch(this.getType()){case CKEDITOR.SELECTION_ELEMENT:return this.getSelectedElement();case CKEDITOR.SELECTION_TEXT:var c=this.getRanges()[0];
if(c){if(c.collapsed)b=c.startContainer,b.type!=CKEDITOR.NODE_ELEMENT&&(b=b.getParent());else{for(c.optimize();b=c.startContainer,c.startOffset==(b.getChildCount?b.getChildCount():b.getLength())&&!b.isBlockBoundary();)c.setStartAfter(b);b=c.startContainer;if(b.type!=CKEDITOR.NODE_ELEMENT)return b.getParent();if((b=b.getChild(c.startOffset))&&b.type==CKEDITOR.NODE_ELEMENT)for(c=b.getFirst();c&&c.type==CKEDITOR.NODE_ELEMENT;)b=c,c=c.getFirst();else b=c.startContainer}b=b.$}}return a.startElement=b?
new CKEDITOR.dom.element(b):null},getSelectedElement:function(){var a=this._.cache;if(void 0!==a.selectedElement)return a.selectedElement;var b=this,c=CKEDITOR.tools.tryThese(function(){return b.getNative().createRange().item(0)},function(){for(var a=b.getRanges()[0].clone(),c,d,f=2;f&&!((c=a.getEnclosedNode())&&c.type==CKEDITOR.NODE_ELEMENT&&F[c.getName()]&&(d=c));f--)a.shrink(CKEDITOR.SHRINK_ELEMENT);return d&&d.$});return a.selectedElement=c?new CKEDITOR.dom.element(c):null},getSelectedText:function(){var a=
this._.cache;if(void 0!==a.selectedText)return a.selectedText;var b=this.getNative(),b=p?"Control"==b.type?"":b.createRange().text:b.toString();return a.selectedText=b},lock:function(){this.getRanges();this.getStartElement();this.getSelectedElement();this.getSelectedText();this._.cache.nativeSel=null;this.isLocked=1},unlock:function(a){if(this.isLocked){if(a)var b=this.getSelectedElement(),c=!b&&this.getRanges(),d=this.isFake;this.isLocked=0;this.reset();a&&(a=b||c[0]&&c[0].getCommonAncestor())&&
a.getAscendant("body",1)&&(d?this.fake(b):b?this.selectElement(b):this.selectRanges(c))}},reset:function(){this._.cache={};this.isFake=0;var a=this.root.editor;if(a&&a._.fakeSelection)if(this.rev==a._.fakeSelection.rev){delete a._.fakeSelection;var b=a._.hiddenSelectionContainer;if(b){var c=a.checkDirty();a.fire("lockSnapshot");b.remove();a.fire("unlockSnapshot");!c&&a.resetDirty()}delete a._.hiddenSelectionContainer}else CKEDITOR.warn("selection-fake-reset");this.rev=B++},selectElement:function(a){var b=
new CKEDITOR.dom.range(this.root);b.setStartBefore(a);b.setEndAfter(a);this.selectRanges([b])},selectRanges:function(a){var b=this.root.editor,b=b&&b._.hiddenSelectionContainer;this.reset();if(b)for(var b=this.root,c,d=0;d<a.length;++d)c=a[d],c.endContainer.equals(b)&&(c.endOffset=Math.min(c.endOffset,b.getChildCount()));if(a.length)if(this.isLocked){var f=CKEDITOR.document.getActive();this.unlock();this.selectRanges(a);this.lock();f&&!f.equals(this.root)&&f.focus()}else{var e;a:{var g,h;if(1==a.length&&
!(h=a[0]).collapsed&&(e=h.getEnclosedNode())&&e.type==CKEDITOR.NODE_ELEMENT&&(h=h.clone(),h.shrink(CKEDITOR.SHRINK_ELEMENT,!0),(g=h.getEnclosedNode())&&g.type==CKEDITOR.NODE_ELEMENT&&(e=g),"false"==e.getAttribute("contenteditable")))break a;e=void 0}if(e)this.fake(e);else{if(p){h=CKEDITOR.dom.walker.whitespaces(!0);g=/\ufeff|\u00a0/;b={table:1,tbody:1,tr:1};1<a.length&&(e=a[a.length-1],a[0].setEnd(e.endContainer,e.endOffset));e=a[0];a=e.collapsed;var B,x,t;if((c=e.getEnclosedNode())&&c.type==CKEDITOR.NODE_ELEMENT&&
c.getName()in F&&(!c.is("a")||!c.getText()))try{t=c.$.createControlRange();t.addElement(c.$);t.select();return}catch(v){}if(e.startContainer.type==CKEDITOR.NODE_ELEMENT&&e.startContainer.getName()in b||e.endContainer.type==CKEDITOR.NODE_ELEMENT&&e.endContainer.getName()in b)e.shrink(CKEDITOR.NODE_ELEMENT,!0),a=e.collapsed;t=e.createBookmark();b=t.startNode;a||(f=t.endNode);t=e.document.$.body.createTextRange();t.moveToElementText(b.$);t.moveStart("character",1);f?(g=e.document.$.body.createTextRange(),
g.moveToElementText(f.$),t.setEndPoint("EndToEnd",g),t.moveEnd("character",-1)):(B=b.getNext(h),x=b.hasAscendant("pre"),B=!(B&&B.getText&&B.getText().match(g))&&(x||!b.hasPrevious()||b.getPrevious().is&&b.getPrevious().is("br")),x=e.document.createElement("span"),x.setHtml("\x26#65279;"),x.insertBefore(b),B&&e.document.createText("﻿").insertBefore(b));e.setStartBefore(b);b.remove();a?(B?(t.moveStart("character",-1),t.select(),e.document.$.selection.clear()):t.select(),e.moveToPosition(x,CKEDITOR.POSITION_BEFORE_START),
x.remove()):(e.setEndBefore(f),f.remove(),t.select())}else{f=this.getNative();if(!f)return;this.removeAllRanges();for(t=0;t<a.length;t++){if(t<a.length-1&&(B=a[t],x=a[t+1],g=B.clone(),g.setStart(B.endContainer,B.endOffset),g.setEnd(x.startContainer,x.startOffset),!g.collapsed&&(g.shrink(CKEDITOR.NODE_ELEMENT,!0),e=g.getCommonAncestor(),g=g.getEnclosedNode(),e.isReadOnly()||g&&g.isReadOnly()))){x.setStart(B.startContainer,B.startOffset);a.splice(t--,1);continue}e=a[t];x=this.document.$.createRange();
e.collapsed&&CKEDITOR.env.webkit&&l(e)&&(g=k(this.root),e.insertNode(g),(B=g.getNext())&&!g.getPrevious()&&B.type==CKEDITOR.NODE_ELEMENT&&"br"==B.getName()?(m(this.root),e.moveToPosition(B,CKEDITOR.POSITION_BEFORE_START)):e.moveToPosition(g,CKEDITOR.POSITION_AFTER_END));x.setStart(e.startContainer.$,e.startOffset);try{x.setEnd(e.endContainer.$,e.endOffset)}catch(q){if(0<=q.toString().indexOf("NS_ERROR_ILLEGAL_VALUE"))e.collapse(1),x.setEnd(e.endContainer.$,e.endOffset);else throw q;}f.addRange(x)}}this.reset();
this.root.fire("selectionchange")}}},fake:function(a,c){var d=this.root.editor;void 0===c&&a.hasAttribute("aria-label")&&(c=a.getAttribute("aria-label"));this.reset();b(d,c);var f=this._.cache,e=new CKEDITOR.dom.range(this.root);e.setStartBefore(a);e.setEndAfter(a);f.ranges=new CKEDITOR.dom.rangeList(e);f.selectedElement=f.startElement=a;f.type=CKEDITOR.SELECTION_ELEMENT;f.selectedText=f.nativeSel=null;this.isFake=1;this.rev=B++;d._.fakeSelection=this;this.root.fire("selectionchange")},isHidden:function(){var a=
this.getCommonAncestor();a&&a.type==CKEDITOR.NODE_TEXT&&(a=a.getParent());return!(!a||!a.data("cke-hidden-sel"))},createBookmarks:function(a){a=this.getRanges().createBookmarks(a);this.isFake&&(a.isFake=1);return a},createBookmarks2:function(a){a=this.getRanges().createBookmarks2(a);this.isFake&&(a.isFake=1);return a},selectBookmarks:function(a){for(var b=[],c,d=0;d<a.length;d++){var f=new CKEDITOR.dom.range(this.root);f.moveToBookmark(a[d]);b.push(f)}a.isFake&&(c=b[0].getEnclosedNode(),c&&c.type==
CKEDITOR.NODE_ELEMENT||(CKEDITOR.warn("selection-not-fake"),a.isFake=0));a.isFake?this.fake(c):this.selectRanges(b);return this},getCommonAncestor:function(){var a=this.getRanges();return a.length?a[0].startContainer.getCommonAncestor(a[a.length-1].endContainer):null},scrollIntoView:function(){this.type!=CKEDITOR.SELECTION_NONE&&this.getRanges()[0].scrollIntoView()},removeAllRanges:function(){if(this.getType()!=CKEDITOR.SELECTION_NONE){var a=this.getNative();try{a&&a[p?"empty":"removeAllRanges"]()}catch(b){}this.reset()}}}}(),
"use strict",CKEDITOR.STYLE_BLOCK=1,CKEDITOR.STYLE_INLINE=2,CKEDITOR.STYLE_OBJECT=3,function(){function a(a,b){for(var c,d;(a=a.getParent())&&!a.equals(b);)if(a.getAttribute("data-nostyle"))c=a;else if(!d){var f=a.getAttribute("contentEditable");"false"==f?c=a:"true"==f&&(d=1)}return c}function e(a,b,c,d){return(a.getPosition(b)|d)==d&&(!c.childRule||c.childRule(a))}function d(b){var c=b.document;if(b.collapsed)c=H(this,c),b.insertNode(c),b.moveToPosition(c,CKEDITOR.POSITION_BEFORE_END);else{var f=
this.element,g=this._.definition,p,h=g.ignoreReadonly,k=h||g.includeReadonly;null==k&&(k=b.root.getCustomData("cke_includeReadonly"));var n=CKEDITOR.dtd[f];n||(p=!0,n=CKEDITOR.dtd.span);b.enlarge(CKEDITOR.ENLARGE_INLINE,1);b.trim();var m=b.createBookmark(),B=m.startNode,E=m.endNode,A=B,M;if(!h){var x=b.getCommonAncestor(),h=a(B,x),x=a(E,x);h&&(A=h.getNextSourceNode(!0));x&&(E=x)}for(A.getPosition(E)==CKEDITOR.POSITION_FOLLOWING&&(A=0);A;){h=!1;if(A.equals(E))A=null,h=!0;else{var u=A.type==CKEDITOR.NODE_ELEMENT?
A.getName():null,x=u&&"false"==A.getAttribute("contentEditable"),y=u&&A.getAttribute("data-nostyle");if(u&&A.data("cke-bookmark")){A=A.getNextSourceNode(!0);continue}if(x&&k&&CKEDITOR.dtd.$block[u])for(var r=A,U=l(r),w=void 0,z=U.length,C=0,r=z&&new CKEDITOR.dom.range(r.getDocument());C<z;++C){var w=U[C],D=CKEDITOR.filter.instances[w.data("cke-filter")];if(D?D.check(this):1)r.selectNodeContents(w),d.call(this,r)}U=u?!n[u]||y?0:x&&!k?0:e(A,E,g,S):1;if(U)if(w=A.getParent(),U=g,z=f,C=p,!w||!(w.getDtd()||
CKEDITOR.dtd.span)[z]&&!C||U.parentRule&&!U.parentRule(w))h=!0;else{if(M||u&&CKEDITOR.dtd.$removeEmpty[u]&&(A.getPosition(E)|S)!=S||(M=b.clone(),M.setStartBefore(A)),u=A.type,u==CKEDITOR.NODE_TEXT||x||u==CKEDITOR.NODE_ELEMENT&&!A.getChildCount()){for(var u=A,O;(h=!u.getNext(L))&&(O=u.getParent(),n[O.getName()])&&e(O,B,g,v);)u=O;M.setEndAfter(u)}}else h=!0;A=A.getNextSourceNode(y||x)}if(h&&M&&!M.collapsed){for(var h=H(this,c),x=h.hasAttributes(),y=M.getCommonAncestor(),u={},U={},w={},z={},F,K,J;h&&
y;){if(y.getName()==f){for(F in g.attributes)!z[F]&&(J=y.getAttribute(K))&&(h.getAttribute(F)==J?U[F]=1:z[F]=1);for(K in g.styles)!w[K]&&(J=y.getStyle(K))&&(h.getStyle(K)==J?u[K]=1:w[K]=1)}y=y.getParent()}for(F in U)h.removeAttribute(F);for(K in u)h.removeStyle(K);x&&!h.hasAttributes()&&(h=null);h?(M.extractContents().appendTo(h),M.insertNode(h),t.call(this,h),h.mergeSiblings(),CKEDITOR.env.ie||h.$.normalize()):(h=new CKEDITOR.dom.element("span"),M.extractContents().appendTo(h),M.insertNode(h),t.call(this,
h),h.remove(!0));M=null}}b.moveToBookmark(m);b.shrink(CKEDITOR.SHRINK_TEXT);b.shrink(CKEDITOR.NODE_ELEMENT,!0)}}function g(a){function b(){for(var a=new CKEDITOR.dom.elementPath(d.getParent()),c=new CKEDITOR.dom.elementPath(v.getParent()),f=null,e=null,g=0;g<a.elements.length;g++){var q=a.elements[g];if(q==a.block||q==a.blockLimit)break;E.checkElementRemovable(q,!0)&&(f=q)}for(g=0;g<c.elements.length;g++){q=c.elements[g];if(q==c.block||q==c.blockLimit)break;E.checkElementRemovable(q,!0)&&(e=q)}e&&
v.breakParent(e);f&&d.breakParent(f)}a.enlarge(CKEDITOR.ENLARGE_INLINE,1);var c=a.createBookmark(),d=c.startNode;if(a.collapsed){for(var f=new CKEDITOR.dom.elementPath(d.getParent(),a.root),e,g=0,p;g<f.elements.length&&(p=f.elements[g])&&p!=f.block&&p!=f.blockLimit;g++)if(this.checkElementRemovable(p)){var h;a.collapsed&&(a.checkBoundaryOfElement(p,CKEDITOR.END)||(h=a.checkBoundaryOfElement(p,CKEDITOR.START)))?(e=p,e.match=h?"start":"end"):(p.mergeSiblings(),p.is(this.element)?x.call(this,p):u(p,
n(this)[p.getName()]))}if(e){p=d;for(g=0;;g++){h=f.elements[g];if(h.equals(e))break;else if(h.match)continue;else h=h.clone();h.append(p);p=h}p["start"==e.match?"insertBefore":"insertAfter"](e)}}else{var v=c.endNode,E=this;b();for(f=d;!f.equals(v);)e=f.getNextSourceNode(),f.type==CKEDITOR.NODE_ELEMENT&&this.checkElementRemovable(f)&&(f.getName()==this.element?x.call(this,f):u(f,n(this)[f.getName()]),e.type==CKEDITOR.NODE_ELEMENT&&e.contains(d)&&(b(),e=d.getNext())),f=e}a.moveToBookmark(c);a.shrink(CKEDITOR.NODE_ELEMENT,
!0)}function l(a){var b=[];a.forEach(function(a){if("true"==a.getAttribute("contenteditable"))return b.push(a),!1},CKEDITOR.NODE_ELEMENT,!0);return b}function k(a){var b=a.getEnclosedNode()||a.getCommonAncestor(!1,!0);(a=(new CKEDITOR.dom.elementPath(b,a.root)).contains(this.element,1))&&!a.isReadOnly()&&w(a,this)}function m(a){var b=a.getCommonAncestor(!0,!0);if(a=(new CKEDITOR.dom.elementPath(b,a.root)).contains(this.element,1)){var b=this._.definition,c=b.attributes;if(c)for(var d in c)a.removeAttribute(d,
c[d]);if(b.styles)for(var f in b.styles)b.styles.hasOwnProperty(f)&&a.removeStyle(f)}}function h(a){var b=a.createBookmark(!0),d=a.createIterator();d.enforceRealBlocks=!0;this._.enterMode&&(d.enlargeBr=this._.enterMode!=CKEDITOR.ENTER_BR);for(var f,e=a.document,g;f=d.getNextParagraph();)!f.isReadOnly()&&(d.activeFilter?d.activeFilter.check(this):1)&&(g=H(this,e,f),c(f,g));a.moveToBookmark(b)}function b(a){var b=a.createBookmark(1),d=a.createIterator();d.enforceRealBlocks=!0;d.enlargeBr=this._.enterMode!=
CKEDITOR.ENTER_BR;for(var f,e;f=d.getNextParagraph();)this.checkElementRemovable(f)&&(f.is("pre")?((e=this._.enterMode==CKEDITOR.ENTER_BR?null:a.document.createElement(this._.enterMode==CKEDITOR.ENTER_P?"p":"div"))&&f.copyAttributes(e),c(f,e)):x.call(this,f));a.moveToBookmark(b)}function c(a,b){var c=!b;c&&(b=a.getDocument().createElement("div"),a.copyAttributes(b));var d=b&&b.is("pre"),e=a.is("pre"),g=!d&&e;if(d&&!e){e=b;(g=a.getBogus())&&g.remove();g=a.getHtml();g=p(g,/(?:^[ \t\n\r]+)|(?:[ \t\n\r]+$)/g,
"");g=g.replace(/[ \t\r\n]*(<br[^>]*>)[ \t\r\n]*/gi,"$1");g=g.replace(/([ \t\n\r]+|&nbsp;)/g," ");g=g.replace(/<br\b[^>]*>/gi,"\n");if(CKEDITOR.env.ie){var h=a.getDocument().createElement("div");h.append(e);e.$.outerHTML="\x3cpre\x3e"+g+"\x3c/pre\x3e";e.copyAttributes(h.getFirst());e=h.getFirst().remove()}else e.setHtml(g);b=e}else g?b=B(c?[a.getHtml()]:f(a),b):a.moveChildren(b);b.replace(a);if(d){var c=b,v;(v=c.getPrevious(O))&&v.type==CKEDITOR.NODE_ELEMENT&&v.is("pre")&&(d=p(v.getHtml(),/\n$/,"")+
"\n\n"+p(c.getHtml(),/^\n/,""),CKEDITOR.env.ie?c.$.outerHTML="\x3cpre\x3e"+d+"\x3c/pre\x3e":c.setHtml(d),v.remove())}else c&&y(b)}function f(a){var b=[];p(a.getOuterHtml(),/(\S\s*)\n(?:\s|(<span[^>]+data-cke-bookmark.*?\/span>))*\n(?!$)/gi,function(a,b,c){return b+"\x3c/pre\x3e"+c+"\x3cpre\x3e"}).replace(/<pre\b.*?>([\s\S]*?)<\/pre>/gi,function(a,c){b.push(c)});return b}function p(a,b,c){var d="",f="";a=a.replace(/(^<span[^>]+data-cke-bookmark.*?\/span>)|(<span[^>]+data-cke-bookmark.*?\/span>$)/gi,
function(a,b,c){b&&(d=b);c&&(f=c);return""});return d+a.replace(b,c)+f}function B(a,b){var c;1<a.length&&(c=new CKEDITOR.dom.documentFragment(b.getDocument()));for(var d=0;d<a.length;d++){var f=a[d],f=f.replace(/(\r\n|\r)/g,"\n"),f=p(f,/^[ \t]*\n/,""),f=p(f,/\n$/,""),f=p(f,/^[ \t]+|[ \t]+$/g,function(a,b){return 1==a.length?"\x26nbsp;":b?" "+CKEDITOR.tools.repeat("\x26nbsp;",a.length-1):CKEDITOR.tools.repeat("\x26nbsp;",a.length-1)+" "}),f=f.replace(/\n/g,"\x3cbr\x3e"),f=f.replace(/[ \t]{2,}/g,function(a){return CKEDITOR.tools.repeat("\x26nbsp;",
a.length-1)+" "});if(c){var e=b.clone();e.setHtml(f);c.append(e)}else b.setHtml(f)}return c||b}function x(a,b){var c=this._.definition,d=c.attributes,c=c.styles,f=n(this)[a.getName()],e=CKEDITOR.tools.isEmpty(d)&&CKEDITOR.tools.isEmpty(c),g;for(g in d)if("class"!=g&&!this._.definition.fullMatch||a.getAttribute(g)==r(g,d[g]))b&&"data-"==g.slice(0,5)||(e=a.hasAttribute(g),a.removeAttribute(g));for(var p in c)this._.definition.fullMatch&&a.getStyle(p)!=r(p,c[p],!0)||(e=e||!!a.getStyle(p),a.removeStyle(p));
u(a,f,z[a.getName()]);e&&(this._.definition.alwaysRemoveElement?y(a,1):!CKEDITOR.dtd.$block[a.getName()]||this._.enterMode==CKEDITOR.ENTER_BR&&!a.hasAttributes()?y(a):a.renameNode(this._.enterMode==CKEDITOR.ENTER_P?"p":"div"))}function t(a){for(var b=n(this),c=a.getElementsByTag(this.element),d,f=c.count();0<=--f;)d=c.getItem(f),d.isReadOnly()||x.call(this,d,!0);for(var e in b)if(e!=this.element)for(c=a.getElementsByTag(e),f=c.count()-1;0<=f;f--)d=c.getItem(f),d.isReadOnly()||u(d,b[e])}function u(a,
b,c){if(b=b&&b.attributes)for(var d=0;d<b.length;d++){var f=b[d][0],e;if(e=a.getAttribute(f)){var g=b[d][1];(null===g||g.test&&g.test(e)||"string"==typeof g&&e==g)&&a.removeAttribute(f)}}c||y(a)}function y(a,b){if(!a.hasAttributes()||b)if(CKEDITOR.dtd.$block[a.getName()]){var c=a.getPrevious(O),d=a.getNext(O);!c||c.type!=CKEDITOR.NODE_TEXT&&c.isBlockBoundary({br:1})||a.append("br",1);!d||d.type!=CKEDITOR.NODE_TEXT&&d.isBlockBoundary({br:1})||a.append("br");a.remove(!0)}else c=a.getFirst(),d=a.getLast(),
a.remove(!0),c&&(c.type==CKEDITOR.NODE_ELEMENT&&c.mergeSiblings(),d&&!c.equals(d)&&d.type==CKEDITOR.NODE_ELEMENT&&d.mergeSiblings())}function H(a,b,c){var d;d=a.element;"*"==d&&(d="span");d=new CKEDITOR.dom.element(d,b);c&&c.copyAttributes(d);d=w(d,a);b.getCustomData("doc_processing_style")&&d.hasAttribute("id")?d.removeAttribute("id"):b.setCustomData("doc_processing_style",1);return d}function w(a,b){var c=b._.definition,d=c.attributes,c=CKEDITOR.style.getStyleText(c);if(d)for(var f in d)a.setAttribute(f,
d[f]);c&&a.setAttribute("style",c);return a}function F(a,b){for(var c in a)a[c]=a[c].replace(P,function(a,c){return b[c]})}function n(a){if(a._.overrides)return a._.overrides;var b=a._.overrides={},c=a._.definition.overrides;if(c){CKEDITOR.tools.isArray(c)||(c=[c]);for(var d=0;d<c.length;d++){var f=c[d],e,g;"string"==typeof f?e=f.toLowerCase():(e=f.element?f.element.toLowerCase():a.element,g=f.attributes);f=b[e]||(b[e]={});if(g){var f=f.attributes=f.attributes||[],p;for(p in g)f.push([p.toLowerCase(),
g[p]])}}}return b}function r(a,b,c){var d=new CKEDITOR.dom.element("span");d[c?"setStyle":"setAttribute"](a,b);return d[c?"getStyle":"getAttribute"](a)}function C(a,b){function c(a,b){return"font-family"==b.toLowerCase()?a.replace(/["']/g,""):a}"string"==typeof a&&(a=CKEDITOR.tools.parseCssText(a));"string"==typeof b&&(b=CKEDITOR.tools.parseCssText(b,!0));for(var d in a)if(!(d in b)||c(b[d],d)!=c(a[d],d)&&"inherit"!=a[d]&&"inherit"!=b[d])return!1;return!0}function D(a,b,c){var d=a.document,f=a.getRanges();
b=b?this.removeFromRange:this.applyToRange;for(var e,g=f.createIterator();e=g.getNextRange();)b.call(this,e,c);a.selectRanges(f);d.removeCustomData("doc_processing_style")}var z={address:1,div:1,h1:1,h2:1,h3:1,h4:1,h5:1,h6:1,p:1,pre:1,section:1,header:1,footer:1,nav:1,article:1,aside:1,figure:1,dialog:1,hgroup:1,time:1,meter:1,menu:1,command:1,keygen:1,output:1,progress:1,details:1,datagrid:1,datalist:1},K={a:1,blockquote:1,embed:1,hr:1,img:1,li:1,object:1,ol:1,table:1,td:1,tr:1,th:1,ul:1,dl:1,dt:1,
dd:1,form:1,audio:1,video:1},J=/\s*(?:;\s*|$)/,P=/#\((.+?)\)/g,L=CKEDITOR.dom.walker.bookmark(0,1),O=CKEDITOR.dom.walker.whitespaces(1);CKEDITOR.style=function(a,b){if("string"==typeof a.type)return new CKEDITOR.style.customHandlers[a.type](a);var c=a.attributes;c&&c.style&&(a.styles=CKEDITOR.tools.extend({},a.styles,CKEDITOR.tools.parseCssText(c.style)),delete c.style);b&&(a=CKEDITOR.tools.clone(a),F(a.attributes,b),F(a.styles,b));c=this.element=a.element?"string"==typeof a.element?a.element.toLowerCase():
a.element:"*";this.type=a.type||(z[c]?CKEDITOR.STYLE_BLOCK:K[c]?CKEDITOR.STYLE_OBJECT:CKEDITOR.STYLE_INLINE);"object"==typeof this.element&&(this.type=CKEDITOR.STYLE_OBJECT);this._={definition:a}};CKEDITOR.style.prototype={apply:function(a){if(a instanceof CKEDITOR.dom.document)return D.call(this,a.getSelection());if(this.checkApplicable(a.elementPath(),a)){var b=this._.enterMode;b||(this._.enterMode=a.activeEnterMode);D.call(this,a.getSelection(),0,a);this._.enterMode=b}},remove:function(a){if(a instanceof
CKEDITOR.dom.document)return D.call(this,a.getSelection(),1);if(this.checkApplicable(a.elementPath(),a)){var b=this._.enterMode;b||(this._.enterMode=a.activeEnterMode);D.call(this,a.getSelection(),1,a);this._.enterMode=b}},applyToRange:function(a){this.applyToRange=this.type==CKEDITOR.STYLE_INLINE?d:this.type==CKEDITOR.STYLE_BLOCK?h:this.type==CKEDITOR.STYLE_OBJECT?k:null;return this.applyToRange(a)},removeFromRange:function(a){this.removeFromRange=this.type==CKEDITOR.STYLE_INLINE?g:this.type==CKEDITOR.STYLE_BLOCK?
b:this.type==CKEDITOR.STYLE_OBJECT?m:null;return this.removeFromRange(a)},applyToObject:function(a){w(a,this)},checkActive:function(a,b){switch(this.type){case CKEDITOR.STYLE_BLOCK:return this.checkElementRemovable(a.block||a.blockLimit,!0,b);case CKEDITOR.STYLE_OBJECT:case CKEDITOR.STYLE_INLINE:for(var c=a.elements,d=0,f;d<c.length;d++)if(f=c[d],this.type!=CKEDITOR.STYLE_INLINE||f!=a.block&&f!=a.blockLimit){if(this.type==CKEDITOR.STYLE_OBJECT){var e=f.getName();if(!("string"==typeof this.element?
e==this.element:e in this.element))continue}if(this.checkElementRemovable(f,!0,b))return!0}}return!1},checkApplicable:function(a,b,c){b&&b instanceof CKEDITOR.filter&&(c=b);if(c&&!c.check(this))return!1;switch(this.type){case CKEDITOR.STYLE_OBJECT:return!!a.contains(this.element);case CKEDITOR.STYLE_BLOCK:return!!a.blockLimit.getDtd()[this.element]}return!0},checkElementMatch:function(a,b){var c=this._.definition;if(!a||!c.ignoreReadonly&&a.isReadOnly())return!1;var d=a.getName();if("string"==typeof this.element?
d==this.element:d in this.element){if(!b&&!a.hasAttributes())return!0;if(d=c._AC)c=d;else{var d={},f=0,e=c.attributes;if(e)for(var g in e)f++,d[g]=e[g];if(g=CKEDITOR.style.getStyleText(c))d.style||f++,d.style=g;d._length=f;c=c._AC=d}if(c._length){for(var p in c)if("_length"!=p)if(d=a.getAttribute(p)||"","style"==p?C(c[p],d):c[p]==d){if(!b)return!0}else if(b)return!1;if(b)return!0}else return!0}return!1},checkElementRemovable:function(a,b,c){if(this.checkElementMatch(a,b,c))return!0;if(b=n(this)[a.getName()]){var d;
if(!(b=b.attributes))return!0;for(c=0;c<b.length;c++)if(d=b[c][0],d=a.getAttribute(d)){var f=b[c][1];if(null===f)return!0;if("string"==typeof f){if(d==f)return!0}else if(f.test(d))return!0}}return!1},buildPreview:function(a){var b=this._.definition,c=[],d=b.element;"bdo"==d&&(d="span");var c=["\x3c",d],f=b.attributes;if(f)for(var e in f)c.push(" ",e,'\x3d"',f[e],'"');(f=CKEDITOR.style.getStyleText(b))&&c.push(' style\x3d"',f,'"');c.push("\x3e",a||b.name,"\x3c/",d,"\x3e");return c.join("")},getDefinition:function(){return this._.definition}};
CKEDITOR.style.getStyleText=function(a){var b=a._ST;if(b)return b;var b=a.styles,c=a.attributes&&a.attributes.style||"",d="";c.length&&(c=c.replace(J,";"));for(var f in b){var e=b[f],g=(f+":"+e).replace(J,";");"inherit"==e?d+=g:c+=g}c.length&&(c=CKEDITOR.tools.normalizeCssText(c,!0));return a._ST=c+d};CKEDITOR.style.customHandlers={};CKEDITOR.style.addCustomHandler=function(a){var b=function(a){this._={definition:a};this.setup&&this.setup(a)};b.prototype=CKEDITOR.tools.extend(CKEDITOR.tools.prototypedCopy(CKEDITOR.style.prototype),
{assignedTo:CKEDITOR.STYLE_OBJECT},a,!0);return this.customHandlers[a.type]=b};var S=CKEDITOR.POSITION_PRECEDING|CKEDITOR.POSITION_IDENTICAL|CKEDITOR.POSITION_IS_CONTAINED,v=CKEDITOR.POSITION_FOLLOWING|CKEDITOR.POSITION_IDENTICAL|CKEDITOR.POSITION_IS_CONTAINED}(),CKEDITOR.styleCommand=function(a,e){this.requiredContent=this.allowedContent=this.style=a;CKEDITOR.tools.extend(this,e,!0)},CKEDITOR.styleCommand.prototype.exec=function(a){a.focus();this.state==CKEDITOR.TRISTATE_OFF?a.applyStyle(this.style):
this.state==CKEDITOR.TRISTATE_ON&&a.removeStyle(this.style)},CKEDITOR.stylesSet=new CKEDITOR.resourceManager("","stylesSet"),CKEDITOR.addStylesSet=CKEDITOR.tools.bind(CKEDITOR.stylesSet.add,CKEDITOR.stylesSet),CKEDITOR.loadStylesSet=function(a,e,d){CKEDITOR.stylesSet.addExternal(a,e,"");CKEDITOR.stylesSet.load(a,d)},CKEDITOR.tools.extend(CKEDITOR.editor.prototype,{attachStyleStateChange:function(a,e){var d=this._.styleStateChangeCallbacks;d||(d=this._.styleStateChangeCallbacks=[],this.on("selectionChange",
function(a){for(var e=0;e<d.length;e++){var k=d[e],m=k.style.checkActive(a.data.path,this)?CKEDITOR.TRISTATE_ON:CKEDITOR.TRISTATE_OFF;k.fn.call(this,m)}}));d.push({style:a,fn:e})},applyStyle:function(a){a.apply(this)},removeStyle:function(a){a.remove(this)},getStylesSet:function(a){if(this._.stylesDefinitions)a(this._.stylesDefinitions);else{var e=this,d=e.config.stylesCombo_stylesSet||e.config.stylesSet;if(!1===d)a(null);else if(d instanceof Array)e._.stylesDefinitions=d,a(d);else{d||(d="default");
var d=d.split(":"),g=d[0];CKEDITOR.stylesSet.addExternal(g,d[1]?d.slice(1).join(":"):CKEDITOR.getUrl("styles.js"),"");CKEDITOR.stylesSet.load(g,function(d){e._.stylesDefinitions=d[g];a(e._.stylesDefinitions)})}}}}),CKEDITOR.dom.comment=function(a,e){"string"==typeof a&&(a=(e?e.$:document).createComment(a));CKEDITOR.dom.domObject.call(this,a)},CKEDITOR.dom.comment.prototype=new CKEDITOR.dom.node,CKEDITOR.tools.extend(CKEDITOR.dom.comment.prototype,{type:CKEDITOR.NODE_COMMENT,getOuterHtml:function(){return"\x3c!--"+
this.$.nodeValue+"--\x3e"}}),"use strict",function(){var a={},e={},d;for(d in CKEDITOR.dtd.$blockLimit)d in CKEDITOR.dtd.$list||(a[d]=1);for(d in CKEDITOR.dtd.$block)d in CKEDITOR.dtd.$blockLimit||d in CKEDITOR.dtd.$empty||(e[d]=1);CKEDITOR.dom.elementPath=function(d,l){var k=null,m=null,h=[],b=d,c;l=l||d.getDocument().getBody();do if(b.type==CKEDITOR.NODE_ELEMENT){h.push(b);if(!this.lastElement&&(this.lastElement=b,b.is(CKEDITOR.dtd.$object)||"false"==b.getAttribute("contenteditable")))continue;
if(b.equals(l))break;if(!m&&(c=b.getName(),"true"==b.getAttribute("contenteditable")?m=b:!k&&e[c]&&(k=b),a[c])){if(c=!k&&"div"==c){a:{c=b.getChildren();for(var f=0,p=c.count();f<p;f++){var B=c.getItem(f);if(B.type==CKEDITOR.NODE_ELEMENT&&CKEDITOR.dtd.$block[B.getName()]){c=!0;break a}}c=!1}c=!c}c?k=b:m=b}}while(b=b.getParent());m||(m=l);this.block=k;this.blockLimit=m;this.root=l;this.elements=h}}(),CKEDITOR.dom.elementPath.prototype={compare:function(a){var e=this.elements;a=a&&a.elements;if(!a||
e.length!=a.length)return!1;for(var d=0;d<e.length;d++)if(!e[d].equals(a[d]))return!1;return!0},contains:function(a,e,d){var g;"string"==typeof a&&(g=function(d){return d.getName()==a});a instanceof CKEDITOR.dom.element?g=function(d){return d.equals(a)}:CKEDITOR.tools.isArray(a)?g=function(d){return-1<CKEDITOR.tools.indexOf(a,d.getName())}:"function"==typeof a?g=a:"object"==typeof a&&(g=function(d){return d.getName()in a});var l=this.elements,k=l.length;e&&k--;d&&(l=Array.prototype.slice.call(l,0),
l.reverse());for(e=0;e<k;e++)if(g(l[e]))return l[e];return null},isContextFor:function(a){var e;return a in CKEDITOR.dtd.$block?(e=this.contains(CKEDITOR.dtd.$intermediate)||this.root.equals(this.block)&&this.block||this.blockLimit,!!e.getDtd()[a]):!0},direction:function(){return(this.block||this.blockLimit||this.root).getDirection(1)}},CKEDITOR.dom.text=function(a,e){"string"==typeof a&&(a=(e?e.$:document).createTextNode(a));this.$=a},CKEDITOR.dom.text.prototype=new CKEDITOR.dom.node,CKEDITOR.tools.extend(CKEDITOR.dom.text.prototype,
{type:CKEDITOR.NODE_TEXT,getLength:function(){return this.$.nodeValue.length},getText:function(){return this.$.nodeValue},setText:function(a){this.$.nodeValue=a},split:function(a){var e=this.$.parentNode,d=e.childNodes.length,g=this.getLength(),l=this.getDocument(),k=new CKEDITOR.dom.text(this.$.splitText(a),l);e.childNodes.length==d&&(a>=g?(k=l.createText(""),k.insertAfter(this)):(a=l.createText(""),a.insertAfter(k),a.remove()));return k},substring:function(a,e){return"number"!=typeof e?this.$.nodeValue.substr(a):
this.$.nodeValue.substring(a,e)}}),function(){function a(a,e,l){var k=a.serializable,m=e[l?"endContainer":"startContainer"],h=l?"endOffset":"startOffset",b=k?e.document.getById(a.startNode):a.startNode;a=k?e.document.getById(a.endNode):a.endNode;m.equals(b.getPrevious())?(e.startOffset=e.startOffset-m.getLength()-a.getPrevious().getLength(),m=a.getNext()):m.equals(a.getPrevious())&&(e.startOffset-=m.getLength(),m=a.getNext());m.equals(b.getParent())&&e[h]++;m.equals(a.getParent())&&e[h]++;e[l?"endContainer":
"startContainer"]=m;return e}CKEDITOR.dom.rangeList=function(a){if(a instanceof CKEDITOR.dom.rangeList)return a;a?a instanceof CKEDITOR.dom.range&&(a=[a]):a=[];return CKEDITOR.tools.extend(a,e)};var e={createIterator:function(){var a=this,e=CKEDITOR.dom.walker.bookmark(),l=[],k;return{getNextRange:function(m){k=void 0===k?0:k+1;var h=a[k];if(h&&1<a.length){if(!k)for(var b=a.length-1;0<=b;b--)l.unshift(a[b].createBookmark(!0));if(m)for(var c=0;a[k+c+1];){var f=h.document;m=0;b=f.getById(l[c].endNode);
for(f=f.getById(l[c+1].startNode);;){b=b.getNextSourceNode(!1);if(f.equals(b))m=1;else if(e(b)||b.type==CKEDITOR.NODE_ELEMENT&&b.isBlockBoundary())continue;break}if(!m)break;c++}for(h.moveToBookmark(l.shift());c--;)b=a[++k],b.moveToBookmark(l.shift()),h.setEnd(b.endContainer,b.endOffset)}return h}}},createBookmarks:function(d){for(var e=[],l,k=0;k<this.length;k++){e.push(l=this[k].createBookmark(d,!0));for(var m=k+1;m<this.length;m++)this[m]=a(l,this[m]),this[m]=a(l,this[m],!0)}return e},createBookmarks2:function(a){for(var e=
[],l=0;l<this.length;l++)e.push(this[l].createBookmark2(a));return e},moveToBookmarks:function(a){for(var e=0;e<this.length;e++)this[e].moveToBookmark(a[e])}}}(),function(){function a(){return CKEDITOR.getUrl(CKEDITOR.skinName.split(",")[1]||"skins/"+CKEDITOR.skinName.split(",")[0]+"/")}function e(b){var d=CKEDITOR.skin["ua_"+b],e=CKEDITOR.env;if(d)for(var d=d.split(",").sort(function(a,b){return a>b?-1:1}),g=0,h;g<d.length;g++)if(h=d[g],e.ie&&(h.replace(/^ie/,"")==e.version||e.quirks&&"iequirks"==
h)&&(h="ie"),e[h]){b+="_"+d[g];break}return CKEDITOR.getUrl(a()+b+".css")}function d(a,b){k[a]||(CKEDITOR.document.appendStyleSheet(e(a)),k[a]=1);b&&b()}function g(a){var b=a.getById(m);b||(b=a.getHead().append("style"),b.setAttribute("id",m),b.setAttribute("type","text/css"));return b}function l(a,b,d){var e,g,h;if(CKEDITOR.env.webkit)for(b=b.split("}").slice(0,-1),g=0;g<b.length;g++)b[g]=b[g].split("{");for(var k=0;k<a.length;k++)if(CKEDITOR.env.webkit)for(g=0;g<b.length;g++){h=b[g][1];for(e=0;e<
d.length;e++)h=h.replace(d[e][0],d[e][1]);a[k].$.sheet.addRule(b[g][0],h)}else{h=b;for(e=0;e<d.length;e++)h=h.replace(d[e][0],d[e][1]);CKEDITOR.env.ie&&11>CKEDITOR.env.version?a[k].$.styleSheet.cssText+=h:a[k].$.innerHTML+=h}}var k={};CKEDITOR.skin={path:a,loadPart:function(b,f){CKEDITOR.skin.name!=CKEDITOR.skinName.split(",")[0]?CKEDITOR.scriptLoader.load(CKEDITOR.getUrl(a()+"skin.js"),function(){d(b,f)}):d(b,f)},getPath:function(a){return CKEDITOR.getUrl(e(a))},icons:{},addIcon:function(a,b,d,e){a=
a.toLowerCase();this.icons[a]||(this.icons[a]={path:b,offset:d||0,bgsize:e||"16px"})},getIconStyle:function(a,b,d,e,g){var h;a&&(a=a.toLowerCase(),b&&(h=this.icons[a+"-rtl"]),h||(h=this.icons[a]));a=d||h&&h.path||"";e=e||h&&h.offset;g=g||h&&h.bgsize||"16px";a&&(a=a.replace(/'/g,"\\'"));return a&&"background-image:url('"+CKEDITOR.getUrl(a)+"');background-position:0 "+e+"px;background-size:"+g+";"}};CKEDITOR.tools.extend(CKEDITOR.editor.prototype,{getUiColor:function(){return this.uiColor},setUiColor:function(a){var d=
g(CKEDITOR.document);return(this.setUiColor=function(a){this.uiColor=a;var c=CKEDITOR.skin.chameleon,e="",g="";"function"==typeof c&&(e=c(this,"editor"),g=c(this,"panel"));a=[[b,a]];l([d],e,a);l(h,g,a)}).call(this,a)}});var m="cke_ui_color",h=[],b=/\$color/g;CKEDITOR.on("instanceLoaded",function(a){if(!CKEDITOR.env.ie||!CKEDITOR.env.quirks){var d=a.editor;a=function(a){a=(a.data[0]||a.data).element.getElementsByTag("iframe").getItem(0).getFrameDocument();if(!a.getById("cke_ui_color")){a=g(a);h.push(a);
var c=d.getUiColor();c&&l([a],CKEDITOR.skin.chameleon(d,"panel"),[[b,c]])}};d.on("panelShow",a);d.on("menuShow",a);d.config.uiColor&&d.setUiColor(d.config.uiColor)}})}(),function(){if(CKEDITOR.env.webkit)CKEDITOR.env.hc=!1;else{var a=CKEDITOR.dom.element.createFromHtml('\x3cdiv style\x3d"width:0;height:0;position:absolute;left:-10000px;border:1px solid;border-color:red blue"\x3e\x3c/div\x3e',CKEDITOR.document);a.appendTo(CKEDITOR.document.getHead());try{var e=a.getComputedStyle("border-top-color"),
d=a.getComputedStyle("border-right-color");CKEDITOR.env.hc=!(!e||e!=d)}catch(g){CKEDITOR.env.hc=!1}a.remove()}CKEDITOR.env.hc&&(CKEDITOR.env.cssClass+=" cke_hc");CKEDITOR.document.appendStyleText(".cke{visibility:hidden;}");CKEDITOR.status="loaded";CKEDITOR.fireOnce("loaded");if(a=CKEDITOR._.pending)for(delete CKEDITOR._.pending,e=0;e<a.length;e++)CKEDITOR.editor.prototype.constructor.apply(a[e][0],a[e][1]),CKEDITOR.add(a[e][0])}(),CKEDITOR.skin.name="minimalist",CKEDITOR.skin.ua_editor="ie,iequirks,ie7,ie8,gecko",
CKEDITOR.skin.ua_dialog="ie,iequirks,ie7,ie8",CKEDITOR.skin.chameleon=function(){var a=function(){return function(a,d){for(var e=a.match(/[^#]./g),m=0;3>m;m++){var h=e,b=m,c;c=parseInt(e[m],16);c=("0"+(0>d?0|c*(1+d):0|c+(255-c)*d).toString(16)).slice(-2);h[b]=c}return"#"+e.join("")}}(),e=function(){var a=new CKEDITOR.template("background:#{to};background-image:-webkit-gradient(linear,lefttop,leftbottom,from({from}),to({to}));background-image:-moz-linear-gradient(top,{from},{to});background-image:-webkit-linear-gradient(top,{from},{to});background-image:-o-linear-gradient(top,{from},{to});background-image:-ms-linear-gradient(top,{from},{to});background-image:linear-gradient(top,{from},{to});filter:progid:DXImageTransform.Microsoft.gradient(gradientType\x3d0,startColorstr\x3d'{from}',endColorstr\x3d'{to}');");
return function(d,e){return a.output({from:d,to:e})}}(),d={editor:new CKEDITOR.template("{id}.cke_chrome [border-color:{defaultBorder};] {id} .cke_top [ {defaultGradient}border-bottom-color:{defaultBorder};] {id} .cke_bottom [{defaultGradient}border-top-color:{defaultBorder};] {id} .cke_resizer [border-right-color:{ckeResizer}] {id} .cke_dialog_title [{defaultGradient}border-bottom-color:{defaultBorder};] {id} .cke_dialog_footer [{defaultGradient}outline-color:{defaultBorder};border-top-color:{defaultBorder};] {id} .cke_dialog_tab [{lightGradient}border-color:{defaultBorder};] {id} .cke_dialog_tab:hover [{mediumGradient}] {id} .cke_dialog_contents [border-top-color:{defaultBorder};] {id} .cke_dialog_tab_selected, {id} .cke_dialog_tab_selected:hover [background:{dialogTabSelected};border-bottom-color:{dialogTabSelectedBorder};] {id} .cke_dialog_body [background:{dialogBody};border-color:{defaultBorder};] {id} .cke_toolgroup [{lightGradient}border-color:{defaultBorder};] {id} a.cke_button_off:hover, {id} a.cke_button_off:focus, {id} a.cke_button_off:active [{mediumGradient}] {id} .cke_button_on [{ckeButtonOn}] {id} .cke_toolbar_separator [background-color: {ckeToolbarSeparator};] {id} .cke_combo_button [border-color:{defaultBorder};{lightGradient}] {id} a.cke_combo_button:hover, {id} a.cke_combo_button:focus, {id} .cke_combo_on a.cke_combo_button [border-color:{defaultBorder};{mediumGradient}] {id} .cke_path_item [color:{elementsPathColor};] {id} a.cke_path_item:hover, {id} a.cke_path_item:focus, {id} a.cke_path_item:active [background-color:{elementsPathBg};] {id}.cke_panel [border-color:{defaultBorder};] "),
panel:new CKEDITOR.template(".cke_panel_grouptitle [{lightGradient}border-color:{defaultBorder};] .cke_menubutton_icon [background-color:{menubuttonIcon};] .cke_menubutton:hover .cke_menubutton_icon, .cke_menubutton:focus .cke_menubutton_icon, .cke_menubutton:active .cke_menubutton_icon [background-color:{menubuttonIconHover};] .cke_menuseparator [background-color:{menubuttonIcon};] a:hover.cke_colorbox, a:focus.cke_colorbox, a:active.cke_colorbox [border-color:{defaultBorder};] a:hover.cke_colorauto, a:hover.cke_colormore, a:focus.cke_colorauto, a:focus.cke_colormore, a:active.cke_colorauto, a:active.cke_colormore [background-color:{ckeColorauto};border-color:{defaultBorder};] ")};
return function(g,l){var k=g.uiColor,k={id:"."+g.id,defaultBorder:a(k,-.1),defaultGradient:e(a(k,.9),k),lightGradient:e(a(k,1),a(k,.7)),mediumGradient:e(a(k,.8),a(k,.5)),ckeButtonOn:e(a(k,.6),a(k,.7)),ckeResizer:a(k,-.4),ckeToolbarSeparator:a(k,.5),ckeColorauto:a(k,.8),dialogBody:a(k,.7),dialogTabSelected:e("#FFFFFF","#FFFFFF"),dialogTabSelectedBorder:"#FFF",elementsPathColor:a(k,-.6),elementsPathBg:k,menubuttonIcon:a(k,.5),menubuttonIconHover:a(k,.3)};return d[l].output(k).replace(/\[/g,"{").replace(/\]/g,
"}")}}(),CKEDITOR.plugins.add("dialogui",{onLoad:function(){var a=function(a){this._||(this._={});this._["default"]=this._.initValue=a["default"]||"";this._.required=a.required||!1;for(var c=[this._],d=1;d<arguments.length;d++)c.push(arguments[d]);c.push(!0);CKEDITOR.tools.extend.apply(CKEDITOR.tools,c);return this._},e={build:function(a,c,d){return new CKEDITOR.ui.dialog.textInput(a,c,d)}},d={build:function(a,c,d){return new CKEDITOR.ui.dialog[c.type](a,c,d)}},g={isChanged:function(){return this.getValue()!=
this.getInitValue()},reset:function(a){this.setValue(this.getInitValue(),a)},setInitValue:function(){this._.initValue=this.getValue()},resetInitValue:function(){this._.initValue=this._["default"]},getInitValue:function(){return this._.initValue}},l=CKEDITOR.tools.extend({},CKEDITOR.ui.dialog.uiElement.prototype.eventProcessors,{onChange:function(a,c){this._.domOnChangeRegistered||(a.on("load",function(){this.getInputElement().on("change",function(){a.parts.dialog.isVisible()&&this.fire("change",{value:this.getValue()})},
this)},this),this._.domOnChangeRegistered=!0);this.on("change",c)}},!0),k=/^on([A-Z]\w+)/,m=function(a){for(var c in a)(k.test(c)||"title"==c||"type"==c)&&delete a[c];return a},h=function(a){a=a.data.getKeystroke();a==CKEDITOR.SHIFT+CKEDITOR.ALT+36?this.setDirectionMarker("ltr"):a==CKEDITOR.SHIFT+CKEDITOR.ALT+35&&this.setDirectionMarker("rtl")};CKEDITOR.tools.extend(CKEDITOR.ui.dialog,{labeledElement:function(b,c,d,e){if(!(4>arguments.length)){var g=a.call(this,c);g.labelId=CKEDITOR.tools.getNextId()+
"_label";this._.children=[];var h={role:c.role||"presentation"};c.includeLabel&&(h["aria-labelledby"]=g.labelId);CKEDITOR.ui.dialog.uiElement.call(this,b,c,d,"div",null,h,function(){var a=[],d=c.required?" cke_required":"";"horizontal"!=c.labelLayout?a.push('\x3clabel class\x3d"cke_dialog_ui_labeled_label'+d+'" ',' id\x3d"'+g.labelId+'"',g.inputId?' for\x3d"'+g.inputId+'"':"",(c.labelStyle?' style\x3d"'+c.labelStyle+'"':"")+"\x3e",c.label,"\x3c/label\x3e",'\x3cdiv class\x3d"cke_dialog_ui_labeled_content"',
c.controlStyle?' style\x3d"'+c.controlStyle+'"':"",' role\x3d"presentation"\x3e',e.call(this,b,c),"\x3c/div\x3e"):(d={type:"hbox",widths:c.widths,padding:0,children:[{type:"html",html:'\x3clabel class\x3d"cke_dialog_ui_labeled_label'+d+'" id\x3d"'+g.labelId+'" for\x3d"'+g.inputId+'"'+(c.labelStyle?' style\x3d"'+c.labelStyle+'"':"")+"\x3e"+CKEDITOR.tools.htmlEncode(c.label)+"\x3c/label\x3e"},{type:"html",html:'\x3cspan class\x3d"cke_dialog_ui_labeled_content"'+(c.controlStyle?' style\x3d"'+c.controlStyle+
'"':"")+"\x3e"+e.call(this,b,c)+"\x3c/span\x3e"}]},CKEDITOR.dialog._.uiElementBuilders.hbox.build(b,d,a));return a.join("")})}},textInput:function(b,c,d){if(!(3>arguments.length)){a.call(this,c);var e=this._.inputId=CKEDITOR.tools.getNextId()+"_textInput",g={"class":"cke_dialog_ui_input_"+c.type,id:e,type:c.type};c.validate&&(this.validate=c.validate);c.maxLength&&(g.maxlength=c.maxLength);c.size&&(g.size=c.size);c.inputStyle&&(g.style=c.inputStyle);var k=this,l=!1;b.on("load",function(){k.getInputElement().on("keydown",
function(a){13==a.data.getKeystroke()&&(l=!0)});k.getInputElement().on("keyup",function(a){13==a.data.getKeystroke()&&l&&(b.getButton("ok")&&setTimeout(function(){b.getButton("ok").click()},0),l=!1);k.bidi&&h.call(k,a)},null,null,1E3)});CKEDITOR.ui.dialog.labeledElement.call(this,b,c,d,function(){var a=['\x3cdiv class\x3d"cke_dialog_ui_input_',c.type,'" role\x3d"presentation"'];c.width&&a.push('style\x3d"width:'+c.width+'" ');a.push("\x3e\x3cinput ");g["aria-labelledby"]=this._.labelId;this._.required&&
(g["aria-required"]=this._.required);for(var b in g)a.push(b+'\x3d"'+g[b]+'" ');a.push(" /\x3e\x3c/div\x3e");return a.join("")})}},textarea:function(b,c,d){if(!(3>arguments.length)){a.call(this,c);var e=this,g=this._.inputId=CKEDITOR.tools.getNextId()+"_textarea",k={};c.validate&&(this.validate=c.validate);k.rows=c.rows||5;k.cols=c.cols||20;k["class"]="cke_dialog_ui_input_textarea "+(c["class"]||"");"undefined"!=typeof c.inputStyle&&(k.style=c.inputStyle);c.dir&&(k.dir=c.dir);if(e.bidi)b.on("load",
function(){e.getInputElement().on("keyup",h)},e);CKEDITOR.ui.dialog.labeledElement.call(this,b,c,d,function(){k["aria-labelledby"]=this._.labelId;this._.required&&(k["aria-required"]=this._.required);var a=['\x3cdiv class\x3d"cke_dialog_ui_input_textarea" role\x3d"presentation"\x3e\x3ctextarea id\x3d"',g,'" '],b;for(b in k)a.push(b+'\x3d"'+CKEDITOR.tools.htmlEncode(k[b])+'" ');a.push("\x3e",CKEDITOR.tools.htmlEncode(e._["default"]),"\x3c/textarea\x3e\x3c/div\x3e");return a.join("")})}},checkbox:function(b,
c,d){if(!(3>arguments.length)){var e=a.call(this,c,{"default":!!c["default"]});c.validate&&(this.validate=c.validate);CKEDITOR.ui.dialog.uiElement.call(this,b,c,d,"span",null,null,function(){var a=CKEDITOR.tools.extend({},c,{id:c.id?c.id+"_checkbox":CKEDITOR.tools.getNextId()+"_checkbox"},!0),d=[],f=CKEDITOR.tools.getNextId()+"_label",g={"class":"cke_dialog_ui_checkbox_input",type:"checkbox","aria-labelledby":f};m(a);c["default"]&&(g.checked="checked");"undefined"!=typeof a.inputStyle&&(a.style=a.inputStyle);
e.checkbox=new CKEDITOR.ui.dialog.uiElement(b,a,d,"input",null,g);d.push(' \x3clabel id\x3d"',f,'" for\x3d"',g.id,'"'+(c.labelStyle?' style\x3d"'+c.labelStyle+'"':"")+"\x3e",CKEDITOR.tools.htmlEncode(c.label),"\x3c/label\x3e");return d.join("")})}},radio:function(b,c,d){if(!(3>arguments.length)){a.call(this,c);this._["default"]||(this._["default"]=this._.initValue=c.items[0][1]);c.validate&&(this.validate=c.validate);var e=[],g=this;c.role="radiogroup";c.includeLabel=!0;CKEDITOR.ui.dialog.labeledElement.call(this,
b,c,d,function(){for(var a=[],d=[],f=(c.id?c.id:CKEDITOR.tools.getNextId())+"_radio",h=0;h<c.items.length;h++){var k=c.items[h],l=void 0!==k[2]?k[2]:k[0],F=void 0!==k[1]?k[1]:k[0],n=CKEDITOR.tools.getNextId()+"_radio_input",r=n+"_label",n=CKEDITOR.tools.extend({},c,{id:n,title:null,type:null},!0),l=CKEDITOR.tools.extend({},n,{title:l},!0),C={type:"radio","class":"cke_dialog_ui_radio_input",name:f,value:F,"aria-labelledby":r},D=[];g._["default"]==F&&(C.checked="checked");m(n);m(l);"undefined"!=typeof n.inputStyle&&
(n.style=n.inputStyle);n.keyboardFocusable=!0;e.push(new CKEDITOR.ui.dialog.uiElement(b,n,D,"input",null,C));D.push(" ");new CKEDITOR.ui.dialog.uiElement(b,l,D,"label",null,{id:r,"for":C.id},k[0]);a.push(D.join(""))}new CKEDITOR.ui.dialog.hbox(b,e,a,d);return d.join("")});this._.children=e}},button:function(b,c,d){if(arguments.length){"function"==typeof c&&(c=c(b.getParentEditor()));a.call(this,c,{disabled:c.disabled||!1});CKEDITOR.event.implementOn(this);var e=this;b.on("load",function(){var a=this.getElement();
(function(){a.on("click",function(a){e.click();a.data.preventDefault()});a.on("keydown",function(a){a.data.getKeystroke()in{32:1}&&(e.click(),a.data.preventDefault())})})();a.unselectable()},this);var g=CKEDITOR.tools.extend({},c);delete g.style;var h=CKEDITOR.tools.getNextId()+"_label";CKEDITOR.ui.dialog.uiElement.call(this,b,g,d,"a",null,{style:c.style,href:"javascript:void(0)",title:c.label,hidefocus:"true","class":c["class"],role:"button","aria-labelledby":h},'\x3cspan id\x3d"'+h+'" class\x3d"cke_dialog_ui_button"\x3e'+
CKEDITOR.tools.htmlEncode(c.label)+"\x3c/span\x3e")}},select:function(b,c,d){if(!(3>arguments.length)){var e=a.call(this,c);c.validate&&(this.validate=c.validate);e.inputId=CKEDITOR.tools.getNextId()+"_select";CKEDITOR.ui.dialog.labeledElement.call(this,b,c,d,function(){var a=CKEDITOR.tools.extend({},c,{id:c.id?c.id+"_select":CKEDITOR.tools.getNextId()+"_select"},!0),d=[],f=[],g={id:e.inputId,"class":"cke_dialog_ui_input_select","aria-labelledby":this._.labelId};d.push('\x3cdiv class\x3d"cke_dialog_ui_input_',
c.type,'" role\x3d"presentation"');c.width&&d.push('style\x3d"width:'+c.width+'" ');d.push("\x3e");void 0!==c.size&&(g.size=c.size);void 0!==c.multiple&&(g.multiple=c.multiple);m(a);for(var h=0,k;h<c.items.length&&(k=c.items[h]);h++)f.push('\x3coption value\x3d"',CKEDITOR.tools.htmlEncode(void 0!==k[1]?k[1]:k[0]).replace(/"/g,"\x26quot;"),'" /\x3e ',CKEDITOR.tools.htmlEncode(k[0]));"undefined"!=typeof a.inputStyle&&(a.style=a.inputStyle);e.select=new CKEDITOR.ui.dialog.uiElement(b,a,d,"select",null,
g,f.join(""));d.push("\x3c/div\x3e");return d.join("")})}},file:function(b,c,d){if(!(3>arguments.length)){void 0===c["default"]&&(c["default"]="");var e=CKEDITOR.tools.extend(a.call(this,c),{definition:c,buttons:[]});c.validate&&(this.validate=c.validate);b.on("load",function(){CKEDITOR.document.getById(e.frameId).getParent().addClass("cke_dialog_ui_input_file")});CKEDITOR.ui.dialog.labeledElement.call(this,b,c,d,function(){e.frameId=CKEDITOR.tools.getNextId()+"_fileInput";var a=['\x3ciframe frameborder\x3d"0" allowtransparency\x3d"0" class\x3d"cke_dialog_ui_input_file" role\x3d"presentation" id\x3d"',
e.frameId,'" title\x3d"',c.label,'" src\x3d"javascript:void('];a.push(CKEDITOR.env.ie?"(function(){"+encodeURIComponent("document.open();("+CKEDITOR.tools.fixDomain+")();document.close();")+"})()":"0");a.push(')"\x3e\x3c/iframe\x3e');return a.join("")})}},fileButton:function(b,c,d){var e=this;if(!(3>arguments.length)){a.call(this,c);c.validate&&(this.validate=c.validate);var g=CKEDITOR.tools.extend({},c),h=g.onClick;g.className=(g.className?g.className+" ":"")+"cke_dialog_ui_button";g.onClick=function(a){var d=
c["for"];h&&!1===h.call(this,a)||(b.getContentElement(d[0],d[1]).submit(),this.disable())};b.on("load",function(){b.getContentElement(c["for"][0],c["for"][1])._.buttons.push(e)});CKEDITOR.ui.dialog.button.call(this,b,g,d)}},html:function(){var a=/^\s*<[\w:]+\s+([^>]*)?>/,c=/^(\s*<[\w:]+(?:\s+[^>]*)?)((?:.|\r|\n)+)$/,d=/\/$/;return function(e,g,h){if(!(3>arguments.length)){var k=[],l=g.html;"\x3c"!=l.charAt(0)&&(l="\x3cspan\x3e"+l+"\x3c/span\x3e");var m=g.focus;if(m){var H=this.focus;this.focus=function(){("function"==
typeof m?m:H).call(this);this.fire("focus")};g.isFocusable&&(this.isFocusable=this.isFocusable);this.keyboardFocusable=!0}CKEDITOR.ui.dialog.uiElement.call(this,e,g,k,"span",null,null,"");k=k.join("").match(a);l=l.match(c)||["","",""];d.test(l[1])&&(l[1]=l[1].slice(0,-1),l[2]="/"+l[2]);h.push([l[1]," ",k[1]||"",l[2]].join(""))}}}(),fieldset:function(a,c,d,e,g){var h=g.label;this._={children:c};CKEDITOR.ui.dialog.uiElement.call(this,a,g,e,"fieldset",null,null,function(){var a=[];h&&a.push("\x3clegend"+
(g.labelStyle?' style\x3d"'+g.labelStyle+'"':"")+"\x3e"+h+"\x3c/legend\x3e");for(var b=0;b<d.length;b++)a.push(d[b]);return a.join("")})}},!0);CKEDITOR.ui.dialog.html.prototype=new CKEDITOR.ui.dialog.uiElement;CKEDITOR.ui.dialog.labeledElement.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.uiElement,{setLabel:function(a){var c=CKEDITOR.document.getById(this._.labelId);1>c.getChildCount()?(new CKEDITOR.dom.text(a,CKEDITOR.document)).appendTo(c):c.getChild(0).$.nodeValue=a;return this},getLabel:function(){var a=
CKEDITOR.document.getById(this._.labelId);return!a||1>a.getChildCount()?"":a.getChild(0).getText()},eventProcessors:l},!0);CKEDITOR.ui.dialog.button.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.uiElement,{click:function(){return this._.disabled?!1:this.fire("click",{dialog:this._.dialog})},enable:function(){this._.disabled=!1;var a=this.getElement();a&&a.removeClass("cke_disabled")},disable:function(){this._.disabled=!0;this.getElement().addClass("cke_disabled")},isVisible:function(){return this.getElement().getFirst().isVisible()},
isEnabled:function(){return!this._.disabled},eventProcessors:CKEDITOR.tools.extend({},CKEDITOR.ui.dialog.uiElement.prototype.eventProcessors,{onClick:function(a,c){this.on("click",function(){c.apply(this,arguments)})}},!0),accessKeyUp:function(){this.click()},accessKeyDown:function(){this.focus()},keyboardFocusable:!0},!0);CKEDITOR.ui.dialog.textInput.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.labeledElement,{getInputElement:function(){return CKEDITOR.document.getById(this._.inputId)},
focus:function(){var a=this.selectParentTab();setTimeout(function(){var c=a.getInputElement();c&&c.$.focus()},0)},select:function(){var a=this.selectParentTab();setTimeout(function(){var c=a.getInputElement();c&&(c.$.focus(),c.$.select())},0)},accessKeyUp:function(){this.select()},setValue:function(a){if(this.bidi){var c=a&&a.charAt(0);(c="‪"==c?"ltr":"‫"==c?"rtl":null)&&(a=a.slice(1));this.setDirectionMarker(c)}a||(a="");return CKEDITOR.ui.dialog.uiElement.prototype.setValue.apply(this,arguments)},
getValue:function(){var a=CKEDITOR.ui.dialog.uiElement.prototype.getValue.call(this);if(this.bidi&&a){var c=this.getDirectionMarker();c&&(a=("ltr"==c?"‪":"‫")+a)}return a},setDirectionMarker:function(a){var c=this.getInputElement();a?c.setAttributes({dir:a,"data-cke-dir-marker":a}):this.getDirectionMarker()&&c.removeAttributes(["dir","data-cke-dir-marker"])},getDirectionMarker:function(){return this.getInputElement().data("cke-dir-marker")},keyboardFocusable:!0},g,!0);CKEDITOR.ui.dialog.textarea.prototype=
new CKEDITOR.ui.dialog.textInput;CKEDITOR.ui.dialog.select.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.labeledElement,{getInputElement:function(){return this._.select.getElement()},add:function(a,c,d){var e=new CKEDITOR.dom.element("option",this.getDialog().getParentEditor().document),g=this.getInputElement().$;e.$.text=a;e.$.value=void 0===c||null===c?a:c;void 0===d||null===d?CKEDITOR.env.ie?g.add(e.$):g.add(e.$,null):g.add(e.$,d);return this},remove:function(a){this.getInputElement().$.remove(a);
return this},clear:function(){for(var a=this.getInputElement().$;0<a.length;)a.remove(0);return this},keyboardFocusable:!0},g,!0);CKEDITOR.ui.dialog.checkbox.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.uiElement,{getInputElement:function(){return this._.checkbox.getElement()},setValue:function(a,c){this.getInputElement().$.checked=a;!c&&this.fire("change",{value:a})},getValue:function(){return this.getInputElement().$.checked},accessKeyUp:function(){this.setValue(!this.getValue())},eventProcessors:{onChange:function(a,
c){if(!CKEDITOR.env.ie||8<CKEDITOR.env.version)return l.onChange.apply(this,arguments);a.on("load",function(){var a=this._.checkbox.getElement();a.on("propertychange",function(b){b=b.data.$;"checked"==b.propertyName&&this.fire("change",{value:a.$.checked})},this)},this);this.on("change",c);return null}},keyboardFocusable:!0},g,!0);CKEDITOR.ui.dialog.radio.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.uiElement,{setValue:function(a,c){for(var d=this._.children,e,g=0;g<d.length&&(e=d[g]);g++)e.getElement().$.checked=
e.getValue()==a;!c&&this.fire("change",{value:a})},getValue:function(){for(var a=this._.children,c=0;c<a.length;c++)if(a[c].getElement().$.checked)return a[c].getValue();return null},accessKeyUp:function(){var a=this._.children,c;for(c=0;c<a.length;c++)if(a[c].getElement().$.checked){a[c].getElement().focus();return}a[0].getElement().focus()},eventProcessors:{onChange:function(a,c){if(!CKEDITOR.env.ie||8<CKEDITOR.env.version)return l.onChange.apply(this,arguments);a.on("load",function(){for(var a=
this._.children,b=this,c=0;c<a.length;c++)a[c].getElement().on("propertychange",function(a){a=a.data.$;"checked"==a.propertyName&&this.$.checked&&b.fire("change",{value:this.getAttribute("value")})})},this);this.on("change",c);return null}}},g,!0);CKEDITOR.ui.dialog.file.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.labeledElement,g,{getInputElement:function(){var a=CKEDITOR.document.getById(this._.frameId).getFrameDocument();return 0<a.$.forms.length?new CKEDITOR.dom.element(a.$.forms[0].elements[0]):
this.getElement()},submit:function(){this.getInputElement().getParent().$.submit();return this},getAction:function(){return this.getInputElement().getParent().$.action},registerEvents:function(a){var c=/^on([A-Z]\w+)/,d,e=function(a,b,c,d){a.on("formLoaded",function(){a.getInputElement().on(c,d,a)})},g;for(g in a)if(d=g.match(c))this.eventProcessors[g]?this.eventProcessors[g].call(this,this._.dialog,a[g]):e(this,this._.dialog,d[1].toLowerCase(),a[g]);return this},reset:function(){function a(){d.$.open();
var b="";e.size&&(b=e.size-(CKEDITOR.env.ie?7:0));var w=c.frameId+"_input";d.$.write(['\x3chtml dir\x3d"'+l+'" lang\x3d"'+m+'"\x3e\x3chead\x3e\x3ctitle\x3e\x3c/title\x3e\x3c/head\x3e\x3cbody style\x3d"margin: 0; overflow: hidden; background: transparent;"\x3e','\x3cform enctype\x3d"multipart/form-data" method\x3d"POST" dir\x3d"'+l+'" lang\x3d"'+m+'" action\x3d"',CKEDITOR.tools.htmlEncode(e.action),'"\x3e\x3clabel id\x3d"',c.labelId,'" for\x3d"',w,'" style\x3d"display:none"\x3e',CKEDITOR.tools.htmlEncode(e.label),
'\x3c/label\x3e\x3cinput style\x3d"width:100%" id\x3d"',w,'" aria-labelledby\x3d"',c.labelId,'" type\x3d"file" name\x3d"',CKEDITOR.tools.htmlEncode(e.id||"cke_upload"),'" size\x3d"',CKEDITOR.tools.htmlEncode(0<b?b:""),'" /\x3e\x3c/form\x3e\x3c/body\x3e\x3c/html\x3e\x3cscript\x3e',CKEDITOR.env.ie?"("+CKEDITOR.tools.fixDomain+")();":"","window.parent.CKEDITOR.tools.callFunction("+h+");","window.onbeforeunload \x3d function() {window.parent.CKEDITOR.tools.callFunction("+k+")}","\x3c/script\x3e"].join(""));
d.$.close();for(b=0;b<g.length;b++)g[b].enable()}var c=this._,d=CKEDITOR.document.getById(c.frameId).getFrameDocument(),e=c.definition,g=c.buttons,h=this.formLoadedNumber,k=this.formUnloadNumber,l=c.dialog._.editor.lang.dir,m=c.dialog._.editor.langCode;h||(h=this.formLoadedNumber=CKEDITOR.tools.addFunction(function(){this.fire("formLoaded")},this),k=this.formUnloadNumber=CKEDITOR.tools.addFunction(function(){this.getInputElement().clearCustomData()},this),this.getDialog()._.editor.on("destroy",function(){CKEDITOR.tools.removeFunction(h);
CKEDITOR.tools.removeFunction(k)}));CKEDITOR.env.gecko?setTimeout(a,500):a()},getValue:function(){return this.getInputElement().$.value||""},setInitValue:function(){this._.initValue=""},eventProcessors:{onChange:function(a,c){this._.domOnChangeRegistered||(this.on("formLoaded",function(){this.getInputElement().on("change",function(){this.fire("change",{value:this.getValue()})},this)},this),this._.domOnChangeRegistered=!0);this.on("change",c)}},keyboardFocusable:!0},!0);CKEDITOR.ui.dialog.fileButton.prototype=
new CKEDITOR.ui.dialog.button;CKEDITOR.ui.dialog.fieldset.prototype=CKEDITOR.tools.clone(CKEDITOR.ui.dialog.hbox.prototype);CKEDITOR.dialog.addUIElement("text",e);CKEDITOR.dialog.addUIElement("password",e);CKEDITOR.dialog.addUIElement("textarea",d);CKEDITOR.dialog.addUIElement("checkbox",d);CKEDITOR.dialog.addUIElement("radio",d);CKEDITOR.dialog.addUIElement("button",d);CKEDITOR.dialog.addUIElement("select",d);CKEDITOR.dialog.addUIElement("file",d);CKEDITOR.dialog.addUIElement("fileButton",d);CKEDITOR.dialog.addUIElement("html",
d);CKEDITOR.dialog.addUIElement("fieldset",{build:function(a,c,d){for(var e=c.children,g,h=[],k=[],l=0;l<e.length&&(g=e[l]);l++){var m=[];h.push(m);k.push(CKEDITOR.dialog._.uiElementBuilders[g.type].build(a,g,m))}return new CKEDITOR.ui.dialog[c.type](a,k,h,d,c)}})}}),CKEDITOR.DIALOG_RESIZE_NONE=0,CKEDITOR.DIALOG_RESIZE_WIDTH=1,CKEDITOR.DIALOG_RESIZE_HEIGHT=2,CKEDITOR.DIALOG_RESIZE_BOTH=3,CKEDITOR.DIALOG_STATE_IDLE=1,CKEDITOR.DIALOG_STATE_BUSY=2,function(){function a(){for(var a=this._.tabIdList.length,
b=CKEDITOR.tools.indexOf(this._.tabIdList,this._.currentTabId)+a,c=b-1;c>b-a;c--)if(this._.tabs[this._.tabIdList[c%a]][0].$.offsetHeight)return this._.tabIdList[c%a];return null}function e(){for(var a=this._.tabIdList.length,b=CKEDITOR.tools.indexOf(this._.tabIdList,this._.currentTabId),c=b+1;c<b+a;c++)if(this._.tabs[this._.tabIdList[c%a]][0].$.offsetHeight)return this._.tabIdList[c%a];return null}function d(a,b){for(var c=a.$.getElementsByTagName("input"),d=0,f=c.length;d<f;d++){var e=new CKEDITOR.dom.element(c[d]);
"text"==e.getAttribute("type").toLowerCase()&&(b?(e.setAttribute("value",e.getCustomData("fake_value")||""),e.removeCustomData("fake_value")):(e.setCustomData("fake_value",e.getAttribute("value")),e.setAttribute("value","")))}}function g(a,b){var c=this.getInputElement();c&&(a?c.removeAttribute("aria-invalid"):c.setAttribute("aria-invalid",!0));a||(this.select?this.select():this.focus());b&&alert(b);this.fire("validated",{valid:a,msg:b})}function l(){var a=this.getInputElement();a&&a.removeAttribute("aria-invalid")}
function k(a){var b=CKEDITOR.dom.element.createFromHtml(CKEDITOR.addTemplate("dialog",u).output({id:CKEDITOR.tools.getNextNumber(),editorId:a.id,langDir:a.lang.dir,langCode:a.langCode,editorDialogClass:"cke_editor_"+a.name.replace(/\./g,"\\.")+"_dialog",closeTitle:a.lang.common.close,hidpi:CKEDITOR.env.hidpi?"cke_hidpi":""})),c=b.getChild([0,0,0,0,0]),d=c.getChild(0),f=c.getChild(1);a.plugins.clipboard&&CKEDITOR.plugins.clipboard.preventDefaultDropOnElement(c);!CKEDITOR.env.ie||CKEDITOR.env.quirks||
CKEDITOR.env.edge||(a="javascript:void(function(){"+encodeURIComponent("document.open();("+CKEDITOR.tools.fixDomain+")();document.close();")+"}())",CKEDITOR.dom.element.createFromHtml('\x3ciframe frameBorder\x3d"0" class\x3d"cke_iframe_shim" src\x3d"'+a+'" tabIndex\x3d"-1"\x3e\x3c/iframe\x3e').appendTo(c.getParent()));d.unselectable();f.unselectable();return{element:b,parts:{dialog:b.getChild(0),title:d,close:f,tabs:c.getChild(2),contents:c.getChild([3,0,0,0]),footer:c.getChild([3,0,1,0])}}}function m(a,
b,c){this.element=b;this.focusIndex=c;this.tabIndex=0;this.isFocusable=function(){return!b.getAttribute("disabled")&&b.isVisible()};this.focus=function(){a._.currentFocusIndex=this.focusIndex;this.element.focus()};b.on("keydown",function(a){a.data.getKeystroke()in{32:1,13:1}&&this.fire("click")});b.on("focus",function(){this.fire("mouseover")});b.on("blur",function(){this.fire("mouseout")})}function h(a){function b(){a.layout()}var c=CKEDITOR.document.getWindow();c.on("resize",b);a.on("hide",function(){c.removeListener("resize",
b)})}function b(a,b){this._={dialog:a};CKEDITOR.tools.extend(this,b)}function c(a){function b(c){var p=a.getSize(),k=CKEDITOR.document.getWindow().getViewPaneSize(),E=c.data.$.screenX,q=c.data.$.screenY,l=E-d.x,n=q-d.y;d={x:E,y:q};f.x+=l;f.y+=n;a.move(f.x+h[3]<g?-h[3]:f.x-h[1]>k.width-p.width-g?k.width-p.width+("rtl"==e.lang.dir?0:h[1]):f.x,f.y+h[0]<g?-h[0]:f.y-h[2]>k.height-p.height-g?k.height-p.height+h[2]:f.y,1);c.data.preventDefault()}function c(){CKEDITOR.document.removeListener("mousemove",
b);CKEDITOR.document.removeListener("mouseup",c);if(CKEDITOR.env.ie6Compat){var a=D.getChild(0).getFrameDocument();a.removeListener("mousemove",b);a.removeListener("mouseup",c)}}var d=null,f=null,e=a.getParentEditor(),g=e.config.dialog_magnetDistance,h=CKEDITOR.skin.margins||[0,0,0,0];"undefined"==typeof g&&(g=20);a.parts.title.on("mousedown",function(e){d={x:e.data.$.screenX,y:e.data.$.screenY};CKEDITOR.document.on("mousemove",b);CKEDITOR.document.on("mouseup",c);f=a.getPosition();if(CKEDITOR.env.ie6Compat){var g=
D.getChild(0).getFrameDocument();g.on("mousemove",b);g.on("mouseup",c)}e.data.preventDefault()},a)}function f(a){function b(c){var E="rtl"==e.lang.dir,q=l.width,A=l.height,n=q+(c.data.$.screenX-k.x)*(E?-1:1)*(a._.moved?1:2),m=A+(c.data.$.screenY-k.y)*(a._.moved?1:2),x=a._.element.getFirst(),x=E&&x.getComputedStyle("right"),t=a.getPosition();t.y+m>p.height&&(m=p.height-t.y);(E?x:t.x)+n>p.width&&(n=p.width-(E?x:t.x));if(f==CKEDITOR.DIALOG_RESIZE_WIDTH||f==CKEDITOR.DIALOG_RESIZE_BOTH)q=Math.max(d.minWidth||
0,n-g);if(f==CKEDITOR.DIALOG_RESIZE_HEIGHT||f==CKEDITOR.DIALOG_RESIZE_BOTH)A=Math.max(d.minHeight||0,m-h);a.resize(q,A);a._.moved||a.layout();c.data.preventDefault()}function c(){CKEDITOR.document.removeListener("mouseup",c);CKEDITOR.document.removeListener("mousemove",b);E&&(E.remove(),E=null);if(CKEDITOR.env.ie6Compat){var a=D.getChild(0).getFrameDocument();a.removeListener("mouseup",c);a.removeListener("mousemove",b)}}var d=a.definition,f=d.resizable;if(f!=CKEDITOR.DIALOG_RESIZE_NONE){var e=a.getParentEditor(),
g,h,p,k,l,E,A=CKEDITOR.tools.addFunction(function(d){l=a.getSize();var f=a.parts.contents;f.$.getElementsByTagName("iframe").length&&(E=CKEDITOR.dom.element.createFromHtml('\x3cdiv class\x3d"cke_dialog_resize_cover" style\x3d"height: 100%; position: absolute; width: 100%;"\x3e\x3c/div\x3e'),f.append(E));h=l.height-a.parts.contents.getSize("height",!(CKEDITOR.env.gecko||CKEDITOR.env.ie&&CKEDITOR.env.quirks));g=l.width-a.parts.contents.getSize("width",1);k={x:d.screenX,y:d.screenY};p=CKEDITOR.document.getWindow().getViewPaneSize();
CKEDITOR.document.on("mousemove",b);CKEDITOR.document.on("mouseup",c);CKEDITOR.env.ie6Compat&&(f=D.getChild(0).getFrameDocument(),f.on("mousemove",b),f.on("mouseup",c));d.preventDefault&&d.preventDefault()});a.on("load",function(){var b="";f==CKEDITOR.DIALOG_RESIZE_WIDTH?b=" cke_resizer_horizontal":f==CKEDITOR.DIALOG_RESIZE_HEIGHT&&(b=" cke_resizer_vertical");b=CKEDITOR.dom.element.createFromHtml('\x3cdiv class\x3d"cke_resizer'+b+" cke_resizer_"+e.lang.dir+'" title\x3d"'+CKEDITOR.tools.htmlEncode(e.lang.common.resize)+
'" onmousedown\x3d"CKEDITOR.tools.callFunction('+A+', event )"\x3e'+("ltr"==e.lang.dir?"◢":"◣")+"\x3c/div\x3e");a.parts.footer.append(b,1)});e.on("destroy",function(){CKEDITOR.tools.removeFunction(A)})}}function p(a){a.data.preventDefault(1)}function B(a){var b=CKEDITOR.document.getWindow(),c=a.config,d=CKEDITOR.skinName||a.config.skin,f=c.dialog_backgroundCoverColor||("moono-lisa"==d?"black":"white"),d=c.dialog_backgroundCoverOpacity,e=c.baseFloatZIndex,c=CKEDITOR.tools.genKey(f,d,e),g=C[c];g?g.show():
(e=['\x3cdiv tabIndex\x3d"-1" style\x3d"position: ',CKEDITOR.env.ie6Compat?"absolute":"fixed","; z-index: ",e,"; top: 0px; left: 0px; ",CKEDITOR.env.ie6Compat?"":"background-color: "+f,'" class\x3d"cke_dialog_background_cover"\x3e'],CKEDITOR.env.ie6Compat&&(f="\x3chtml\x3e\x3cbody style\x3d\\'background-color:"+f+";\\'\x3e\x3c/body\x3e\x3c/html\x3e",e.push('\x3ciframe hidefocus\x3d"true" frameborder\x3d"0" id\x3d"cke_dialog_background_iframe" src\x3d"javascript:'),e.push("void((function(){"+encodeURIComponent("document.open();("+
CKEDITOR.tools.fixDomain+")();document.write( '"+f+"' );document.close();")+"})())"),e.push('" style\x3d"position:absolute;left:0;top:0;width:100%;height: 100%;filter: progid:DXImageTransform.Microsoft.Alpha(opacity\x3d0)"\x3e\x3c/iframe\x3e')),e.push("\x3c/div\x3e"),g=CKEDITOR.dom.element.createFromHtml(e.join("")),g.setOpacity(void 0!==d?d:.5),g.on("keydown",p),g.on("keypress",p),g.on("keyup",p),g.appendTo(CKEDITOR.document.getBody()),C[c]=g);a.focusManager.add(g);D=g;a=function(){var a=b.getViewPaneSize();
g.setStyles({width:a.width+"px",height:a.height+"px"})};var h=function(){var a=b.getScrollPosition(),c=CKEDITOR.dialog._.currentTop;g.setStyles({left:a.x+"px",top:a.y+"px"});if(c){do a=c.getPosition(),c.move(a.x,a.y);while(c=c._.parentDialog)}};r=a;b.on("resize",a);a();CKEDITOR.env.mac&&CKEDITOR.env.webkit||g.focus();if(CKEDITOR.env.ie6Compat){var k=function(){h();arguments.callee.prevScrollHandler.apply(this,arguments)};b.$.setTimeout(function(){k.prevScrollHandler=window.onscroll||function(){};
window.onscroll=k},0);h()}}function x(a){D&&(a.focusManager.remove(D),a=CKEDITOR.document.getWindow(),D.hide(),a.removeListener("resize",r),CKEDITOR.env.ie6Compat&&a.$.setTimeout(function(){window.onscroll=window.onscroll&&window.onscroll.prevScrollHandler||null},0),r=null)}var t=CKEDITOR.tools.cssLength,u='\x3cdiv class\x3d"cke_reset_all {editorId} {editorDialogClass} {hidpi}" dir\x3d"{langDir}" lang\x3d"{langCode}" role\x3d"dialog" aria-labelledby\x3d"cke_dialog_title_{id}"\x3e\x3ctable class\x3d"cke_dialog '+
CKEDITOR.env.cssClass+' cke_{langDir}" style\x3d"position:absolute" role\x3d"presentation"\x3e\x3ctr\x3e\x3ctd role\x3d"presentation"\x3e\x3cdiv class\x3d"cke_dialog_body" role\x3d"presentation"\x3e\x3cdiv id\x3d"cke_dialog_title_{id}" class\x3d"cke_dialog_title" role\x3d"presentation"\x3e\x3c/div\x3e\x3ca id\x3d"cke_dialog_close_button_{id}" class\x3d"cke_dialog_close_button" href\x3d"javascript:void(0)" title\x3d"{closeTitle}" role\x3d"button"\x3e\x3cspan class\x3d"cke_label"\x3eX\x3c/span\x3e\x3c/a\x3e\x3cdiv id\x3d"cke_dialog_tabs_{id}" class\x3d"cke_dialog_tabs" role\x3d"tablist"\x3e\x3c/div\x3e\x3ctable class\x3d"cke_dialog_contents" role\x3d"presentation"\x3e\x3ctr\x3e\x3ctd id\x3d"cke_dialog_contents_{id}" class\x3d"cke_dialog_contents_body" role\x3d"presentation"\x3e\x3c/td\x3e\x3c/tr\x3e\x3ctr\x3e\x3ctd id\x3d"cke_dialog_footer_{id}" class\x3d"cke_dialog_footer" role\x3d"presentation"\x3e\x3c/td\x3e\x3c/tr\x3e\x3c/table\x3e\x3c/div\x3e\x3c/td\x3e\x3c/tr\x3e\x3c/table\x3e\x3c/div\x3e';
CKEDITOR.dialog=function(b,d){function h(){var a=I._.focusList;a.sort(function(a,b){return a.tabIndex!=b.tabIndex?b.tabIndex-a.tabIndex:a.focusIndex-b.focusIndex});for(var b=a.length,c=0;c<b;c++)a[c].focusIndex=c}function p(a){var b=I._.focusList;a=a||0;if(!(1>b.length)){var c=I._.currentFocusIndex;I._.tabBarMode&&0>a&&(c=0);try{b[c].getInputElement().$.blur()}catch(d){}var f=c,e=1<I._.pageCount;do{f+=a;if(e&&!I._.tabBarMode&&(f==b.length||-1==f)){I._.tabBarMode=!0;I._.tabs[I._.currentTabId][0].focus();
I._.currentFocusIndex=-1;return}f=(f+b.length)%b.length;if(f==c)break}while(a&&!b[f].isFocusable());b[f].focus();"text"==b[f].type&&b[f].select()}}function m(c){if(I==CKEDITOR.dialog._.currentTop){var d=c.data.getKeystroke(),f="rtl"==b.lang.dir,g=[37,38,39,40];E=A=0;if(9==d||d==CKEDITOR.SHIFT+9)p(d==CKEDITOR.SHIFT+9?-1:1),E=1;else if(d==CKEDITOR.ALT+121&&!I._.tabBarMode&&1<I.getPageCount())I._.tabBarMode=!0,I._.tabs[I._.currentTabId][0].focus(),I._.currentFocusIndex=-1,E=1;else if(-1!=CKEDITOR.tools.indexOf(g,
d)&&I._.tabBarMode)d=-1!=CKEDITOR.tools.indexOf([f?39:37,38],d)?a.call(I):e.call(I),I.selectPage(d),I._.tabs[d][0].focus(),E=1;else if(13!=d&&32!=d||!I._.tabBarMode)if(13==d)d=c.data.getTarget(),d.is("a","button","select","textarea")||d.is("input")&&"button"==d.$.type||((d=this.getButton("ok"))&&CKEDITOR.tools.setTimeout(d.click,0,d),E=1),A=1;else if(27==d)(d=this.getButton("cancel"))?CKEDITOR.tools.setTimeout(d.click,0,d):!1!==this.fire("cancel",{hide:!0}).hide&&this.hide(),A=1;else return;else this.selectPage(this._.currentTabId),
this._.tabBarMode=!1,this._.currentFocusIndex=-1,p(1),E=1;x(c)}}function x(a){E?a.data.preventDefault(1):A&&a.data.stopPropagation()}var t=CKEDITOR.dialog._.dialogDefinitions[d],B=CKEDITOR.tools.clone(y),u=b.config.dialog_buttonsOrder||"OS",r=b.lang.dir,w={},E,A;("OS"==u&&CKEDITOR.env.mac||"rtl"==u&&"ltr"==r||"ltr"==u&&"rtl"==r)&&B.buttons.reverse();t=CKEDITOR.tools.extend(t(b),B);t=CKEDITOR.tools.clone(t);t=new n(this,t);B=k(b);this._={editor:b,element:B.element,name:d,contentSize:{width:0,height:0},
size:{width:0,height:0},contents:{},buttons:{},accessKeyMap:{},tabs:{},tabIdList:[],currentTabId:null,currentTabIndex:null,pageCount:0,lastTab:null,tabBarMode:!1,focusList:[],currentFocusIndex:0,hasFocus:!1};this.parts=B.parts;CKEDITOR.tools.setTimeout(function(){b.fire("ariaWidget",this.parts.contents)},0,this);B={position:CKEDITOR.env.ie6Compat?"absolute":"fixed",top:0,visibility:"hidden"};B["rtl"==r?"right":"left"]=0;this.parts.dialog.setStyles(B);CKEDITOR.event.call(this);this.definition=t=CKEDITOR.fire("dialogDefinition",
{name:d,definition:t},b).definition;if(!("removeDialogTabs"in b._)&&b.config.removeDialogTabs){B=b.config.removeDialogTabs.split(";");for(r=0;r<B.length;r++)if(u=B[r].split(":"),2==u.length){var M=u[0];w[M]||(w[M]=[]);w[M].push(u[1])}b._.removeDialogTabs=w}if(b._.removeDialogTabs&&(w=b._.removeDialogTabs[d]))for(r=0;r<w.length;r++)t.removeContents(w[r]);if(t.onLoad)this.on("load",t.onLoad);if(t.onShow)this.on("show",t.onShow);if(t.onHide)this.on("hide",t.onHide);if(t.onOk)this.on("ok",function(a){b.fire("saveSnapshot");
setTimeout(function(){b.fire("saveSnapshot")},0);!1===t.onOk.call(this,a)&&(a.data.hide=!1)});this.state=CKEDITOR.DIALOG_STATE_IDLE;if(t.onCancel)this.on("cancel",function(a){!1===t.onCancel.call(this,a)&&(a.data.hide=!1)});var I=this,W=function(a){var b=I._.contents,c=!1,d;for(d in b)for(var f in b[d])if(c=a.call(this,b[d][f]))return};this.on("ok",function(a){W(function(b){if(b.validate){var c=b.validate(this),d="string"==typeof c||!1===c;d&&(a.data.hide=!1,a.stop());g.call(b,!d,"string"==typeof c?
c:void 0);return d}})},this,null,0);this.on("cancel",function(a){W(function(c){if(c.isChanged())return b.config.dialog_noConfirmCancel||confirm(b.lang.common.confirmCancel)||(a.data.hide=!1),!0})},this,null,0);this.parts.close.on("click",function(a){!1!==this.fire("cancel",{hide:!0}).hide&&this.hide();a.data.preventDefault()},this);this.changeFocus=p;var T=this._.element;b.focusManager.add(T,1);this.on("show",function(){T.on("keydown",m,this);if(CKEDITOR.env.gecko)T.on("keypress",x,this)});this.on("hide",
function(){T.removeListener("keydown",m);CKEDITOR.env.gecko&&T.removeListener("keypress",x);W(function(a){l.apply(a)})});this.on("iframeAdded",function(a){(new CKEDITOR.dom.document(a.data.iframe.$.contentWindow.document)).on("keydown",m,this,null,0)});this.on("show",function(){h();var a=1<I._.pageCount;b.config.dialog_startupFocusTab&&a?(I._.tabBarMode=!0,I._.tabs[I._.currentTabId][0].focus(),I._.currentFocusIndex=-1):this._.hasFocus||(this._.currentFocusIndex=a?-1:this._.focusList.length-1,t.onFocus?
(a=t.onFocus.call(this))&&a.focus():p(1))},this,null,4294967295);if(CKEDITOR.env.ie6Compat)this.on("load",function(){var a=this.getElement(),b=a.getFirst();b.remove();b.appendTo(a)},this);c(this);f(this);(new CKEDITOR.dom.text(t.title,CKEDITOR.document)).appendTo(this.parts.title);for(r=0;r<t.contents.length;r++)(w=t.contents[r])&&this.addPage(w);this.parts.tabs.on("click",function(a){var b=a.data.getTarget();b.hasClass("cke_dialog_tab")&&(b=b.$.id,this.selectPage(b.substring(4,b.lastIndexOf("_"))),
this._.tabBarMode&&(this._.tabBarMode=!1,this._.currentFocusIndex=-1,p(1)),a.data.preventDefault())},this);r=[];w=CKEDITOR.dialog._.uiElementBuilders.hbox.build(this,{type:"hbox",className:"cke_dialog_footer_buttons",widths:[],children:t.buttons},r).getChild();this.parts.footer.setHtml(r.join(""));for(r=0;r<w.length;r++)this._.buttons[w[r].id]=w[r]};CKEDITOR.dialog.prototype={destroy:function(){this.hide();this._.element.remove()},resize:function(){return function(a,b){this._.contentSize&&this._.contentSize.width==
a&&this._.contentSize.height==b||(CKEDITOR.dialog.fire("resize",{dialog:this,width:a,height:b},this._.editor),this.fire("resize",{width:a,height:b},this._.editor),this.parts.contents.setStyles({width:a+"px",height:b+"px"}),"rtl"==this._.editor.lang.dir&&this._.position&&(this._.position.x=CKEDITOR.document.getWindow().getViewPaneSize().width-this._.contentSize.width-parseInt(this._.element.getFirst().getStyle("right"),10)),this._.contentSize={width:a,height:b})}}(),getSize:function(){var a=this._.element.getFirst();
return{width:a.$.offsetWidth||0,height:a.$.offsetHeight||0}},move:function(a,b,c){var d=this._.element.getFirst(),f="rtl"==this._.editor.lang.dir,e="fixed"==d.getComputedStyle("position");CKEDITOR.env.ie&&d.setStyle("zoom","100%");e&&this._.position&&this._.position.x==a&&this._.position.y==b||(this._.position={x:a,y:b},e||(e=CKEDITOR.document.getWindow().getScrollPosition(),a+=e.x,b+=e.y),f&&(e=this.getSize(),a=CKEDITOR.document.getWindow().getViewPaneSize().width-e.width-a),b={top:(0<b?b:0)+"px"},
b[f?"right":"left"]=(0<a?a:0)+"px",d.setStyles(b),c&&(this._.moved=1))},getPosition:function(){return CKEDITOR.tools.extend({},this._.position)},show:function(){var a=this._.element,b=this.definition;a.getParent()&&a.getParent().equals(CKEDITOR.document.getBody())?a.setStyle("display","block"):a.appendTo(CKEDITOR.document.getBody());this.resize(this._.contentSize&&this._.contentSize.width||b.width||b.minWidth,this._.contentSize&&this._.contentSize.height||b.height||b.minHeight);this.reset();this.selectPage(this.definition.contents[0].id);
null===CKEDITOR.dialog._.currentZIndex&&(CKEDITOR.dialog._.currentZIndex=this._.editor.config.baseFloatZIndex);this._.element.getFirst().setStyle("z-index",CKEDITOR.dialog._.currentZIndex+=10);null===CKEDITOR.dialog._.currentTop?(CKEDITOR.dialog._.currentTop=this,this._.parentDialog=null,B(this._.editor)):(this._.parentDialog=CKEDITOR.dialog._.currentTop,this._.parentDialog.getElement().getFirst().$.style.zIndex-=Math.floor(this._.editor.config.baseFloatZIndex/2),CKEDITOR.dialog._.currentTop=this);
a.on("keydown",K);a.on("keyup",J);this._.hasFocus=!1;for(var c in b.contents)if(b.contents[c]){var a=b.contents[c],d=this._.tabs[a.id],f=a.requiredContent,e=0;if(d){for(var g in this._.contents[a.id]){var p=this._.contents[a.id][g];"hbox"!=p.type&&"vbox"!=p.type&&p.getInputElement()&&(p.requiredContent&&!this._.editor.activeFilter.check(p.requiredContent)?p.disable():(p.enable(),e++))}!e||f&&!this._.editor.activeFilter.check(f)?d[0].addClass("cke_dialog_tab_disabled"):d[0].removeClass("cke_dialog_tab_disabled")}}CKEDITOR.tools.setTimeout(function(){this.layout();
h(this);this.parts.dialog.setStyle("visibility","");this.fireOnce("load",{});CKEDITOR.ui.fire("ready",this);this.fire("show",{});this._.editor.fire("dialogShow",this);this._.parentDialog||this._.editor.focusManager.lock();this.foreach(function(a){a.setInitValue&&a.setInitValue()})},100,this)},layout:function(){var a=this.parts.dialog,b=this.getSize(),c=CKEDITOR.document.getWindow().getViewPaneSize(),d=(c.width-b.width)/2,f=(c.height-b.height)/2;CKEDITOR.env.ie6Compat||(b.height+(0<f?f:0)>c.height||
b.width+(0<d?d:0)>c.width?a.setStyle("position","absolute"):a.setStyle("position","fixed"));this.move(this._.moved?this._.position.x:d,this._.moved?this._.position.y:f)},foreach:function(a){for(var b in this._.contents)for(var c in this._.contents[b])a.call(this,this._.contents[b][c]);return this},reset:function(){var a=function(a){a.reset&&a.reset(1)};return function(){this.foreach(a);return this}}(),setupContent:function(){var a=arguments;this.foreach(function(b){b.setup&&b.setup.apply(b,a)})},
commitContent:function(){var a=arguments;this.foreach(function(b){CKEDITOR.env.ie&&this._.currentFocusIndex==b.focusIndex&&b.getInputElement().$.blur();b.commit&&b.commit.apply(b,a)})},hide:function(){if(this.parts.dialog.isVisible()){this.fire("hide",{});this._.editor.fire("dialogHide",this);this.selectPage(this._.tabIdList[0]);var a=this._.element;a.setStyle("display","none");this.parts.dialog.setStyle("visibility","hidden");for(L(this);CKEDITOR.dialog._.currentTop!=this;)CKEDITOR.dialog._.currentTop.hide();
if(this._.parentDialog){var b=this._.parentDialog.getElement().getFirst();b.setStyle("z-index",parseInt(b.$.style.zIndex,10)+Math.floor(this._.editor.config.baseFloatZIndex/2))}else x(this._.editor);if(CKEDITOR.dialog._.currentTop=this._.parentDialog)CKEDITOR.dialog._.currentZIndex-=10;else{CKEDITOR.dialog._.currentZIndex=null;a.removeListener("keydown",K);a.removeListener("keyup",J);var c=this._.editor;c.focus();setTimeout(function(){c.focusManager.unlock();CKEDITOR.env.iOS&&c.window.focus()},0)}delete this._.parentDialog;
this.foreach(function(a){a.resetInitValue&&a.resetInitValue()});this.setState(CKEDITOR.DIALOG_STATE_IDLE)}},addPage:function(a){if(!a.requiredContent||this._.editor.filter.check(a.requiredContent)){for(var b=[],c=a.label?' title\x3d"'+CKEDITOR.tools.htmlEncode(a.label)+'"':"",d=CKEDITOR.dialog._.uiElementBuilders.vbox.build(this,{type:"vbox",className:"cke_dialog_page_contents",children:a.elements,expand:!!a.expand,padding:a.padding,style:a.style||"width: 100%;"},b),f=this._.contents[a.id]={},e=d.getChild(),
g=0;d=e.shift();)d.notAllowed||"hbox"==d.type||"vbox"==d.type||g++,f[d.id]=d,"function"==typeof d.getChild&&e.push.apply(e,d.getChild());g||(a.hidden=!0);b=CKEDITOR.dom.element.createFromHtml(b.join(""));b.setAttribute("role","tabpanel");d=CKEDITOR.env;f="cke_"+a.id+"_"+CKEDITOR.tools.getNextNumber();c=CKEDITOR.dom.element.createFromHtml(['\x3ca class\x3d"cke_dialog_tab"',0<this._.pageCount?" cke_last":"cke_first",c,a.hidden?' style\x3d"display:none"':"",' id\x3d"',f,'"',d.gecko&&!d.hc?"":' href\x3d"javascript:void(0)"',
' tabIndex\x3d"-1" hidefocus\x3d"true" role\x3d"tab"\x3e',a.label,"\x3c/a\x3e"].join(""));b.setAttribute("aria-labelledby",f);this._.tabs[a.id]=[c,b];this._.tabIdList.push(a.id);!a.hidden&&this._.pageCount++;this._.lastTab=c;this.updateStyle();b.setAttribute("name",a.id);b.appendTo(this.parts.contents);c.unselectable();this.parts.tabs.append(c);a.accessKey&&(P(this,this,"CTRL+"+a.accessKey,S,O),this._.accessKeyMap["CTRL+"+a.accessKey]=a.id)}},selectPage:function(a){if(this._.currentTabId!=a&&!this._.tabs[a][0].hasClass("cke_dialog_tab_disabled")&&
!1!==this.fire("selectPage",{page:a,currentPage:this._.currentTabId})){for(var b in this._.tabs){var c=this._.tabs[b][0],f=this._.tabs[b][1];b!=a&&(c.removeClass("cke_dialog_tab_selected"),f.hide());f.setAttribute("aria-hidden",b!=a)}var e=this._.tabs[a];e[0].addClass("cke_dialog_tab_selected");CKEDITOR.env.ie6Compat||CKEDITOR.env.ie7Compat?(d(e[1]),e[1].show(),setTimeout(function(){d(e[1],1)},0)):e[1].show();this._.currentTabId=a;this._.currentTabIndex=CKEDITOR.tools.indexOf(this._.tabIdList,a)}},
updateStyle:function(){this.parts.dialog[(1===this._.pageCount?"add":"remove")+"Class"]("cke_single_page")},hidePage:function(b){var c=this._.tabs[b]&&this._.tabs[b][0];c&&1!=this._.pageCount&&c.isVisible()&&(b==this._.currentTabId&&this.selectPage(a.call(this)),c.hide(),this._.pageCount--,this.updateStyle())},showPage:function(a){if(a=this._.tabs[a]&&this._.tabs[a][0])a.show(),this._.pageCount++,this.updateStyle()},getElement:function(){return this._.element},getName:function(){return this._.name},
getContentElement:function(a,b){var c=this._.contents[a];return c&&c[b]},getValueOf:function(a,b){return this.getContentElement(a,b).getValue()},setValueOf:function(a,b,c){return this.getContentElement(a,b).setValue(c)},getButton:function(a){return this._.buttons[a]},click:function(a){return this._.buttons[a].click()},disableButton:function(a){return this._.buttons[a].disable()},enableButton:function(a){return this._.buttons[a].enable()},getPageCount:function(){return this._.pageCount},getParentEditor:function(){return this._.editor},
getSelectedElement:function(){return this.getParentEditor().getSelection().getSelectedElement()},addFocusable:function(a,b){if("undefined"==typeof b)b=this._.focusList.length,this._.focusList.push(new m(this,a,b));else{this._.focusList.splice(b,0,new m(this,a,b));for(var c=b+1;c<this._.focusList.length;c++)this._.focusList[c].focusIndex++}},setState:function(a){if(this.state!=a){this.state=a;if(a==CKEDITOR.DIALOG_STATE_BUSY){if(!this.parts.spinner){var b=this.getParentEditor().lang.dir,c={attributes:{"class":"cke_dialog_spinner"},
styles:{"float":"rtl"==b?"right":"left"}};c.styles["margin-"+("rtl"==b?"left":"right")]="8px";this.parts.spinner=CKEDITOR.document.createElement("div",c);this.parts.spinner.setHtml("\x26#8987;");this.parts.spinner.appendTo(this.parts.title,1)}this.parts.spinner.show();this.getButton("ok").disable()}else a==CKEDITOR.DIALOG_STATE_IDLE&&(this.parts.spinner&&this.parts.spinner.hide(),this.getButton("ok").enable());this.fire("state",a)}}};CKEDITOR.tools.extend(CKEDITOR.dialog,{add:function(a,b){this._.dialogDefinitions[a]&&
"function"!=typeof b||(this._.dialogDefinitions[a]=b)},exists:function(a){return!!this._.dialogDefinitions[a]},getCurrent:function(){return CKEDITOR.dialog._.currentTop},isTabEnabled:function(a,b,c){a=a.config.removeDialogTabs;return!(a&&a.match(new RegExp("(?:^|;)"+b+":"+c+"(?:$|;)","i")))},okButton:function(){var a=function(a,b){b=b||{};return CKEDITOR.tools.extend({id:"ok",type:"button",label:a.lang.common.ok,"class":"cke_dialog_ui_button_ok",onClick:function(a){a=a.data.dialog;!1!==a.fire("ok",
{hide:!0}).hide&&a.hide()}},b,!0)};a.type="button";a.override=function(b){return CKEDITOR.tools.extend(function(c){return a(c,b)},{type:"button"},!0)};return a}(),cancelButton:function(){var a=function(a,b){b=b||{};return CKEDITOR.tools.extend({id:"cancel",type:"button",label:a.lang.common.cancel,"class":"cke_dialog_ui_button_cancel",onClick:function(a){a=a.data.dialog;!1!==a.fire("cancel",{hide:!0}).hide&&a.hide()}},b,!0)};a.type="button";a.override=function(b){return CKEDITOR.tools.extend(function(c){return a(c,
b)},{type:"button"},!0)};return a}(),addUIElement:function(a,b){this._.uiElementBuilders[a]=b}});CKEDITOR.dialog._={uiElementBuilders:{},dialogDefinitions:{},currentTop:null,currentZIndex:null};CKEDITOR.event.implementOn(CKEDITOR.dialog);CKEDITOR.event.implementOn(CKEDITOR.dialog.prototype);var y={resizable:CKEDITOR.DIALOG_RESIZE_BOTH,minWidth:600,minHeight:400,buttons:[CKEDITOR.dialog.okButton,CKEDITOR.dialog.cancelButton]},H=function(a,b,c){for(var d=0,f;f=a[d];d++)if(f.id==b||c&&f[c]&&(f=H(f[c],
b,c)))return f;return null},w=function(a,b,c,d,f){if(c){for(var e=0,g;g=a[e];e++){if(g.id==c)return a.splice(e,0,b),b;if(d&&g[d]&&(g=w(g[d],b,c,d,!0)))return g}if(f)return null}a.push(b);return b},F=function(a,b,c){for(var d=0,f;f=a[d];d++){if(f.id==b)return a.splice(d,1);if(c&&f[c]&&(f=F(f[c],b,c)))return f}return null},n=function(a,c){this.dialog=a;for(var d=c.contents,f=0,e;e=d[f];f++)d[f]=e&&new b(a,e);CKEDITOR.tools.extend(this,c)};n.prototype={getContents:function(a){return H(this.contents,
a)},getButton:function(a){return H(this.buttons,a)},addContents:function(a,b){return w(this.contents,a,b)},addButton:function(a,b){return w(this.buttons,a,b)},removeContents:function(a){F(this.contents,a)},removeButton:function(a){F(this.buttons,a)}};b.prototype={get:function(a){return H(this.elements,a,"children")},add:function(a,b){return w(this.elements,a,b,"children")},remove:function(a){F(this.elements,a,"children")}};var r,C={},D,z={},K=function(a){var b=a.data.$.ctrlKey||a.data.$.metaKey,c=
a.data.$.altKey,d=a.data.$.shiftKey,f=String.fromCharCode(a.data.$.keyCode);(b=z[(b?"CTRL+":"")+(c?"ALT+":"")+(d?"SHIFT+":"")+f])&&b.length&&(b=b[b.length-1],b.keydown&&b.keydown.call(b.uiElement,b.dialog,b.key),a.data.preventDefault())},J=function(a){var b=a.data.$.ctrlKey||a.data.$.metaKey,c=a.data.$.altKey,d=a.data.$.shiftKey,f=String.fromCharCode(a.data.$.keyCode);(b=z[(b?"CTRL+":"")+(c?"ALT+":"")+(d?"SHIFT+":"")+f])&&b.length&&(b=b[b.length-1],b.keyup&&(b.keyup.call(b.uiElement,b.dialog,b.key),
a.data.preventDefault()))},P=function(a,b,c,d,f){(z[c]||(z[c]=[])).push({uiElement:a,dialog:b,key:c,keyup:f||a.accessKeyUp,keydown:d||a.accessKeyDown})},L=function(a){for(var b in z){for(var c=z[b],d=c.length-1;0<=d;d--)c[d].dialog!=a&&c[d].uiElement!=a||c.splice(d,1);0===c.length&&delete z[b]}},O=function(a,b){a._.accessKeyMap[b]&&a.selectPage(a._.accessKeyMap[b])},S=function(){};(function(){CKEDITOR.ui.dialog={uiElement:function(a,b,c,d,f,e,g){if(!(4>arguments.length)){var h=(d.call?d(b):d)||"div",
p=["\x3c",h," "],k=(f&&f.call?f(b):f)||{},l=(e&&e.call?e(b):e)||{},E=(g&&g.call?g.call(this,a,b):g)||"",A=this.domId=l.id||CKEDITOR.tools.getNextId()+"_uiElement";b.requiredContent&&!a.getParentEditor().filter.check(b.requiredContent)&&(k.display="none",this.notAllowed=!0);l.id=A;var n={};b.type&&(n["cke_dialog_ui_"+b.type]=1);b.className&&(n[b.className]=1);b.disabled&&(n.cke_disabled=1);for(var m=l["class"]&&l["class"].split?l["class"].split(" "):[],A=0;A<m.length;A++)m[A]&&(n[m[A]]=1);m=[];for(A in n)m.push(A);
l["class"]=m.join(" ");b.title&&(l.title=b.title);n=(b.style||"").split(";");b.align&&(m=b.align,k["margin-left"]="left"==m?0:"auto",k["margin-right"]="right"==m?0:"auto");for(A in k)n.push(A+":"+k[A]);b.hidden&&n.push("display:none");for(A=n.length-1;0<=A;A--)""===n[A]&&n.splice(A,1);0<n.length&&(l.style=(l.style?l.style+"; ":"")+n.join("; "));for(A in l)p.push(A+'\x3d"'+CKEDITOR.tools.htmlEncode(l[A])+'" ');p.push("\x3e",E,"\x3c/",h,"\x3e");c.push(p.join(""));(this._||(this._={})).dialog=a;"boolean"==
typeof b.isChanged&&(this.isChanged=function(){return b.isChanged});"function"==typeof b.isChanged&&(this.isChanged=b.isChanged);"function"==typeof b.setValue&&(this.setValue=CKEDITOR.tools.override(this.setValue,function(a){return function(c){a.call(this,b.setValue.call(this,c))}}));"function"==typeof b.getValue&&(this.getValue=CKEDITOR.tools.override(this.getValue,function(a){return function(){return b.getValue.call(this,a.call(this))}}));CKEDITOR.event.implementOn(this);this.registerEvents(b);
this.accessKeyUp&&this.accessKeyDown&&b.accessKey&&P(this,a,"CTRL+"+b.accessKey);var t=this;a.on("load",function(){var b=t.getInputElement();if(b){var c=t.type in{checkbox:1,ratio:1}&&CKEDITOR.env.ie&&8>CKEDITOR.env.version?"cke_dialog_ui_focused":"";b.on("focus",function(){a._.tabBarMode=!1;a._.hasFocus=!0;t.fire("focus");c&&this.addClass(c)});b.on("blur",function(){t.fire("blur");c&&this.removeClass(c)})}});CKEDITOR.tools.extend(this,b);this.keyboardFocusable&&(this.tabIndex=b.tabIndex||0,this.focusIndex=
a._.focusList.push(this)-1,this.on("focus",function(){a._.currentFocusIndex=t.focusIndex}))}},hbox:function(a,b,c,d,f){if(!(4>arguments.length)){this._||(this._={});var e=this._.children=b,g=f&&f.widths||null,h=f&&f.height||null,p,k={role:"presentation"};f&&f.align&&(k.align=f.align);CKEDITOR.ui.dialog.uiElement.call(this,a,f||{type:"hbox"},d,"table",{},k,function(){var a=['\x3ctbody\x3e\x3ctr class\x3d"cke_dialog_ui_hbox"\x3e'];for(p=0;p<c.length;p++){var b="cke_dialog_ui_hbox_child",d=[];0===p&&
(b="cke_dialog_ui_hbox_first");p==c.length-1&&(b="cke_dialog_ui_hbox_last");a.push('\x3ctd class\x3d"',b,'" role\x3d"presentation" ');g?g[p]&&d.push("width:"+t(g[p])):d.push("width:"+Math.floor(100/c.length)+"%");h&&d.push("height:"+t(h));f&&void 0!==f.padding&&d.push("padding:"+t(f.padding));CKEDITOR.env.ie&&CKEDITOR.env.quirks&&e[p].align&&d.push("text-align:"+e[p].align);0<d.length&&a.push('style\x3d"'+d.join("; ")+'" ');a.push("\x3e",c[p],"\x3c/td\x3e")}a.push("\x3c/tr\x3e\x3c/tbody\x3e");return a.join("")})}},
vbox:function(a,b,c,d,f){if(!(3>arguments.length)){this._||(this._={});var e=this._.children=b,g=f&&f.width||null,h=f&&f.heights||null;CKEDITOR.ui.dialog.uiElement.call(this,a,f||{type:"vbox"},d,"div",null,{role:"presentation"},function(){var b=['\x3ctable role\x3d"presentation" cellspacing\x3d"0" border\x3d"0" '];b.push('style\x3d"');f&&f.expand&&b.push("height:100%;");b.push("width:"+t(g||"100%"),";");CKEDITOR.env.webkit&&b.push("float:none;");b.push('"');b.push('align\x3d"',CKEDITOR.tools.htmlEncode(f&&
f.align||("ltr"==a.getParentEditor().lang.dir?"left":"right")),'" ');b.push("\x3e\x3ctbody\x3e");for(var d=0;d<c.length;d++){var p=[];b.push('\x3ctr\x3e\x3ctd role\x3d"presentation" ');g&&p.push("width:"+t(g||"100%"));h?p.push("height:"+t(h[d])):f&&f.expand&&p.push("height:"+Math.floor(100/c.length)+"%");f&&void 0!==f.padding&&p.push("padding:"+t(f.padding));CKEDITOR.env.ie&&CKEDITOR.env.quirks&&e[d].align&&p.push("text-align:"+e[d].align);0<p.length&&b.push('style\x3d"',p.join("; "),'" ');b.push(' class\x3d"cke_dialog_ui_vbox_child"\x3e',
c[d],"\x3c/td\x3e\x3c/tr\x3e")}b.push("\x3c/tbody\x3e\x3c/table\x3e");return b.join("")})}}}})();CKEDITOR.ui.dialog.uiElement.prototype={getElement:function(){return CKEDITOR.document.getById(this.domId)},getInputElement:function(){return this.getElement()},getDialog:function(){return this._.dialog},setValue:function(a,b){this.getInputElement().setValue(a);!b&&this.fire("change",{value:a});return this},getValue:function(){return this.getInputElement().getValue()},isChanged:function(){return!1},selectParentTab:function(){for(var a=
this.getInputElement();(a=a.getParent())&&-1==a.$.className.search("cke_dialog_page_contents"););if(!a)return this;a=a.getAttribute("name");this._.dialog._.currentTabId!=a&&this._.dialog.selectPage(a);return this},focus:function(){this.selectParentTab().getInputElement().focus();return this},registerEvents:function(a){var b=/^on([A-Z]\w+)/,c,d=function(a,b,c,d){b.on("load",function(){a.getInputElement().on(c,d,a)})},f;for(f in a)if(c=f.match(b))this.eventProcessors[f]?this.eventProcessors[f].call(this,
this._.dialog,a[f]):d(this,this._.dialog,c[1].toLowerCase(),a[f]);return this},eventProcessors:{onLoad:function(a,b){a.on("load",b,this)},onShow:function(a,b){a.on("show",b,this)},onHide:function(a,b){a.on("hide",b,this)}},accessKeyDown:function(){this.focus()},accessKeyUp:function(){},disable:function(){var a=this.getElement();this.getInputElement().setAttribute("disabled","true");a.addClass("cke_disabled")},enable:function(){var a=this.getElement();this.getInputElement().removeAttribute("disabled");
a.removeClass("cke_disabled")},isEnabled:function(){return!this.getElement().hasClass("cke_disabled")},isVisible:function(){return this.getInputElement().isVisible()},isFocusable:function(){return this.isEnabled()&&this.isVisible()?!0:!1}};CKEDITOR.ui.dialog.hbox.prototype=CKEDITOR.tools.extend(new CKEDITOR.ui.dialog.uiElement,{getChild:function(a){if(1>arguments.length)return this._.children.concat();a.splice||(a=[a]);return 2>a.length?this._.children[a[0]]:this._.children[a[0]]&&this._.children[a[0]].getChild?
this._.children[a[0]].getChild(a.slice(1,a.length)):null}},!0);CKEDITOR.ui.dialog.vbox.prototype=new CKEDITOR.ui.dialog.hbox;(function(){var a={build:function(a,b,c){for(var d=b.children,f,e=[],g=[],h=0;h<d.length&&(f=d[h]);h++){var p=[];e.push(p);g.push(CKEDITOR.dialog._.uiElementBuilders[f.type].build(a,f,p))}return new CKEDITOR.ui.dialog[b.type](a,g,e,c,b)}};CKEDITOR.dialog.addUIElement("hbox",a);CKEDITOR.dialog.addUIElement("vbox",a)})();CKEDITOR.dialogCommand=function(a,b){this.dialogName=a;
CKEDITOR.tools.extend(this,b,!0)};CKEDITOR.dialogCommand.prototype={exec:function(a){a.openDialog(this.dialogName)},canUndo:!1,editorFocus:1};(function(){var a=/^([a]|[^a])+$/,b=/^\d*$/,c=/^\d*(?:\.\d+)?$/,d=/^(((\d*(\.\d+))|(\d*))(px|\%)?)?$/,f=/^(((\d*(\.\d+))|(\d*))(px|em|ex|in|cm|mm|pt|pc|\%)?)?$/i,e=/^(\s*[\w-]+\s*:\s*[^:;]+(?:;|$))*$/;CKEDITOR.VALIDATE_OR=1;CKEDITOR.VALIDATE_AND=2;CKEDITOR.dialog.validate={functions:function(){var a=arguments;return function(){var b=this&&this.getValue?this.getValue():
a[0],c,d=CKEDITOR.VALIDATE_AND,f=[],e;for(e=0;e<a.length;e++)if("function"==typeof a[e])f.push(a[e]);else break;e<a.length&&"string"==typeof a[e]&&(c=a[e],e++);e<a.length&&"number"==typeof a[e]&&(d=a[e]);var g=d==CKEDITOR.VALIDATE_AND?!0:!1;for(e=0;e<f.length;e++)g=d==CKEDITOR.VALIDATE_AND?g&&f[e](b):g||f[e](b);return g?!0:c}},regex:function(a,b){return function(c){c=this&&this.getValue?this.getValue():c;return a.test(c)?!0:b}},notEmpty:function(b){return this.regex(a,b)},integer:function(a){return this.regex(b,
a)},number:function(a){return this.regex(c,a)},cssLength:function(a){return this.functions(function(a){return f.test(CKEDITOR.tools.trim(a))},a)},htmlLength:function(a){return this.functions(function(a){return d.test(CKEDITOR.tools.trim(a))},a)},inlineStyle:function(a){return this.functions(function(a){return e.test(CKEDITOR.tools.trim(a))},a)},equals:function(a,b){return this.functions(function(b){return b==a},b)},notEqual:function(a,b){return this.functions(function(b){return b!=a},b)}};CKEDITOR.on("instanceDestroyed",
function(a){if(CKEDITOR.tools.isEmpty(CKEDITOR.instances)){for(var b;b=CKEDITOR.dialog._.currentTop;)b.hide();for(var c in C)C[c].remove();C={}}a=a.editor._.storedDialogs;for(var d in a)a[d].destroy()})})();CKEDITOR.tools.extend(CKEDITOR.editor.prototype,{openDialog:function(a,b){var c=null,d=CKEDITOR.dialog._.dialogDefinitions[a];null===CKEDITOR.dialog._.currentTop&&B(this);if("function"==typeof d)c=this._.storedDialogs||(this._.storedDialogs={}),c=c[a]||(c[a]=new CKEDITOR.dialog(this,a)),b&&b.call(c,
c),c.show();else{if("failed"==d)throw x(this),Error('[CKEDITOR.dialog.openDialog] Dialog "'+a+'" failed when loading definition.');"string"==typeof d&&CKEDITOR.scriptLoader.load(CKEDITOR.getUrl(d),function(){"function"!=typeof CKEDITOR.dialog._.dialogDefinitions[a]&&(CKEDITOR.dialog._.dialogDefinitions[a]="failed");this.openDialog(a,b)},this,0,1)}CKEDITOR.skin.loadPart("dialog");return c}})}(),CKEDITOR.plugins.add("dialog",{requires:"dialogui",init:function(a){a.on("doubleclick",function(e){e.data.dialog&&
a.openDialog(e.data.dialog)},null,null,999)}}),"use strict",function(){function a(a,b,c){b.type||(b.type="auto");if(c&&!1===a.fire("beforePaste",b)||!b.dataValue&&b.dataTransfer.isEmpty())return!1;b.dataValue||(b.dataValue="");if(CKEDITOR.env.gecko&&"drop"==b.method&&a.toolbox)a.once("afterPaste",function(){a.toolbox.focus()});return a.fire("paste",b)}function e(b){function c(){var a=b.editable();if(CKEDITOR.plugins.clipboard.isCustomCopyCutSupported){var d=function(a){b.readOnly&&"cut"==a.name||
z.initPasteDataTransfer(a,b);a.data.preventDefault()};a.on("copy",d);a.on("cut",d);a.on("cut",function(){b.readOnly||b.extractSelectedHtml()},null,null,999)}a.on(z.mainPasteEvent,function(a){"beforepaste"==z.mainPasteEvent&&K||r(a)});"beforepaste"==z.mainPasteEvent&&(a.on("paste",function(a){J||(g(),a.data.preventDefault(),r(a),k("paste")||b.openDialog("paste"))}),a.on("contextmenu",h,null,null,0),a.on("beforepaste",function(a){!a.data||a.data.$.ctrlKey||a.data.$.shiftKey||h()},null,null,0));a.on("beforecut",
function(){!K&&l(b)});var e;a.attachListener(CKEDITOR.env.ie?a:b.document.getDocumentElement(),"mouseup",function(){e=setTimeout(function(){C()},0)});b.on("destroy",function(){clearTimeout(e)});a.on("keyup",C)}function d(a){return{type:a,canUndo:"cut"==a,startDisabled:!0,fakeKeystroke:"cut"==a?CKEDITOR.CTRL+88:CKEDITOR.CTRL+67,exec:function(){"cut"==this.type&&l();var a;var c=this.type;if(CKEDITOR.env.ie)a=k(c);else try{a=b.document.$.execCommand(c,!1,null)}catch(d){a=!1}a||b.showNotification(b.lang.clipboard[this.type+
"Error"]);return a}}}function e(){return{canUndo:!1,async:!0,fakeKeystroke:CKEDITOR.CTRL+86,exec:function(b,c){var d=this,f=function(c,f){c&&a(b,c,!!f);b.fire("afterCommandExec",{name:"paste",command:d,returnValue:!!c})};"string"==typeof c?f({dataValue:c,method:"paste",dataTransfer:z.initPasteDataTransfer()},1):b.getClipboardData(f)}}}function g(){J=1;setTimeout(function(){J=0},100)}function h(){K=1;setTimeout(function(){K=0},10)}function k(a){var c=b.document,d=c.getBody(),e=!1,g=function(){e=!0};
d.on(a,g);7<CKEDITOR.env.version?c.$.execCommand(a):c.$.selection.createRange().execCommand(a);d.removeListener(a,g);return e}function l(){if(CKEDITOR.env.ie&&!CKEDITOR.env.quirks){var a=b.getSelection(),c,d,e;a.getType()==CKEDITOR.SELECTION_ELEMENT&&(c=a.getSelectedElement())&&(d=a.getRanges()[0],e=b.document.createText(""),e.insertBefore(c),d.setStartBefore(e),d.setEndAfter(c),a.selectRanges([d]),setTimeout(function(){c.getParent()&&(e.remove(),a.selectElement(c))},0))}}function m(a,c){var d=b.document,
e=b.editable(),g=function(a){a.cancel()},h;if(!d.getById("cke_pastebin")){var p=b.getSelection(),k=p.createBookmarks();CKEDITOR.env.ie&&p.root.fire("selectionchange");var l=new CKEDITOR.dom.element(!CKEDITOR.env.webkit&&!e.is("body")||CKEDITOR.env.ie?"div":"body",d);l.setAttributes({id:"cke_pastebin","data-cke-temp":"1"});var n=0,d=d.getWindow();CKEDITOR.env.webkit?(e.append(l),l.addClass("cke_editable"),e.is("body")||(n="static"!=e.getComputedStyle("position")?e:CKEDITOR.dom.element.get(e.$.offsetParent),
n=n.getDocumentPosition().y)):e.getAscendant(CKEDITOR.env.ie?"body":"html",1).append(l);l.setStyles({position:"absolute",top:d.getScrollPosition().y-n+10+"px",width:"1px",height:Math.max(1,d.getViewPaneSize().height-20)+"px",overflow:"hidden",margin:0,padding:0});CKEDITOR.env.safari&&l.setStyles(CKEDITOR.tools.cssVendorPrefix("user-select","text"));(n=l.getParent().isReadOnly())?(l.setOpacity(0),l.setAttribute("contenteditable",!0)):l.setStyle("ltr"==b.config.contentsLangDirection?"left":"right",
"-10000px");b.on("selectionChange",g,null,null,0);if(CKEDITOR.env.webkit||CKEDITOR.env.gecko)h=e.once("blur",g,null,null,-100);n&&l.focus();n=new CKEDITOR.dom.range(l);n.selectNodeContents(l);var t=n.select();CKEDITOR.env.ie&&(h=e.once("blur",function(){b.lockSelection(t)}));var x=CKEDITOR.document.getWindow().getScrollPosition().y;setTimeout(function(){CKEDITOR.env.webkit&&(CKEDITOR.document.getBody().$.scrollTop=x);h&&h.removeListener();CKEDITOR.env.ie&&e.focus();p.selectBookmarks(k);l.remove();
var a;CKEDITOR.env.webkit&&(a=l.getFirst())&&a.is&&a.hasClass("Apple-style-span")&&(l=a);b.removeListener("selectionChange",g);c(l.getHtml())},0)}}function F(){if("paste"==z.mainPasteEvent)return b.fire("beforePaste",{type:"auto",method:"paste"}),!1;b.focus();g();var a=b.focusManager;a.lock();if(b.editable().fire(z.mainPasteEvent)&&!k("paste"))return a.unlock(),!1;a.unlock();return!0}function n(a){if("wysiwyg"==b.mode)switch(a.data.keyCode){case CKEDITOR.CTRL+86:case CKEDITOR.SHIFT+45:a=b.editable();
g();"paste"==z.mainPasteEvent&&a.fire("beforepaste");break;case CKEDITOR.CTRL+88:case CKEDITOR.SHIFT+46:b.fire("saveSnapshot"),setTimeout(function(){b.fire("saveSnapshot")},50)}}function r(c){var d={type:"auto",method:"paste",dataTransfer:z.initPasteDataTransfer(c)};d.dataTransfer.cacheData();var e=!1!==b.fire("beforePaste",d);e&&z.canClipboardApiBeTrusted(d.dataTransfer,b)?(c.data.preventDefault(),setTimeout(function(){a(b,d)},0)):m(c,function(c){d.dataValue=c.replace(/<span[^>]+data-cke-bookmark[^<]*?<\/span>/ig,
"");e&&a(b,d)})}function C(){if("wysiwyg"==b.mode){var a=D("paste");b.getCommand("cut").setState(D("cut"));b.getCommand("copy").setState(D("copy"));b.getCommand("paste").setState(a);b.fire("pasteState",a)}}function D(a){if(P&&a in{paste:1,cut:1})return CKEDITOR.TRISTATE_DISABLED;if("paste"==a)return CKEDITOR.TRISTATE_OFF;a=b.getSelection();var c=a.getRanges();return a.getType()==CKEDITOR.SELECTION_NONE||1==c.length&&c[0].collapsed?CKEDITOR.TRISTATE_DISABLED:CKEDITOR.TRISTATE_OFF}var z=CKEDITOR.plugins.clipboard,
K=0,J=0,P=0;(function(){b.on("key",n);b.on("contentDom",c);b.on("selectionChange",function(a){P=a.data.selection.getRanges()[0].checkReadOnly();C()});b.contextMenu&&b.contextMenu.addListener(function(a,b){P=b.getRanges()[0].checkReadOnly();return{cut:D("cut"),copy:D("copy"),paste:D("paste")}})})();(function(){function a(c,d,e,g,h){var p=b.lang.clipboard[d];b.addCommand(d,e);b.ui.addButton&&b.ui.addButton(c,{label:p,command:d,toolbar:"clipboard,"+g});b.addMenuItems&&b.addMenuItem(d,{label:p,command:d,
group:"clipboard",order:h})}a("Cut","cut",d("cut"),10,1);a("Copy","copy",d("copy"),20,4);a("Paste","paste",e(),30,8)})();b.getClipboardData=function(a,c){function d(a){a.removeListener();a.cancel();c(a.data)}function e(a){a.removeListener();a.cancel();k=!0;c({type:p,dataValue:a.data.dataValue,dataTransfer:a.data.dataTransfer,method:"paste"})}function g(){this.customTitle=a&&a.title}var h=!1,p="auto",k=!1;c||(c=a,a=null);b.on("paste",d,null,null,0);b.on("beforePaste",function(a){a.removeListener();
h=!0;p=a.data.type},null,null,1E3);!1===F()&&(b.removeListener("paste",d),h&&b.fire("pasteDialog",g)?(b.on("pasteDialogCommit",e),b.on("dialogHide",function(a){a.removeListener();a.data.removeListener("pasteDialogCommit",e);setTimeout(function(){k||c(null)},10)})):c(null))}}function d(a){if(CKEDITOR.env.webkit){if(!a.match(/^[^<]*$/g)&&!a.match(/^(<div><br( ?\/)?><\/div>|<div>[^<]*<\/div>)*$/gi))return"html"}else if(CKEDITOR.env.ie){if(!a.match(/^([^<]|<br( ?\/)?>)*$/gi)&&!a.match(/^(<p>([^<]|<br( ?\/)?>)*<\/p>|(\r\n))*$/gi))return"html"}else if(CKEDITOR.env.gecko){if(!a.match(/^([^<]|<br( ?\/)?>)*$/gi))return"html"}else return"html";
return"htmlifiedtext"}function g(a,b){function c(a){return CKEDITOR.tools.repeat("\x3c/p\x3e\x3cp\x3e",~~(a/2))+(1==a%2?"\x3cbr\x3e":"")}b=b.replace(/\s+/g," ").replace(/> +</g,"\x3e\x3c").replace(/<br ?\/>/gi,"\x3cbr\x3e");b=b.replace(/<\/?[A-Z]+>/g,function(a){return a.toLowerCase()});if(b.match(/^[^<]$/))return b;CKEDITOR.env.webkit&&-1<b.indexOf("\x3cdiv\x3e")&&(b=b.replace(/^(<div>(<br>|)<\/div>)(?!$|(<div>(<br>|)<\/div>))/g,"\x3cbr\x3e").replace(/^(<div>(<br>|)<\/div>){2}(?!$)/g,"\x3cdiv\x3e\x3c/div\x3e"),
b.match(/<div>(<br>|)<\/div>/)&&(b="\x3cp\x3e"+b.replace(/(<div>(<br>|)<\/div>)+/g,function(a){return c(a.split("\x3c/div\x3e\x3cdiv\x3e").length+1)})+"\x3c/p\x3e"),b=b.replace(/<\/div><div>/g,"\x3cbr\x3e"),b=b.replace(/<\/?div>/g,""));CKEDITOR.env.gecko&&a.enterMode!=CKEDITOR.ENTER_BR&&(CKEDITOR.env.gecko&&(b=b.replace(/^<br><br>$/,"\x3cbr\x3e")),-1<b.indexOf("\x3cbr\x3e\x3cbr\x3e")&&(b="\x3cp\x3e"+b.replace(/(<br>){2,}/g,function(a){return c(a.length/4)})+"\x3c/p\x3e"));return m(a,b)}function l(){function a(){var b=
{},c;for(c in CKEDITOR.dtd)"$"!=c.charAt(0)&&"div"!=c&&"span"!=c&&(b[c]=1);return b}var b={};return{get:function(c){return"plain-text"==c?b.plainText||(b.plainText=new CKEDITOR.filter("br")):"semantic-content"==c?((c=b.semanticContent)||(c=new CKEDITOR.filter,c.allow({$1:{elements:a(),attributes:!0,styles:!1,classes:!1}}),c=b.semanticContent=c),c):c?new CKEDITOR.filter(c):null}}}function k(a,b,c){b=CKEDITOR.htmlParser.fragment.fromHtml(b);var d=new CKEDITOR.htmlParser.basicWriter;c.applyTo(b,!0,!1,
a.activeEnterMode);b.writeHtml(d);return d.getHtml()}function m(a,b){a.enterMode==CKEDITOR.ENTER_BR?b=b.replace(/(<\/p><p>)+/g,function(a){return CKEDITOR.tools.repeat("\x3cbr\x3e",a.length/7*2)}).replace(/<\/?p>/g,""):a.enterMode==CKEDITOR.ENTER_DIV&&(b=b.replace(/<(\/)?p>/g,"\x3c$1div\x3e"));return b}function h(a){a.data.preventDefault();a.data.$.dataTransfer.dropEffect="none"}function b(b){var c=CKEDITOR.plugins.clipboard;b.on("contentDom",function(){function d(c,e,g){e.select();a(b,{dataTransfer:g,
method:"drop"},1);g.sourceEditor.fire("saveSnapshot");g.sourceEditor.editable().extractHtmlFromRange(c);g.sourceEditor.getSelection().selectRanges([c]);g.sourceEditor.fire("saveSnapshot")}function e(d,g){d.select();a(b,{dataTransfer:g,method:"drop"},1);c.resetDragDataTransfer()}function g(a,c,d){var e={$:a.data.$,target:a.data.getTarget()};c&&(e.dragRange=c);d&&(e.dropRange=d);!1===b.fire(a.name,e)&&a.data.preventDefault()}function h(a){a.type!=CKEDITOR.NODE_ELEMENT&&(a=a.getParent());return a.getChildCount()}
var k=b.editable(),l=CKEDITOR.plugins.clipboard.getDropTarget(b),m=b.ui.space("top"),F=b.ui.space("bottom");c.preventDefaultDropOnElement(m);c.preventDefaultDropOnElement(F);k.attachListener(l,"dragstart",g);k.attachListener(b,"dragstart",c.resetDragDataTransfer,c,null,1);k.attachListener(b,"dragstart",function(a){c.initDragDataTransfer(a,b)},null,null,2);k.attachListener(b,"dragstart",function(){var a=c.dragRange=b.getSelection().getRanges()[0];CKEDITOR.env.ie&&10>CKEDITOR.env.version&&(c.dragStartContainerChildCount=
a?h(a.startContainer):null,c.dragEndContainerChildCount=a?h(a.endContainer):null)},null,null,100);k.attachListener(l,"dragend",g);k.attachListener(b,"dragend",c.initDragDataTransfer,c,null,1);k.attachListener(b,"dragend",c.resetDragDataTransfer,c,null,100);k.attachListener(l,"dragover",function(a){var b=a.data.getTarget();b&&b.is&&b.is("html")?a.data.preventDefault():CKEDITOR.env.ie&&CKEDITOR.plugins.clipboard.isFileApiSupported&&a.data.$.dataTransfer.types.contains("Files")&&a.data.preventDefault()});
k.attachListener(l,"drop",function(a){if(!a.data.$.defaultPrevented){a.data.preventDefault();var d=a.data.getTarget();if(!d.isReadOnly()||d.type==CKEDITOR.NODE_ELEMENT&&d.is("html")){var d=c.getRangeAtDropPosition(a,b),e=c.dragRange;d&&g(a,e,d)}}},null,null,9999);k.attachListener(b,"drop",c.initDragDataTransfer,c,null,1);k.attachListener(b,"drop",function(a){if(a=a.data){var g=a.dropRange,h=a.dragRange,k=a.dataTransfer;k.getTransferType(b)==CKEDITOR.DATA_TRANSFER_INTERNAL?setTimeout(function(){c.internalDrop(h,
g,k,b)},0):k.getTransferType(b)==CKEDITOR.DATA_TRANSFER_CROSS_EDITORS?d(h,g,k):e(g,k)}},null,null,9999)})}CKEDITOR.plugins.add("clipboard",{requires:"dialog",init:function(a){var c,h=l();a.config.forcePasteAsPlainText?c="plain-text":a.config.pasteFilter?c=a.config.pasteFilter:!CKEDITOR.env.webkit||"pasteFilter"in a.config||(c="semantic-content");a.pasteFilter=h.get(c);e(a);b(a);CKEDITOR.dialog.add("paste",CKEDITOR.getUrl(this.path+"dialogs/paste.js"));a.on("paste",function(b){b.data.dataTransfer||
(b.data.dataTransfer=new CKEDITOR.plugins.clipboard.dataTransfer);if(!b.data.dataValue){var c=b.data.dataTransfer,d=c.getData("text/html");if(d)b.data.dataValue=d,b.data.type="html";else if(d=c.getData("text/plain"))b.data.dataValue=a.editable().transformPlainTextToHtml(d),b.data.type="text"}},null,null,1);a.on("paste",function(a){var b=a.data.dataValue,c=CKEDITOR.dtd.$block;-1<b.indexOf("Apple-")&&(b=b.replace(/<span class="Apple-converted-space">&nbsp;<\/span>/gi," "),"html"!=a.data.type&&(b=b.replace(/<span class="Apple-tab-span"[^>]*>([^<]*)<\/span>/gi,
function(a,b){return b.replace(/\t/g,"\x26nbsp;\x26nbsp; \x26nbsp;")})),-1<b.indexOf('\x3cbr class\x3d"Apple-interchange-newline"\x3e')&&(a.data.startsWithEOL=1,a.data.preSniffing="html",b=b.replace(/<br class="Apple-interchange-newline">/,"")),b=b.replace(/(<[^>]+) class="Apple-[^"]*"/gi,"$1"));if(b.match(/^<[^<]+cke_(editable|contents)/i)){var d,f,e=new CKEDITOR.dom.element("div");for(e.setHtml(b);1==e.getChildCount()&&(d=e.getFirst())&&d.type==CKEDITOR.NODE_ELEMENT&&(d.hasClass("cke_editable")||
d.hasClass("cke_contents"));)e=f=d;f&&(b=f.getHtml().replace(/<br>$/i,""))}CKEDITOR.env.ie?b=b.replace(/^&nbsp;(?: |\r\n)?<(\w+)/g,function(b,d){return d.toLowerCase()in c?(a.data.preSniffing="html","\x3c"+d):b}):CKEDITOR.env.webkit?b=b.replace(/<\/(\w+)><div><br><\/div>$/,function(b,d){return d in c?(a.data.endsWithEOL=1,"\x3c/"+d+"\x3e"):b}):CKEDITOR.env.gecko&&(b=b.replace(/(\s)<br>$/,"$1"));a.data.dataValue=b},null,null,3);a.on("paste",function(b){b=b.data;var c=b.type,e=b.dataValue,p,l=a.config.clipboard_defaultContentType||
"html",m=b.dataTransfer.getTransferType(a);p="html"==c||"html"==b.preSniffing?"html":d(e);"htmlifiedtext"==p&&(e=g(a.config,e));"text"==c&&"html"==p?e=k(a,e,h.get("plain-text")):m==CKEDITOR.DATA_TRANSFER_EXTERNAL&&a.pasteFilter&&!b.dontFilter&&(e=k(a,e,a.pasteFilter));b.startsWithEOL&&(e='\x3cbr data-cke-eol\x3d"1"\x3e'+e);b.endsWithEOL&&(e+='\x3cbr data-cke-eol\x3d"1"\x3e');"auto"==c&&(c="html"==p||"html"==l?"html":"text");b.type=c;b.dataValue=e;delete b.preSniffing;delete b.startsWithEOL;delete b.endsWithEOL},
null,null,6);a.on("paste",function(b){b=b.data;b.dataValue&&(a.insertHtml(b.dataValue,b.type,b.range),setTimeout(function(){a.fire("afterPaste")},0))},null,null,1E3);a.on("pasteDialog",function(b){setTimeout(function(){a.openDialog("paste",b.data)},0)})}});CKEDITOR.plugins.clipboard={isCustomCopyCutSupported:!CKEDITOR.env.ie&&!CKEDITOR.env.iOS,isCustomDataTypesSupported:!CKEDITOR.env.ie,isFileApiSupported:!CKEDITOR.env.ie||9<CKEDITOR.env.version,mainPasteEvent:CKEDITOR.env.ie&&!CKEDITOR.env.edge?
"beforepaste":"paste",canClipboardApiBeTrusted:function(a,b){return a.getTransferType(b)!=CKEDITOR.DATA_TRANSFER_EXTERNAL||CKEDITOR.env.chrome&&!a.isEmpty()||CKEDITOR.env.gecko&&(a.getData("text/html")||a.getFilesCount())?!0:!1},getDropTarget:function(a){var b=a.editable();return CKEDITOR.env.ie&&9>CKEDITOR.env.version||b.isInline()?b:a.document},fixSplitNodesAfterDrop:function(a,b,c,d){function e(a,c,d){var f=a;f.type==CKEDITOR.NODE_TEXT&&(f=a.getParent());if(f.equals(c)&&d!=c.getChildCount())return a=
b.startContainer.getChild(b.startOffset-1),c=b.startContainer.getChild(b.startOffset),a&&a.type==CKEDITOR.NODE_TEXT&&c&&c.type==CKEDITOR.NODE_TEXT&&(d=a.getLength(),a.setText(a.getText()+c.getText()),c.remove(),b.setStart(a,d),b.collapse(!0)),!0}var g=b.startContainer;"number"==typeof d&&"number"==typeof c&&g.type==CKEDITOR.NODE_ELEMENT&&(e(a.startContainer,g,c)||e(a.endContainer,g,d))},isDropRangeAffectedByDragRange:function(a,b){var c=b.startContainer,d=b.endOffset;return a.endContainer.equals(c)&&
a.endOffset<=d||a.startContainer.getParent().equals(c)&&a.startContainer.getIndex()<d||a.endContainer.getParent().equals(c)&&a.endContainer.getIndex()<d?!0:!1},internalDrop:function(b,c,d,e){var g=CKEDITOR.plugins.clipboard,h=e.editable(),k,l;e.fire("saveSnapshot");e.fire("lockSnapshot",{dontUpdate:1});CKEDITOR.env.ie&&10>CKEDITOR.env.version&&this.fixSplitNodesAfterDrop(b,c,g.dragStartContainerChildCount,g.dragEndContainerChildCount);(l=this.isDropRangeAffectedByDragRange(b,c))||(k=b.createBookmark(!1));
g=c.clone().createBookmark(!1);l&&(k=b.createBookmark(!1));b=k.startNode;c=k.endNode;l=g.startNode;c&&b.getPosition(l)&CKEDITOR.POSITION_PRECEDING&&c.getPosition(l)&CKEDITOR.POSITION_FOLLOWING&&l.insertBefore(b);b=e.createRange();b.moveToBookmark(k);h.extractHtmlFromRange(b,1);c=e.createRange();c.moveToBookmark(g);a(e,{dataTransfer:d,method:"drop",range:c},1);e.fire("unlockSnapshot")},getRangeAtDropPosition:function(a,b){var c=a.data.$,d=c.clientX,e=c.clientY,g=b.getSelection(!0).getRanges()[0],h=
b.createRange();if(a.data.testRange)return a.data.testRange;if(document.caretRangeFromPoint)c=b.document.$.caretRangeFromPoint(d,e),h.setStart(CKEDITOR.dom.node(c.startContainer),c.startOffset),h.collapse(!0);else if(c.rangeParent)h.setStart(CKEDITOR.dom.node(c.rangeParent),c.rangeOffset),h.collapse(!0);else{if(CKEDITOR.env.ie&&8<CKEDITOR.env.version&&g&&b.editable().hasFocus)return g;if(document.body.createTextRange){b.focus();c=b.document.getBody().$.createTextRange();try{for(var k=!1,l=0;20>l&&
!k;l++){if(!k)try{c.moveToPoint(d,e-l),k=!0}catch(m){}if(!k)try{c.moveToPoint(d,e+l),k=!0}catch(n){}}if(k){var r="cke-temp-"+(new Date).getTime();c.pasteHTML('\x3cspan id\x3d"'+r+'"\x3e​\x3c/span\x3e');var C=b.document.getById(r);h.moveToPosition(C,CKEDITOR.POSITION_BEFORE_START);C.remove()}else{var D=b.document.$.elementFromPoint(d,e),z=new CKEDITOR.dom.element(D),K;if(z.equals(b.editable())||"html"==z.getName())return g&&g.startContainer&&!g.startContainer.equals(b.editable())?g:null;K=z.getClientRect();
d<K.left?h.setStartAt(z,CKEDITOR.POSITION_AFTER_START):h.setStartAt(z,CKEDITOR.POSITION_BEFORE_END);h.collapse(!0)}}catch(J){return null}}else return null}return h},initDragDataTransfer:function(a,b){var c=a.data.$?a.data.$.dataTransfer:null,d=new this.dataTransfer(c,b);c?this.dragData&&d.id==this.dragData.id?d=this.dragData:this.dragData=d:this.dragData?d=this.dragData:this.dragData=d;a.data.dataTransfer=d},resetDragDataTransfer:function(){this.dragData=null},initPasteDataTransfer:function(a,b){if(this.isCustomCopyCutSupported){if(a&&
a.data&&a.data.$){var c=new this.dataTransfer(a.data.$.clipboardData,b);this.copyCutData&&c.id==this.copyCutData.id?(c=this.copyCutData,c.$=a.data.$.clipboardData):this.copyCutData=c;return c}return new this.dataTransfer(null,b)}return new this.dataTransfer(CKEDITOR.env.edge&&a&&a.data.$&&a.data.$.clipboardData||null,b)},preventDefaultDropOnElement:function(a){a&&a.on("dragover",h)}};var c=CKEDITOR.plugins.clipboard.isCustomDataTypesSupported?"cke/id":"Text";CKEDITOR.plugins.clipboard.dataTransfer=
function(a,b){a&&(this.$=a);this._={metaRegExp:/^<meta.*?>/i,bodyRegExp:/<body(?:[\s\S]*?)>([\s\S]*)<\/body>/i,fragmentRegExp:/\x3c!--(?:Start|End)Fragment--\x3e/g,data:{},files:[],normalizeType:function(a){a=a.toLowerCase();return"text"==a||"text/plain"==a?"Text":"url"==a?"URL":a}};this.id=this.getData(c);this.id||(this.id="Text"==c?"":"cke-"+CKEDITOR.tools.getUniqueId());if("Text"!=c)try{this.$.setData(c,this.id)}catch(d){}b&&(this.sourceEditor=b,this.setData("text/html",b.getSelectedHtml(1)),"Text"==
c||this.getData("text/plain")||this.setData("text/plain",b.getSelection().getSelectedText()))};CKEDITOR.DATA_TRANSFER_INTERNAL=1;CKEDITOR.DATA_TRANSFER_CROSS_EDITORS=2;CKEDITOR.DATA_TRANSFER_EXTERNAL=3;CKEDITOR.plugins.clipboard.dataTransfer.prototype={getData:function(a){a=this._.normalizeType(a);var b=this._.data[a];if(void 0===b||null===b||""===b)try{b=this.$.getData(a)}catch(c){}if(void 0===b||null===b||""===b)b="";"text/html"==a?(b=b.replace(this._.metaRegExp,""),(a=this._.bodyRegExp.exec(b))&&
a.length&&(b=a[1],b=b.replace(this._.fragmentRegExp,""))):"Text"==a&&CKEDITOR.env.gecko&&this.getFilesCount()&&"file://"==b.substring(0,7)&&(b="");return b},setData:function(a,b){a=this._.normalizeType(a);this._.data[a]=b;if(CKEDITOR.plugins.clipboard.isCustomDataTypesSupported||"URL"==a||"Text"==a){"Text"==c&&"Text"==a&&(this.id=b);try{this.$.setData(a,b)}catch(d){}}},getTransferType:function(a){return this.sourceEditor?this.sourceEditor==a?CKEDITOR.DATA_TRANSFER_INTERNAL:CKEDITOR.DATA_TRANSFER_CROSS_EDITORS:
CKEDITOR.DATA_TRANSFER_EXTERNAL},cacheData:function(){function a(c){c=b._.normalizeType(c);var d=b.getData(c);d&&(b._.data[c]=d)}if(this.$){var b=this,c,d;if(CKEDITOR.plugins.clipboard.isCustomDataTypesSupported){if(this.$.types)for(c=0;c<this.$.types.length;c++)a(this.$.types[c])}else a("Text"),a("URL");d=this._getImageFromClipboard();if(this.$&&this.$.files||d){this._.files=[];if(this.$.files&&this.$.files.length)for(c=0;c<this.$.files.length;c++)this._.files.push(this.$.files[c]);0===this._.files.length&&
d&&this._.files.push(d)}}},getFilesCount:function(){return this._.files.length?this._.files.length:this.$&&this.$.files&&this.$.files.length?this.$.files.length:this._getImageFromClipboard()?1:0},getFile:function(a){return this._.files.length?this._.files[a]:this.$&&this.$.files&&this.$.files.length?this.$.files[a]:0===a?this._getImageFromClipboard():void 0},isEmpty:function(){var a={},b;if(this.getFilesCount())return!1;for(b in this._.data)a[b]=1;if(this.$)if(CKEDITOR.plugins.clipboard.isCustomDataTypesSupported){if(this.$.types)for(var d=
0;d<this.$.types.length;d++)a[this.$.types[d]]=1}else a.Text=1,a.URL=1;"Text"!=c&&(a[c]=0);for(b in a)if(a[b]&&""!==this.getData(b))return!1;return!0},_getImageFromClipboard:function(){var a;if(this.$&&this.$.items&&this.$.items[0])try{if((a=this.$.items[0].getAsFile())&&a.type)return a}catch(b){}}}}(),function(){function a(a){return a?20<a.length?!1:(a=a.replace(/[\n|\t]*/g,"").toLowerCase())&&"\x3cbr\x3e"!=a&&"\x3cp\x3e\x26nbsp;\x3cbr\x3e\x3c/p\x3e"!=a&&"\x3cp\x3e\x3cbr\x3e\x3c/p\x3e"!=a&&"\x3cp\x3e\x26nbsp;\x3c/p\x3e"!=
a&&"\x26nbsp;"!=a&&" "!=a&&"\x26nbsp;\x3cbr\x3e"!=a&&" \x3cbr\x3e"!=a?!1:!0:!0}function e(d){var e=d.editor,g=e.editable?e.editable():"wysiwyg"==e.mode?e.document&&e.document.getBody():e.textarea,b=d.listenerData;if(g){if("wysiwyg"==e.mode){if(CKEDITOR.dialog._.currentTop||!g)return;a(g.getHtml())&&(g.setHtml(b),g.addClass("placeholder"))}"source"==e.mode&&(l?"mode"==d.name&&g.setAttribute("placeholder",b):a(g.getValue())&&(g.setValue(b),g.addClass("placeholder")))}}function d(a){a=a.editor;var d=
a.editable?a.editable():"wysiwyg"==a.mode?a.document&&a.document.getBody():a.textarea;if(d){if("wysiwyg"==a.mode){if(!d.hasClass("placeholder"))return;d.removeClass("placeholder");if(CKEDITOR.dtd[d.getName()].p){d.setHtml("\x3cp\x3e\x3cbr/\x3e\x3c/p\x3e");var e=new CKEDITOR.dom.range(a.document);e.moveToElementEditablePosition(d.getFirst(),!0);a.getSelection().selectRanges([e])}else d.setHtml(" ")}"source"==a.mode&&d.hasClass("placeholder")&&(d.removeClass("placeholder"),d.setValue(""))}}function g(a){return a?
a.getAttribute("lang")||g(a.getParent()):null}var l="placeholder"in document.createElement("textarea");CKEDITOR.plugins.add("confighelper",{getPlaceholderCss:function(){return".placeholder{ color: #999; }"},onLoad:function(){CKEDITOR.addCss&&CKEDITOR.addCss(this.getPlaceholderCss())},init:function(k){k.on("mode",function(a){a.editor.focusManager.hasFocus=!1});var m=k.element.getAttribute("placeholder")||k.config.placeholder;if(m){k.addCss&&k.addCss(this.getPlaceholderCss());var h=CKEDITOR.document.getHead().append("style");
h.setAttribute("type","text/css");CKEDITOR.env.ie&&11>CKEDITOR.env.version?h.$.styleSheet.cssText="textarea.placeholder { color: #999; font-style: italic; }":h.$.innerHTML="textarea.placeholder { color: #999; font-style: italic; }";k.on("getData",function(a){var b=k.editable?k.editable():"wysiwyg"==k.mode?k.document&&k.document.getBody():k.textarea;b&&b.hasClass("placeholder")&&(a.data.dataValue="")});k.on("setData",function(b){if(!(CKEDITOR.dialog._.currentTop||"source"==k.mode&&l)){var d=k.editable?
k.editable():"wysiwyg"==k.mode?k.document&&k.document.getBody():k.textarea;d&&(a(b.data.dataValue)?e(b):d.hasClass("placeholder")&&d.removeClass("placeholder"))}});k.on("blur",e,null,m);k.on("mode",e,null,m);k.on("contentDom",e,null,m);k.on("focus",d);k.on("beforeModeUnload",d)}(m=k.config.contentsLanguage||g(k.element))&&!k.config.scayt_sLang&&(localStorage&&localStorage.removeItem("scayt_0_lang"),k.config.scayt_sLang={en:"en_US","en-us":"en_US","en-gb":"en_GB","pt-br":"pt_BR",da:"da_DK","da-dk":"da_DK",
"nl-nl":"nl_NL","en-ca":"en_CA","fi-fi":"fi_FI",fr:"fr_FR","fr-fr":"fr_FR","fr-ca":"fr_CA",de:"de_DE","de-de":"de_DE","el-gr":"el_GR",it:"it_IT","it-it":"it_IT","nb-no":"nb_NO",pt:"pt_PT","pt-pt":"pt_PT",es:"es_ES","es-es":"es_ES","sv-se":"sv_SE"}[m.toLowerCase()]);var b=function(a){if("object"==typeof a)return a;a=a.split(";");var b={},d;for(d=0;d<a.length;d++){var e=a[d].split(":");if(3==e.length){var g=e[0],h=e[1],e=e[2];b[g]||(b[g]={});b[g][h]||(b[g][h]=[]);b[g][h].push(e)}}return b};CKEDITOR.on("dialogDefinition",
function(a){if(k==a.editor){var d=a.data.name;a=a.data.definition;var e,g,h,l,m;"tableProperties"==d&&"table"==d;"removeDialogFields"in k._||!k.config.removeDialogFields||(k._.removeDialogFields=b(k.config.removeDialogFields));if(k._.removeDialogFields&&(e=k._.removeDialogFields[d]))for(h in e)for(l=e[h],m=a.getContents(h),g=0;g<l.length;g++)m.remove(l[g]);"hideDialogFields"in k._||!k.config.hideDialogFields||(k._.hideDialogFields=b(k.config.hideDialogFields));if(k._.hideDialogFields&&(e=k._.hideDialogFields[d]))for(h in e)for(l=
e[h],m=a.getContents(h),g=0;g<l.length;g++)m.get(l[g]).hidden=!0;if(k.config.dialogFieldsDefaultValues&&(e=k.config.dialogFieldsDefaultValues[d]))for(h in e){l=e[h];m=a.getContents(h);for(var y in l)(d=m.get(y))&&(d["default"]=l[y])}}})}})}(),function(){function a(a,d){var g={},l=[],k={nbsp:" ",shy:"­",gt:"\x3e",lt:"\x3c",amp:"\x26",apos:"'",quot:'"'};a=a.replace(/\b(nbsp|shy|gt|lt|amp|apos|quot)(?:,|$)/g,function(a,b){var e=d?"\x26"+b+";":k[b];g[e]=d?k[b]:"\x26"+b+";";l.push(e);return""});if(!d&&
a){a=a.split(",");var m=document.createElement("div"),h;m.innerHTML="\x26"+a.join(";\x26")+";";h=m.innerHTML;m=null;for(m=0;m<h.length;m++){var b=h.charAt(m);g[b]="\x26"+a[m]+";";l.push(b)}}g.regex=l.join(d?"|":"");return g}CKEDITOR.plugins.add("entities",{afterInit:function(e){function d(a){return b[a]}function g(a){return"force"!=l.entities_processNumerical&&m[a]?m[a]:"\x26#"+a.charCodeAt(0)+";"}var l=e.config;if(e=(e=e.dataProcessor)&&e.htmlFilter){var k=[];!1!==l.basicEntities&&k.push("nbsp,gt,lt,amp");
l.entities&&(k.length&&k.push("quot,iexcl,cent,pound,curren,yen,brvbar,sect,uml,copy,ordf,laquo,not,shy,reg,macr,deg,plusmn,sup2,sup3,acute,micro,para,middot,cedil,sup1,ordm,raquo,frac14,frac12,frac34,iquest,times,divide,fnof,bull,hellip,prime,Prime,oline,frasl,weierp,image,real,trade,alefsym,larr,uarr,rarr,darr,harr,crarr,lArr,uArr,rArr,dArr,hArr,forall,part,exist,empty,nabla,isin,notin,ni,prod,sum,minus,lowast,radic,prop,infin,ang,and,or,cap,cup,int,there4,sim,cong,asymp,ne,equiv,le,ge,sub,sup,nsub,sube,supe,oplus,otimes,perp,sdot,lceil,rceil,lfloor,rfloor,lang,rang,loz,spades,clubs,hearts,diams,circ,tilde,ensp,emsp,thinsp,zwnj,zwj,lrm,rlm,ndash,mdash,lsquo,rsquo,sbquo,ldquo,rdquo,bdquo,dagger,Dagger,permil,lsaquo,rsaquo,euro"),
l.entities_latin&&k.push("Agrave,Aacute,Acirc,Atilde,Auml,Aring,AElig,Ccedil,Egrave,Eacute,Ecirc,Euml,Igrave,Iacute,Icirc,Iuml,ETH,Ntilde,Ograve,Oacute,Ocirc,Otilde,Ouml,Oslash,Ugrave,Uacute,Ucirc,Uuml,Yacute,THORN,szlig,agrave,aacute,acirc,atilde,auml,aring,aelig,ccedil,egrave,eacute,ecirc,euml,igrave,iacute,icirc,iuml,eth,ntilde,ograve,oacute,ocirc,otilde,ouml,oslash,ugrave,uacute,ucirc,uuml,yacute,thorn,yuml,OElig,oelig,Scaron,scaron,Yuml"),l.entities_greek&&k.push("Alpha,Beta,Gamma,Delta,Epsilon,Zeta,Eta,Theta,Iota,Kappa,Lambda,Mu,Nu,Xi,Omicron,Pi,Rho,Sigma,Tau,Upsilon,Phi,Chi,Psi,Omega,alpha,beta,gamma,delta,epsilon,zeta,eta,theta,iota,kappa,lambda,mu,nu,xi,omicron,pi,rho,sigmaf,sigma,tau,upsilon,phi,chi,psi,omega,thetasym,upsih,piv"),
l.entities_additional&&k.push(l.entities_additional));var m=a(k.join(",")),h=m.regex?"["+m.regex+"]":"a^";delete m.regex;l.entities&&l.entities_processNumerical&&(h="[^ -~]|"+h);var h=new RegExp(h,"g"),b=a("nbsp,gt,lt,amp,shy",!0),c=new RegExp(b.regex,"g");e.addRules({text:function(a){return a.replace(c,d).replace(h,g)}},{applyToAll:!0,excludeNestedEditable:!0})}}})}(),CKEDITOR.config.basicEntities=!0,CKEDITOR.config.entities=!0,CKEDITOR.config.entities_latin=!0,CKEDITOR.config.entities_greek=!0,
CKEDITOR.config.entities_additional="#39",function(){function a(a){var l=a.config,k=a.fire("uiSpace",{space:"top",html:""}).html,m=function(){function c(a,e,f){b.setStyle(e,d(f));b.setStyle("position",a)}function f(a){var b=k.getDocumentPosition();switch(a){case "top":c("absolute","top",b.y-w-r);break;case "pin":c("fixed","top",D);break;case "bottom":c("absolute","top",b.y+(y.height||y.bottom-y.top)+r)}h=a}var h,k,u,y,H,w,F,n=l.floatSpaceDockedOffsetX||0,r=l.floatSpaceDockedOffsetY||0,C=l.floatSpacePinnedOffsetX||
0,D=l.floatSpacePinnedOffsetY||0;return function(c){if(k=a.editable()){var p=c&&"focus"==c.name;p&&b.show();a.fire("floatingSpaceLayout",{show:p});b.removeStyle("left");b.removeStyle("right");u=b.getClientRect();y=k.getClientRect();H=e.getViewPaneSize();w=u.height;F="pageXOffset"in e.$?e.$.pageXOffset:CKEDITOR.document.$.documentElement.scrollLeft;h?(w+r<=y.top?f("top"):w+r>H.height-y.bottom?f("pin"):f("bottom"),c=H.width/2,c=l.floatSpacePreferRight?"right":0<y.left&&y.right<H.width&&y.width>u.width?
"rtl"==l.contentsLangDirection?"right":"left":c-y.left>y.right-c?"left":"right",u.width>H.width?(c="left",p=0):(p="left"==c?0<y.left?y.left:0:y.right<H.width?H.width-y.right:0,p+u.width>H.width&&(c="left"==c?"right":"left",p=0)),b.setStyle(c,d(("pin"==h?C:n)+p+("pin"==h?0:"left"==c?F:-F)))):(h="pin",f("pin"),m(c))}}}();if(k){var h=new CKEDITOR.template('\x3cdiv id\x3d"cke_{name}" class\x3d"cke {id} cke_reset_all cke_chrome cke_editor_{name} cke_float cke_{langDir} '+CKEDITOR.env.cssClass+'" dir\x3d"{langDir}" title\x3d"'+
(CKEDITOR.env.gecko?" ":"")+'" lang\x3d"{langCode}" role\x3d"application" style\x3d"{style}"'+(a.title?' aria-labelledby\x3d"cke_{name}_arialbl"':" ")+"\x3e"+(a.title?'\x3cspan id\x3d"cke_{name}_arialbl" class\x3d"cke_voice_label"\x3e{voiceLabel}\x3c/span\x3e':" ")+'\x3cdiv class\x3d"cke_inner"\x3e\x3cdiv id\x3d"{topId}" class\x3d"cke_top" role\x3d"presentation"\x3e{content}\x3c/div\x3e\x3c/div\x3e\x3c/div\x3e'),b=CKEDITOR.document.getBody().append(CKEDITOR.dom.element.createFromHtml(h.output({content:k,
id:a.id,langDir:a.lang.dir,langCode:a.langCode,name:a.name,style:"display:none;z-index:"+(l.baseFloatZIndex-1),topId:a.ui.spaceId("top"),voiceLabel:a.title}))),c=CKEDITOR.tools.eventsBuffer(500,m),f=CKEDITOR.tools.eventsBuffer(100,m);b.unselectable();b.on("mousedown",function(a){a=a.data;a.getTarget().hasAscendant("a",1)||a.preventDefault()});a.on("focus",function(b){m(b);a.on("change",c.input);e.on("scroll",f.input);e.on("resize",f.input)});a.on("blur",function(){b.hide();a.removeListener("change",
c.input);e.removeListener("scroll",f.input);e.removeListener("resize",f.input)});a.on("destroy",function(){e.removeListener("scroll",f.input);e.removeListener("resize",f.input);b.clearCustomData();b.remove()});a.focusManager.hasFocus&&b.show();a.focusManager.add(b,1)}}var e=CKEDITOR.document.getWindow(),d=CKEDITOR.tools.cssLength;CKEDITOR.plugins.add("floatingspace",{init:function(d){d.on("loaded",function(){a(this)},null,null,20)}})}(),"use strict",function(){var a=[CKEDITOR.CTRL+90,CKEDITOR.CTRL+
89,CKEDITOR.CTRL+CKEDITOR.SHIFT+90],e={8:1,46:1};CKEDITOR.plugins.add("undo",{init:function(e){function b(a){f.enabled&&!1!==a.data.command.canUndo&&f.save()}function c(){f.enabled=e.readOnly?!1:"wysiwyg"==e.mode;f.onChange()}var f=e.undoManager=new d(e),g=f.editingHandler=new k(f),l=e.addCommand("undo",{exec:function(){f.undo()&&(e.selectionChange(),this.fire("afterUndo"))},startDisabled:!0,canUndo:!1}),m=e.addCommand("redo",{exec:function(){f.redo()&&(e.selectionChange(),this.fire("afterRedo"))},
startDisabled:!0,canUndo:!1});e.setKeystroke([[a[0],"undo"],[a[1],"redo"],[a[2],"redo"]]);f.onChange=function(){l.setState(f.undoable()?CKEDITOR.TRISTATE_OFF:CKEDITOR.TRISTATE_DISABLED);m.setState(f.redoable()?CKEDITOR.TRISTATE_OFF:CKEDITOR.TRISTATE_DISABLED)};e.on("beforeCommandExec",b);e.on("afterCommandExec",b);e.on("saveSnapshot",function(a){f.save(a.data&&a.data.contentOnly)});e.on("contentDom",g.attachListeners,g);e.on("instanceReady",function(){e.fire("saveSnapshot")});e.on("beforeModeUnload",
function(){"wysiwyg"==e.mode&&f.save(!0)});e.on("mode",c);e.on("readOnly",c);e.ui.addButton&&(e.ui.addButton("Undo",{label:e.lang.undo.undo,command:"undo",toolbar:"undo,10"}),e.ui.addButton("Redo",{label:e.lang.undo.redo,command:"redo",toolbar:"undo,20"}));e.resetUndo=function(){f.reset();e.fire("saveSnapshot")};e.on("updateSnapshot",function(){f.currentImage&&f.update()});e.on("lockSnapshot",function(a){a=a.data;f.lock(a&&a.dontUpdate,a&&a.forceUpdate)});e.on("unlockSnapshot",f.unlock,f)}});CKEDITOR.plugins.undo=
{};var d=CKEDITOR.plugins.undo.UndoManager=function(a){this.strokesRecorded=[0,0];this.locked=null;this.previousKeyGroup=-1;this.limit=a.config.undoStackSize||20;this.strokesLimit=25;this.editor=a;this.reset()};d.prototype={type:function(a,b){var c=d.getKeyGroup(a),e=this.strokesRecorded[c]+1;b=b||e>=this.strokesLimit;this.typing||(this.hasUndo=this.typing=!0,this.hasRedo=!1,this.onChange());b?(e=0,this.editor.fire("saveSnapshot")):this.editor.fire("change");this.strokesRecorded[c]=e;this.previousKeyGroup=
c},keyGroupChanged:function(a){return d.getKeyGroup(a)!=this.previousKeyGroup},reset:function(){this.snapshots=[];this.index=-1;this.currentImage=null;this.hasRedo=this.hasUndo=!1;this.locked=null;this.resetType()},resetType:function(){this.strokesRecorded=[0,0];this.typing=!1;this.previousKeyGroup=-1},refreshState:function(){this.hasUndo=!!this.getNextImage(!0);this.hasRedo=!!this.getNextImage(!1);this.resetType();this.onChange()},save:function(a,b,c){var d=this.editor;if(this.locked||"ready"!=d.status||
"wysiwyg"!=d.mode)return!1;var e=d.editable();if(!e||"ready"!=e.status)return!1;e=this.snapshots;b||(b=new g(d));if(!1===b.contents)return!1;if(this.currentImage)if(b.equalsContent(this.currentImage)){if(a||b.equalsSelection(this.currentImage))return!1}else!1!==c&&d.fire("change");e.splice(this.index+1,e.length-this.index-1);e.length==this.limit&&e.shift();this.index=e.push(b)-1;this.currentImage=b;!1!==c&&this.refreshState();return!0},restoreImage:function(a){var b=this.editor,c;a.bookmarks&&(b.focus(),
c=b.getSelection());this.locked={level:999};this.editor.loadSnapshot(a.contents);a.bookmarks?c.selectBookmarks(a.bookmarks):CKEDITOR.env.ie&&(c=this.editor.document.getBody().$.createTextRange(),c.collapse(!0),c.select());this.locked=null;this.index=a.index;this.currentImage=this.snapshots[this.index];this.update();this.refreshState();b.fire("change")},getNextImage:function(a){var b=this.snapshots,c=this.currentImage,d;if(c)if(a)for(d=this.index-1;0<=d;d--){if(a=b[d],!c.equalsContent(a))return a.index=
d,a}else for(d=this.index+1;d<b.length;d++)if(a=b[d],!c.equalsContent(a))return a.index=d,a;return null},redoable:function(){return this.enabled&&this.hasRedo},undoable:function(){return this.enabled&&this.hasUndo},undo:function(){if(this.undoable()){this.save(!0);var a=this.getNextImage(!0);if(a)return this.restoreImage(a),!0}return!1},redo:function(){if(this.redoable()&&(this.save(!0),this.redoable())){var a=this.getNextImage(!1);if(a)return this.restoreImage(a),!0}return!1},update:function(a){if(!this.locked){a||
(a=new g(this.editor));for(var b=this.index,c=this.snapshots;0<b&&this.currentImage.equalsContent(c[b-1]);)--b;c.splice(b,this.index-b+1,a);this.index=b;this.currentImage=a}},updateSelection:function(a){if(!this.snapshots.length)return!1;var b=this.snapshots,c=b[b.length-1];return c.equalsContent(a)&&!c.equalsSelection(a)?(this.currentImage=b[b.length-1]=a,!0):!1},lock:function(a,b){if(this.locked)this.locked.level++;else if(a)this.locked={level:1};else{var c=null;if(b)c=!0;else{var d=new g(this.editor,
!0);this.currentImage&&this.currentImage.equalsContent(d)&&(c=d)}this.locked={update:c,level:1}}},unlock:function(){if(this.locked&&!--this.locked.level){var a=this.locked.update;this.locked=null;if(!0===a)this.update();else if(a){var b=new g(this.editor,!0);a.equalsContent(b)||this.update()}}}};d.navigationKeyCodes={37:1,38:1,39:1,40:1,36:1,35:1,33:1,34:1};d.keyGroups={PRINTABLE:0,FUNCTIONAL:1};d.isNavigationKey=function(a){return!!d.navigationKeyCodes[a]};d.getKeyGroup=function(a){var b=d.keyGroups;
return e[a]?b.FUNCTIONAL:b.PRINTABLE};d.getOppositeKeyGroup=function(a){var b=d.keyGroups;return a==b.FUNCTIONAL?b.PRINTABLE:b.FUNCTIONAL};d.ieFunctionalKeysBug=function(a){return CKEDITOR.env.ie&&d.getKeyGroup(a)==d.keyGroups.FUNCTIONAL};var g=CKEDITOR.plugins.undo.Image=function(a,b){this.editor=a;a.fire("beforeUndoImage");var c=a.getSnapshot();CKEDITOR.env.ie&&c&&(c=c.replace(/\s+data-cke-expando=".*?"/g,""));this.contents=c;b||(this.bookmarks=(c=c&&a.getSelection())&&c.createBookmarks2(!0));a.fire("afterUndoImage")},
l=/\b(?:href|src|name)="[^"]*?"/gi;g.prototype={equalsContent:function(a){var b=this.contents;a=a.contents;CKEDITOR.env.ie&&(CKEDITOR.env.ie7Compat||CKEDITOR.env.quirks)&&(b=b.replace(l,""),a=a.replace(l,""));return b!=a?!1:!0},equalsSelection:function(a){var b=this.bookmarks;a=a.bookmarks;if(b||a){if(!b||!a||b.length!=a.length)return!1;for(var c=0;c<b.length;c++){var d=b[c],e=a[c];if(d.startOffset!=e.startOffset||d.endOffset!=e.endOffset||!CKEDITOR.tools.arrayCompare(d.start,e.start)||!CKEDITOR.tools.arrayCompare(d.end,
e.end))return!1}}return!0}};var k=CKEDITOR.plugins.undo.NativeEditingHandler=function(a){this.undoManager=a;this.ignoreInputEvent=!1;this.keyEventsStack=new m;this.lastKeydownImage=null};k.prototype={onKeydown:function(e){var b=e.data.getKey();if(229!==b)if(-1<CKEDITOR.tools.indexOf(a,e.data.getKeystroke()))e.data.preventDefault();else if(this.keyEventsStack.cleanUp(e),e=this.undoManager,this.keyEventsStack.getLast(b)||this.keyEventsStack.push(b),this.lastKeydownImage=new g(e.editor),d.isNavigationKey(b)||
this.undoManager.keyGroupChanged(b))if(e.strokesRecorded[0]||e.strokesRecorded[1])e.save(!1,this.lastKeydownImage,!1),e.resetType()},onInput:function(){if(this.ignoreInputEvent)this.ignoreInputEvent=!1;else{var a=this.keyEventsStack.getLast();a||(a=this.keyEventsStack.push(0));this.keyEventsStack.increment(a.keyCode);this.keyEventsStack.getTotalInputs()>=this.undoManager.strokesLimit&&(this.undoManager.type(a.keyCode,!0),this.keyEventsStack.resetInputs())}},onKeyup:function(a){var b=this.undoManager;
a=a.data.getKey();var c=this.keyEventsStack.getTotalInputs();this.keyEventsStack.remove(a);if(!(d.ieFunctionalKeysBug(a)&&this.lastKeydownImage&&this.lastKeydownImage.equalsContent(new g(b.editor,!0))))if(0<c)b.type(a);else if(d.isNavigationKey(a))this.onNavigationKey(!0)},onNavigationKey:function(a){var b=this.undoManager;!a&&b.save(!0,null,!1)||b.updateSelection(new g(b.editor));b.resetType()},ignoreInputEventListener:function(){this.ignoreInputEvent=!0},attachListeners:function(){var a=this.undoManager.editor,
b=a.editable(),c=this;b.attachListener(b,"keydown",function(a){c.onKeydown(a);if(d.ieFunctionalKeysBug(a.data.getKey()))c.onInput()},null,null,999);b.attachListener(b,CKEDITOR.env.ie?"keypress":"input",c.onInput,c,null,999);b.attachListener(b,"keyup",c.onKeyup,c,null,999);b.attachListener(b,"paste",c.ignoreInputEventListener,c,null,999);b.attachListener(b,"drop",c.ignoreInputEventListener,c,null,999);a.on("afterPaste",function(){c.ignoreInputEvent=!1});b.attachListener(b.isInline()?b:a.document.getDocumentElement(),
"click",function(){c.onNavigationKey()},null,null,999);b.attachListener(this.undoManager.editor,"blur",function(){c.keyEventsStack.remove(9)},null,null,999)}};var m=CKEDITOR.plugins.undo.KeyEventsStack=function(){this.stack=[]};m.prototype={push:function(a){a=this.stack.push({keyCode:a,inputs:0});return this.stack[a-1]},getLastIndex:function(a){if("number"!=typeof a)return this.stack.length-1;for(var b=this.stack.length;b--;)if(this.stack[b].keyCode==a)return b;return-1},getLast:function(a){a=this.getLastIndex(a);
return-1!=a?this.stack[a]:null},increment:function(a){this.getLast(a).inputs++},remove:function(a){a=this.getLastIndex(a);-1!=a&&this.stack.splice(a,1)},resetInputs:function(a){if("number"==typeof a)this.getLast(a).inputs=0;else for(a=this.stack.length;a--;)this.stack[a].inputs=0},getTotalInputs:function(){for(var a=this.stack.length,b=0;a--;)b+=this.stack[a].inputs;return b},cleanUp:function(a){a=a.data.$;a.ctrlKey||a.metaKey||this.remove(17);a.shiftKey||this.remove(16);a.altKey||this.remove(18)}}}(),
"use strict",function(){function a(a,c){CKEDITOR.tools.extend(this,{editor:a,editable:a.editable(),doc:a.document,win:a.window},c,!0);this.inline=this.editable.isInline();this.inline||(this.frame=this.win.getFrame());this.target=this[this.inline?"editable":"doc"]}function e(a,c){CKEDITOR.tools.extend(this,c,{editor:a},!0)}function d(a,c){var d=a.editable();CKEDITOR.tools.extend(this,{editor:a,editable:d,inline:d.isInline(),doc:a.document,win:a.window,container:CKEDITOR.document.getBody(),winTop:CKEDITOR.document.getWindow()},
c,!0);this.hidden={};this.visible={};this.inline||(this.frame=this.win.getFrame());this.queryViewport();var e=CKEDITOR.tools.bind(this.queryViewport,this),g=CKEDITOR.tools.bind(this.hideVisible,this),h=CKEDITOR.tools.bind(this.removeAll,this);d.attachListener(this.winTop,"resize",e);d.attachListener(this.winTop,"scroll",e);d.attachListener(this.winTop,"resize",g);d.attachListener(this.win,"scroll",g);d.attachListener(this.inline?d:this.frame,"mouseout",function(a){var b=a.data.$.clientX;a=a.data.$.clientY;
this.queryViewport();(b<=this.rect.left||b>=this.rect.right||a<=this.rect.top||a>=this.rect.bottom)&&this.hideVisible();(0>=b||b>=this.winTopPane.width||0>=a||a>=this.winTopPane.height)&&this.hideVisible()},this);d.attachListener(a,"resize",e);d.attachListener(a,"mode",h);a.on("destroy",h);this.lineTpl=(new CKEDITOR.template('\x3cdiv data-cke-lineutils-line\x3d"1" class\x3d"cke_reset_all" style\x3d"{lineStyle}"\x3e\x3cspan style\x3d"{tipLeftStyle}"\x3e\x26nbsp;\x3c/span\x3e\x3cspan style\x3d"{tipRightStyle}"\x3e\x26nbsp;\x3c/span\x3e\x3c/div\x3e')).output({lineStyle:CKEDITOR.tools.writeCssText(CKEDITOR.tools.extend({},
k,this.lineStyle,!0)),tipLeftStyle:CKEDITOR.tools.writeCssText(CKEDITOR.tools.extend({},l,{left:"0px","border-left-color":"red","border-width":"6px 0 6px 6px"},this.tipCss,this.tipLeftStyle,!0)),tipRightStyle:CKEDITOR.tools.writeCssText(CKEDITOR.tools.extend({},l,{right:"0px","border-right-color":"red","border-width":"6px 6px 6px 0"},this.tipCss,this.tipRightStyle,!0))})}function g(a){var c;if(c=a&&a.type==CKEDITOR.NODE_ELEMENT)c=!(m[a.getComputedStyle("float")]||m[a.getAttribute("align")]);return c&&
!h[a.getComputedStyle("position")]}CKEDITOR.plugins.add("lineutils");CKEDITOR.LINEUTILS_BEFORE=1;CKEDITOR.LINEUTILS_AFTER=2;CKEDITOR.LINEUTILS_INSIDE=4;a.prototype={start:function(a){var c=this,d=this.editor,e=this.doc,g,h,k,l,m=CKEDITOR.tools.eventsBuffer(50,function(){d.readOnly||"wysiwyg"!=d.mode||(c.relations={},(h=e.$.elementFromPoint(k,l))&&h.nodeType&&(g=new CKEDITOR.dom.element(h),c.traverseSearch(g),isNaN(k+l)||c.pixelSearch(g,k,l),a&&a(c.relations,k,l)))});this.listener=this.editable.attachListener(this.target,
"mousemove",function(a){k=a.data.$.clientX;l=a.data.$.clientY;m.input()});this.editable.attachListener(this.inline?this.editable:this.frame,"mouseout",function(){m.reset()})},stop:function(){this.listener&&this.listener.removeListener()},getRange:function(){var a={};a[CKEDITOR.LINEUTILS_BEFORE]=CKEDITOR.POSITION_BEFORE_START;a[CKEDITOR.LINEUTILS_AFTER]=CKEDITOR.POSITION_AFTER_END;a[CKEDITOR.LINEUTILS_INSIDE]=CKEDITOR.POSITION_AFTER_START;return function(c){var d=this.editor.createRange();d.moveToPosition(this.relations[c.uid].element,
a[c.type]);return d}}(),store:function(){function a(b,d,e){var g=b.getUniqueId();g in e?e[g].type|=d:e[g]={element:b,type:d}}return function(c,d){var e;d&CKEDITOR.LINEUTILS_AFTER&&g(e=c.getNext())&&e.isVisible()&&(a(e,CKEDITOR.LINEUTILS_BEFORE,this.relations),d^=CKEDITOR.LINEUTILS_AFTER);d&CKEDITOR.LINEUTILS_INSIDE&&g(e=c.getFirst())&&e.isVisible()&&(a(e,CKEDITOR.LINEUTILS_BEFORE,this.relations),d^=CKEDITOR.LINEUTILS_INSIDE);a(c,d,this.relations)}}(),traverseSearch:function(a){var c,d,e;do if(e=a.$["data-cke-expando"],
!(e&&e in this.relations)){if(a.equals(this.editable))break;if(g(a))for(c in this.lookups)(d=this.lookups[c](a))&&this.store(a,d)}while((!a||a.type!=CKEDITOR.NODE_ELEMENT||"true"!=a.getAttribute("contenteditable"))&&(a=a.getParent()))},pixelSearch:function(){function a(b,d,e,h,k){for(var l=0,m;k(e);){e+=h;if(25==++l)break;if(m=this.doc.$.elementFromPoint(d,e))if(m==b)l=0;else if(c(b,m)&&(l=0,g(m=new CKEDITOR.dom.element(m))))return m}}var c=CKEDITOR.env.ie||CKEDITOR.env.webkit?function(a,b){return a.contains(b)}:
function(a,b){return!!(a.compareDocumentPosition(b)&16)};return function(c,d,e){var h=this.win.getViewPaneSize().height,k=a.call(this,c.$,d,e,-1,function(a){return 0<a});d=a.call(this,c.$,d,e,1,function(a){return a<h});if(k)for(this.traverseSearch(k);!k.getParent().equals(c);)k=k.getParent();if(d)for(this.traverseSearch(d);!d.getParent().equals(c);)d=d.getParent();for(;k||d;){k&&(k=k.getNext(g));if(!k||k.equals(d))break;this.traverseSearch(k);d&&(d=d.getPrevious(g));if(!d||d.equals(k))break;this.traverseSearch(d)}}}(),
greedySearch:function(){this.relations={};for(var a=this.editable.getElementsByTag("*"),c=0,d,e,h;d=a.getItem(c++);)if(!d.equals(this.editable)&&d.type==CKEDITOR.NODE_ELEMENT&&(d.hasAttribute("contenteditable")||!d.isReadOnly())&&g(d)&&d.isVisible())for(h in this.lookups)(e=this.lookups[h](d))&&this.store(d,e);return this.relations}};e.prototype={locate:function(){function a(b,d){var e=b.element[d===CKEDITOR.LINEUTILS_BEFORE?"getPrevious":"getNext"]();return e&&g(e)?(b.siblingRect=e.getClientRect(),
d==CKEDITOR.LINEUTILS_BEFORE?(b.siblingRect.bottom+b.elementRect.top)/2:(b.elementRect.bottom+b.siblingRect.top)/2):d==CKEDITOR.LINEUTILS_BEFORE?b.elementRect.top:b.elementRect.bottom}return function(c){var d;this.locations={};for(var e in c)d=c[e],d.elementRect=d.element.getClientRect(),d.type&CKEDITOR.LINEUTILS_BEFORE&&this.store(e,CKEDITOR.LINEUTILS_BEFORE,a(d,CKEDITOR.LINEUTILS_BEFORE)),d.type&CKEDITOR.LINEUTILS_AFTER&&this.store(e,CKEDITOR.LINEUTILS_AFTER,a(d,CKEDITOR.LINEUTILS_AFTER)),d.type&
CKEDITOR.LINEUTILS_INSIDE&&this.store(e,CKEDITOR.LINEUTILS_INSIDE,(d.elementRect.top+d.elementRect.bottom)/2);return this.locations}}(),sort:function(){var a,c,d,e;return function(g,h){a=this.locations;c=[];for(var k in a)for(var l in a[k])if(d=Math.abs(g-a[k][l]),c.length){for(e=0;e<c.length;e++)if(d<c[e].dist){c.splice(e,0,{uid:+k,type:l,dist:d});break}e==c.length&&c.push({uid:+k,type:l,dist:d})}else c.push({uid:+k,type:l,dist:d});return"undefined"!=typeof h?c.slice(0,h):c}}(),store:function(a,
c,d){this.locations[a]||(this.locations[a]={});this.locations[a][c]=d}};var l={display:"block",width:"0px",height:"0px","border-color":"transparent","border-style":"solid",position:"absolute",top:"-6px"},k={height:"0px","border-top":"1px dashed red",position:"absolute","z-index":9999};d.prototype={removeAll:function(){for(var a in this.hidden)this.hidden[a].remove(),delete this.hidden[a];for(a in this.visible)this.visible[a].remove(),delete this.visible[a]},hideLine:function(a){var c=a.getUniqueId();
a.hide();this.hidden[c]=a;delete this.visible[c]},showLine:function(a){var c=a.getUniqueId();a.show();this.visible[c]=a;delete this.hidden[c]},hideVisible:function(){for(var a in this.visible)this.hideLine(this.visible[a])},placeLine:function(a,c){var d,e,g;if(d=this.getStyle(a.uid,a.type)){for(g in this.visible)if(this.visible[g].getCustomData("hash")!==this.hash){e=this.visible[g];break}if(!e)for(g in this.hidden)if(this.hidden[g].getCustomData("hash")!==this.hash){this.showLine(e=this.hidden[g]);
break}e||this.showLine(e=this.addLine());e.setCustomData("hash",this.hash);this.visible[e.getUniqueId()]=e;e.setStyles(d);c&&c(e)}},getStyle:function(a,c){var d=this.relations[a],e=this.locations[a][c],g={};g.width=d.siblingRect?Math.max(d.siblingRect.width,d.elementRect.width):d.elementRect.width;g.top=this.inline?e+this.winTopScroll.y-this.rect.relativeY:this.rect.top+this.winTopScroll.y+e;if(g.top-this.winTopScroll.y<this.rect.top||g.top-this.winTopScroll.y>this.rect.bottom)return!1;this.inline?
g.left=d.elementRect.left-this.rect.relativeX:(0<d.elementRect.left?g.left=this.rect.left+d.elementRect.left:(g.width+=d.elementRect.left,g.left=this.rect.left),0<(d=g.left+g.width-(this.rect.left+this.winPane.width))&&(g.width-=d));g.left+=this.winTopScroll.x;for(var h in g)g[h]=CKEDITOR.tools.cssLength(g[h]);return g},addLine:function(){var a=CKEDITOR.dom.element.createFromHtml(this.lineTpl);a.appendTo(this.container);return a},prepare:function(a,c){this.relations=a;this.locations=c;this.hash=Math.random()},
cleanup:function(){var a,c;for(c in this.visible)a=this.visible[c],a.getCustomData("hash")!==this.hash&&this.hideLine(a)},queryViewport:function(){this.winPane=this.win.getViewPaneSize();this.winTopScroll=this.winTop.getScrollPosition();this.winTopPane=this.winTop.getViewPaneSize();this.rect=this.getClientRect(this.inline?this.editable:this.frame)},getClientRect:function(a){a=a.getClientRect();var c=this.container.getDocumentPosition(),d=this.container.getComputedStyle("position");a.relativeX=a.relativeY=
0;"static"!=d&&(a.relativeY=c.y,a.relativeX=c.x,a.top-=a.relativeY,a.bottom-=a.relativeY,a.left-=a.relativeX,a.right-=a.relativeX);return a}};var m={left:1,right:1,center:1},h={absolute:1,fixed:1};CKEDITOR.plugins.lineutils={finder:a,locator:e,liner:d}}(),function(){function a(a){return a.getName&&!a.hasAttribute("data-cke-temp")}CKEDITOR.plugins.add("widgetselection",{init:function(a){if(CKEDITOR.env.webkit){var d=CKEDITOR.plugins.widgetselection;a.on("contentDom",function(a){a=a.editor;var e=a.document,
k=a.editable();k.attachListener(e,"keydown",function(a){var e=a.data.$;65==a.data.getKey()&&(CKEDITOR.env.mac&&e.metaKey||!CKEDITOR.env.mac&&e.ctrlKey)&&CKEDITOR.tools.setTimeout(function(){d.addFillers(k)||d.removeFillers(k)},0)},null,null,-1);a.on("selectionCheck",function(a){d.removeFillers(a.editor.editable())});a.on("paste",function(a){a.data.dataValue=d.cleanPasteData(a.data.dataValue)});"selectall"in a.plugins&&d.addSelectAllIntegration(a)})}}});CKEDITOR.plugins.widgetselection={startFiller:null,
endFiller:null,fillerAttribute:"data-cke-filler-webkit",fillerContent:"\x26nbsp;",fillerTagName:"div",addFillers:function(e){var d=e.editor;if(!this.isWholeContentSelected(e)&&0<e.getChildCount()){var g=e.getFirst(a),l=e.getLast(a);g&&g.type==CKEDITOR.NODE_ELEMENT&&!g.isEditable()&&(this.startFiller=this.createFiller(),e.append(this.startFiller,1));l&&l.type==CKEDITOR.NODE_ELEMENT&&!l.isEditable()&&(this.endFiller=this.createFiller(!0),e.append(this.endFiller,0));if(this.hasFiller(e))return d=d.createRange(),
d.selectNodeContents(e),d.select(),!0}return!1},removeFillers:function(a){if(this.hasFiller(a)&&!this.isWholeContentSelected(a)){var d=a.findOne(this.fillerTagName+"["+this.fillerAttribute+"\x3dstart]"),g=a.findOne(this.fillerTagName+"["+this.fillerAttribute+"\x3dend]");this.startFiller&&d&&this.startFiller.equals(d)?this.removeFiller(this.startFiller,a):this.startFiller=d;this.endFiller&&g&&this.endFiller.equals(g)?this.removeFiller(this.endFiller,a):this.endFiller=g}},cleanPasteData:function(a){a&&
a.length&&(a=a.replace(this.createFillerRegex(),"").replace(this.createFillerRegex(!0),""));return a},isWholeContentSelected:function(a){var d=a.editor.getSelection().getRanges()[0];return!d||d&&d.collapsed?!1:(d=d.clone(),d.enlarge(CKEDITOR.ENLARGE_ELEMENT),!!(d&&a&&d.startContainer&&d.endContainer&&0===d.startOffset&&d.endOffset===a.getChildCount()&&d.startContainer.equals(a)&&d.endContainer.equals(a)))},hasFiller:function(a){return 0<a.find(this.fillerTagName+"["+this.fillerAttribute+"]").count()},
createFiller:function(a){var d=new CKEDITOR.dom.element(this.fillerTagName);d.setHtml(this.fillerContent);d.setAttribute(this.fillerAttribute,a?"end":"start");d.setAttribute("data-cke-temp",1);d.setStyles({display:"block",width:0,height:0,padding:0,border:0,margin:0,position:"absolute",top:0,left:"-9999px",opacity:0,overflow:"hidden"});return d},removeFiller:function(a,d){if(a){var g=d.editor,l=d.editor.getSelection().getRanges()[0].startPath(),k=g.createRange(),m,h;l.contains(a)&&(m=a.getHtml(),
h=!0);l="start"==a.getAttribute(this.fillerAttribute);a.remove();m&&0<m.length&&m!=this.fillerContent?(d.insertHtmlIntoRange(m,g.getSelection().getRanges()[0]),k.setStartAt(d.getChild(d.getChildCount()-1),CKEDITOR.POSITION_BEFORE_END),g.getSelection().selectRanges([k])):h&&(l?k.setStartAt(d.getFirst().getNext(),CKEDITOR.POSITION_AFTER_START):k.setEndAt(d.getLast().getPrevious(),CKEDITOR.POSITION_BEFORE_END),d.editor.getSelection().selectRanges([k]))}},createFillerRegex:function(a){var d=this.createFiller(a).getOuterHtml().replace(/style="[^"]*"/gi,
'style\x3d"[^"]*"').replace(/>[^<]*</gi,"\x3e[^\x3c]*\x3c");return new RegExp((a?"":"^")+d+(a?"$":""))},addSelectAllIntegration:function(a){var d=this;a.editable().attachListener(a,"beforeCommandExec",function(g){var l=a.editable();"selectAll"==g.data.name&&l&&d.addFillers(l)},null,null,9999)}}}(),"use strict",function(){function a(a){this.editor=a;this.registered={};this.instances={};this.selected=[];this.widgetHoldingFocusedEditable=this.focused=null;this._={nextId:0,upcasts:[],upcastCallbacks:[],
filters:{}};C(this);r(this);this.on("checkWidgets",m);this.editor.on("contentDomInvalidated",this.checkWidgets,this);n(this);H(this);w(this);y(this);F(this)}function e(a,b,c,d,f){var g=a.editor;CKEDITOR.tools.extend(this,d,{editor:g,id:b,inline:"span"==c.getParent().getName(),element:c,data:CKEDITOR.tools.extend({},"function"==typeof d.defaults?d.defaults():d.defaults),dataReady:!1,inited:!1,ready:!1,edit:e.prototype.edit,focusedEditable:null,definition:d,repository:a,draggable:!1!==d.draggable,_:{downcastFn:d.downcast&&
"string"==typeof d.downcast?d.downcasts[d.downcast]:d.downcast}},!0);a.fire("instanceCreated",this);Q(this,d);this.init&&this.init();this.inited=!0;(a=this.element.data("cke-widget-data"))&&this.setData(JSON.parse(decodeURIComponent(a)));f&&this.setData(f);this.data.classes||this.setData("classes",this.getClasses());this.dataReady=!0;Y(this);this.fire("data",this.data);this.isInited()&&g.editable().contains(this.wrapper)&&(this.ready=!0,this.fire("ready"))}function d(a,b,c){CKEDITOR.dom.element.call(this,
b.$);this.editor=a;this._={};b=this.filter=c.filter;CKEDITOR.dtd[this.getName()].p?(this.enterMode=b?b.getAllowedEnterMode(a.enterMode):a.enterMode,this.shiftEnterMode=b?b.getAllowedEnterMode(a.shiftEnterMode,!0):a.shiftEnterMode):this.enterMode=this.shiftEnterMode=CKEDITOR.ENTER_BR}function g(a,b){a.addCommand(b.name,{exec:function(a,c){function d(){a.widgets.finalizeCreation(h)}var e=a.widgets.focused;if(e&&e.name==b.name)e.edit();else if(b.insert)b.insert();else if(b.template){var e="function"==
typeof b.defaults?b.defaults():b.defaults,e=CKEDITOR.dom.element.createFromHtml(b.template.output(e)),f,g=a.widgets.wrapElement(e,b.name),h=new CKEDITOR.dom.documentFragment(g.getDocument());h.append(g);(f=a.widgets.initOn(e,b,c&&c.startupData))?(e=f.once("edit",function(b){if(b.data.dialog)f.once("dialog",function(b){b=b.data;var c,e;c=b.once("ok",d,null,null,20);e=b.once("cancel",function(b){b.data&&!1===b.data.hide||a.widgets.destroy(f,!0)});b.once("hide",function(){c.removeListener();e.removeListener()})});
else d()},null,null,999),f.edit(),e.removeListener()):d()}},allowedContent:b.allowedContent,requiredContent:b.requiredContent,contentForms:b.contentForms,contentTransformations:b.contentTransformations})}function l(a,b){function c(b,d,e){var f=CKEDITOR.tools.getIndex(a._.upcasts,function(a){return a[2]>e});0>f&&(f=a._.upcasts.length);a._.upcasts.splice(f,0,[b,d,e])}var d=b.upcast,e=b.upcastPriority||10;if(d)if("string"==typeof d)for(d=d.split(",");d.length;)c(b.upcasts[d.pop()],b.name,e);else c(d,
b.name,e)}function k(a,b){a.focused=null;if(b.isInited()){var c=b.editor.checkDirty();a.fire("widgetBlurred",{widget:b});b.setFocused(!1);!c&&b.editor.resetDirty()}}function m(a){a=a.data;if("wysiwyg"==this.editor.mode){var b=this.editor.editable(),c=this.instances,d,f,g,h;if(b){for(d in c)c[d].isReady()&&!b.contains(c[d].wrapper)&&this.destroy(c[d],!0);if(a&&a.initOnlyNew)c=this.initOnAll();else{var k=b.find(".cke_widget_wrapper"),c=[];d=0;for(f=k.count();d<f;d++){g=k.getItem(d);if(h=!this.getByElement(g,
!0)){a:{h=B;for(var l=g;l=l.getParent();)if(h(l)){h=!0;break a}h=!1}h=!h}h&&b.contains(g)&&(g.addClass("cke_widget_new"),c.push(this.initOn(g.getFirst(e.isDomWidgetElement))))}}a&&a.focusInited&&1==c.length&&c[0].focus()}}}function h(a,b,c){if(!c.allowedContent)return null;var d=this._.filters[a];d||(this._.filters[a]=d={});(a=d[b])||(d[b]=a=new CKEDITOR.filter(c.allowedContent));return a}function b(a){var b=[],c=a._.upcasts,d=a._.upcastCallbacks;return{toBeWrapped:b,iterator:function(a){var f,g,
h,k,l;if("data-cke-widget-wrapper"in a.attributes)return(a=a.getFirst(e.isParserWidgetElement))&&b.push([a]),!1;if("data-widget"in a.attributes)return b.push([a]),!1;if(l=c.length){if(a.attributes["data-cke-widget-upcasted"])return!1;k=0;for(f=d.length;k<f;++k)if(!1===d[k](a))return;for(k=0;k<l;++k)if(f=c[k],h={},g=f[0](a,h))return g instanceof CKEDITOR.htmlParser.element&&(a=g),a.attributes["data-cke-widget-data"]=encodeURIComponent(JSON.stringify(h)),a.attributes["data-cke-widget-upcasted"]=1,b.push([a,
f[1]]),!1}}}}function c(a,b){return{tabindex:-1,contenteditable:"false","data-cke-widget-wrapper":1,"data-cke-filter":"off","class":"cke_widget_wrapper cke_widget_new cke_widget_"+(a?"inline":"block")+(b?" cke_widget_"+b:"")}}function f(a,b,c){if(a.type==CKEDITOR.NODE_ELEMENT){var d=CKEDITOR.dtd[a.name];if(d&&!d[c.name]){var d=a.split(b),e=a.parent;b=d.getIndex();a.children.length||(--b,a.remove());d.children.length||d.remove();return f(e,b,c)}}a.add(c,b)}function p(a,b){return"boolean"==typeof a.inline?
a.inline:!!CKEDITOR.dtd.$inline[b]}function B(a){return a.hasAttribute("data-cke-temp")}function x(a,b,c,d){var e=a.editor;e.fire("lockSnapshot");c?(d=c.data("cke-widget-editable"),d=b.editables[d],a.widgetHoldingFocusedEditable=b,b.focusedEditable=d,c.addClass("cke_widget_editable_focused"),d.filter&&e.setActiveFilter(d.filter),e.setActiveEnterMode(d.enterMode,d.shiftEnterMode)):(d||b.focusedEditable.removeClass("cke_widget_editable_focused"),b.focusedEditable=null,a.widgetHoldingFocusedEditable=
null,e.setActiveFilter(null),e.setActiveEnterMode(null,null));e.fire("unlockSnapshot")}function t(a){a.contextMenu&&a.contextMenu.addListener(function(b){if(b=a.widgets.getByElement(b,!0))return b.fire("contextMenu",{})})}function u(a,b){return CKEDITOR.tools.trim(b)}function y(a){var b=a.editor,c=CKEDITOR.plugins.lineutils;b.on("dragstart",function(c){var d=c.data.target;e.isDomDragHandler(d)&&(d=a.getByElement(d),c.data.dataTransfer.setData("cke/widget-id",d.id),b.focus(),d.focus())});b.on("drop",
function(c){var d=c.data.dataTransfer,e=d.getData("cke/widget-id"),f=d.getTransferType(b),d=b.createRange();""!==e&&f===CKEDITOR.DATA_TRANSFER_CROSS_EDITORS?c.cancel():""!==e&&f==CKEDITOR.DATA_TRANSFER_INTERNAL&&(e=a.instances[e])&&(d.setStartBefore(e.wrapper),d.setEndAfter(e.wrapper),c.data.dragRange=d,delete CKEDITOR.plugins.clipboard.dragStartContainerChildCount,delete CKEDITOR.plugins.clipboard.dragEndContainerChildCount,c.data.dataTransfer.setData("text/html",b.editable().getHtmlFromRange(d).getHtml()),
b.widgets.destroy(e,!0))});b.on("contentDom",function(){var d=b.editable();CKEDITOR.tools.extend(a,{finder:new c.finder(b,{lookups:{"default":function(b){if(!b.is(CKEDITOR.dtd.$listItem)&&b.is(CKEDITOR.dtd.$block)&&!e.isDomNestedEditable(b)&&!a._.draggedWidget.wrapper.contains(b)){var c=e.getNestedEditable(d,b);if(c){b=a._.draggedWidget;if(a.getByElement(c)==b)return;c=CKEDITOR.filter.instances[c.data("cke-filter")];b=b.requiredContent;if(c&&b&&!c.check(b))return}return CKEDITOR.LINEUTILS_BEFORE|
CKEDITOR.LINEUTILS_AFTER}}}}),locator:new c.locator(b),liner:new c.liner(b,{lineStyle:{cursor:"move !important","border-top-color":"#666"},tipLeftStyle:{"border-left-color":"#666"},tipRightStyle:{"border-right-color":"#666"}})},!0)})}function H(a){var b=a.editor;b.on("contentDom",function(){var c=b.editable(),d=c.isInline()?c:b.document,f,g;c.attachListener(d,"mousedown",function(c){var d=c.data.getTarget();if(!d.type)return!1;f=a.getByElement(d);g=0;f&&(f.inline&&d.type==CKEDITOR.NODE_ELEMENT&&d.hasAttribute("data-cke-widget-drag-handler")?
(g=1,a.focused!=f&&b.getSelection().removeAllRanges()):e.getNestedEditable(f.wrapper,d)?f=null:(c.data.preventDefault(),CKEDITOR.env.ie||f.focus()))});c.attachListener(d,"mouseup",function(){g&&f&&f.wrapper&&(g=0,f.focus())});CKEDITOR.env.ie&&c.attachListener(d,"mouseup",function(){setTimeout(function(){f&&f.wrapper&&c.contains(f.wrapper)&&(f.focus(),f=null)})})});b.on("doubleclick",function(b){var c=a.getByElement(b.data.element);if(c&&!e.getNestedEditable(c.wrapper,b.data.element))return c.fire("doubleclick",
{element:b.data.element})},null,null,1)}function w(a){a.editor.on("key",function(b){var c=a.focused,d=a.widgetHoldingFocusedEditable,e;c?e=c.fire("key",{keyCode:b.data.keyCode}):d&&(c=b.data.keyCode,b=d.focusedEditable,c==CKEDITOR.CTRL+65?(c=b.getBogus(),d=d.editor.createRange(),d.selectNodeContents(b),c&&d.setEndAt(c,CKEDITOR.POSITION_BEFORE_START),d.select(),e=!1):8==c||46==c?(e=d.editor.getSelection().getRanges(),d=e[0],e=!(1==e.length&&d.collapsed&&d.checkBoundaryOfElement(b,CKEDITOR[8==c?"START":
"END"]))):e=void 0);return e},null,null,1)}function F(a){function b(c){a.focused&&J(a.focused,"cut"==c.name)}var c=a.editor;c.on("contentDom",function(){var a=c.editable();a.attachListener(a,"copy",b);a.attachListener(a,"cut",b)})}function n(a){var b=a.editor;b.on("selectionCheck",function(){a.fire("checkSelection")});a.on("checkSelection",a.checkSelection,a);b.on("selectionChange",function(c){var d=(c=e.getNestedEditable(b.editable(),c.data.selection.getStartElement()))&&a.getByElement(c),f=a.widgetHoldingFocusedEditable;
f?f===d&&f.focusedEditable.equals(c)||(x(a,f,null),d&&c&&x(a,d,c)):d&&c&&x(a,d,c)});b.on("dataReady",function(){D(a).commit()});b.on("blur",function(){var b;(b=a.focused)&&k(a,b);(b=a.widgetHoldingFocusedEditable)&&x(a,b,null)})}function r(a){var b=a.editor,c={};b.on("toDataFormat",function(b){var d=CKEDITOR.tools.getNextNumber(),f=[];b.data.downcastingSessionId=d;c[d]=f;b.data.dataValue.forEach(function(b){var c=b.attributes,d;if("data-cke-widget-id"in c){if(c=a.instances[c["data-cke-widget-id"]])d=
b.getFirst(e.isParserWidgetElement),f.push({wrapper:b,element:d,widget:c,editables:{}}),"1"!=d.attributes["data-cke-widget-keep-attr"]&&delete d.attributes["data-widget"]}else if("data-cke-widget-editable"in c)return f[f.length-1].editables[c["data-cke-widget-editable"]]=b,!1},CKEDITOR.NODE_ELEMENT,!0)},null,null,8);b.on("toDataFormat",function(a){if(a.data.downcastingSessionId){a=c[a.data.downcastingSessionId];for(var b,d,e,f,g,h;b=a.shift();){d=b.widget;e=b.element;f=d._.downcastFn&&d._.downcastFn.call(d,
e);for(h in b.editables)g=b.editables[h],delete g.attributes.contenteditable,g.setHtml(d.editables[h].getData());f||(f=e);b.wrapper.replaceWith(f)}}},null,null,13);b.on("contentDomUnload",function(){a.destroyAll(!0)})}function C(a){var c=a.editor,d,f;c.on("toHtml",function(c){var f=b(a),g;for(c.data.dataValue.forEach(f.iterator,CKEDITOR.NODE_ELEMENT,!0);g=f.toBeWrapped.pop();){var h=g[0],k=h.parent;k.type==CKEDITOR.NODE_ELEMENT&&k.attributes["data-cke-widget-wrapper"]&&k.replaceWith(h);a.wrapElement(g[0],
g[1])}d=c.data.protectedWhitespaces?3==c.data.dataValue.children.length&&e.isParserWidgetWrapper(c.data.dataValue.children[1]):1==c.data.dataValue.children.length&&e.isParserWidgetWrapper(c.data.dataValue.children[0])},null,null,8);c.on("dataReady",function(){if(f)for(var b=c.editable().find(".cke_widget_wrapper"),d,g,h=0,k=b.count();h<k;++h)d=b.getItem(h),g=d.getFirst(e.isDomWidgetElement),g.type==CKEDITOR.NODE_ELEMENT&&g.data("widget")?(g.replace(d),a.wrapElement(g)):d.remove();f=0;a.destroyAll(!0);
a.initOnAll()});c.on("loadSnapshot",function(b){/data-cke-widget/.test(b.data)&&(f=1);a.destroyAll(!0)},null,null,9);c.on("paste",function(a){a=a.data;a.dataValue=a.dataValue.replace(ca,u);a.range&&(a=e.getNestedEditable(c.editable(),a.range.startContainer))&&(a=CKEDITOR.filter.instances[a.data("cke-filter")])&&c.setActiveFilter(a)});c.on("afterInsertHtml",function(b){b.data.intoRange?a.checkWidgets({initOnlyNew:!0}):(c.fire("lockSnapshot"),a.checkWidgets({initOnlyNew:!0,focusInited:d}),c.fire("unlockSnapshot"))})}
function D(a){var b=a.selected,c=[],d=b.slice(0),e=null;return{select:function(a){0>CKEDITOR.tools.indexOf(b,a)&&c.push(a);a=CKEDITOR.tools.indexOf(d,a);0<=a&&d.splice(a,1);return this},focus:function(a){e=a;return this},commit:function(){var f=a.focused!==e,g,h;a.editor.fire("lockSnapshot");for(f&&(g=a.focused)&&k(a,g);g=d.pop();)b.splice(CKEDITOR.tools.indexOf(b,g),1),g.isInited()&&(h=g.editor.checkDirty(),g.setSelected(!1),!h&&g.editor.resetDirty());f&&e&&(h=a.editor.checkDirty(),a.focused=e,a.fire("widgetFocused",
{widget:e}),e.setFocused(!0),!h&&a.editor.resetDirty());for(;g=c.pop();)b.push(g),g.setSelected(!0);a.editor.fire("unlockSnapshot")}}}function z(a,b,c){var d=0;b=P(b);var e=a.data.classes||{},f;if(b){for(e=CKEDITOR.tools.clone(e);f=b.pop();)c?e[f]||(d=e[f]=1):e[f]&&(delete e[f],d=1);d&&a.setData("classes",e)}}function K(a){a.cancel()}function J(a,b){var c=a.editor,d=c.document;if(!d.getById("cke_copybin")){var e=c.blockless||CKEDITOR.env.ie?"span":"div",f=d.createElement(e),g=d.createElement(e),e=
CKEDITOR.env.ie&&9>CKEDITOR.env.version;g.setAttributes({id:"cke_copybin","data-cke-temp":"1"});f.setStyles({position:"absolute",width:"1px",height:"1px",overflow:"hidden"});f.setStyle("ltr"==c.config.contentsLangDirection?"left":"right","-5000px");var h=c.createRange();h.setStartBefore(a.wrapper);h.setEndAfter(a.wrapper);f.setHtml('\x3cspan data-cke-copybin-start\x3d"1"\x3e​\x3c/span\x3e'+c.editable().getHtmlFromRange(h).getHtml()+'\x3cspan data-cke-copybin-end\x3d"1"\x3e​\x3c/span\x3e');c.fire("saveSnapshot");
c.fire("lockSnapshot");g.append(f);c.editable().append(g);var k=c.on("selectionChange",K,null,null,0),l=a.repository.on("checkSelection",K,null,null,0);if(e)var m=d.getDocumentElement().$,n=m.scrollTop;h=c.createRange();h.selectNodeContents(f);h.select();e&&(m.scrollTop=n);setTimeout(function(){b||a.focus();g.remove();k.removeListener();l.removeListener();c.fire("unlockSnapshot");b&&(a.repository.del(a),c.fire("saveSnapshot"))},100)}}function P(a){return(a=(a=a.getDefinition().attributes)&&a["class"])?
a.split(/\s+/):null}function L(){var a=CKEDITOR.document.getActive(),b=this.editor,c=b.editable();(c.isInline()?c:b.document.getWindow().getFrame()).equals(a)&&b.focusManager.focus(c)}function O(){CKEDITOR.env.gecko&&this.editor.unlockSelection();CKEDITOR.env.webkit||(this.editor.forceNextSelectionCheck(),this.editor.selectionChange(1))}function S(a){var b=null;a.on("data",function(){var a=this.data.classes,c;if(b!=a){for(c in b)a&&a[c]||this.removeClass(c);for(c in a)this.addClass(c);b=a}})}function v(a){a.on("data",
function(){if(a.wrapper){var b=this.getLabel?this.getLabel():this.editor.lang.widget.label.replace(/%1/,this.pathName||this.element.getName());a.wrapper.setAttribute("role","region");a.wrapper.setAttribute("aria-label",b)}},null,null,9999)}function q(a){if(a.draggable){var b=a.editor,c=a.wrapper.getLast(e.isDomDragHandlerContainer),d;c?d=c.findOne("img"):(c=new CKEDITOR.dom.element("span",b.document),c.setAttributes({"class":"cke_reset cke_widget_drag_handler_container",style:"background:rgba(220,220,220,0.5);background-image:url("+
b.plugins.widget.path+"images/handle.png)"}),d=new CKEDITOR.dom.element("img",b.document),d.setAttributes({"class":"cke_reset cke_widget_drag_handler","data-cke-widget-drag-handler":"1",src:CKEDITOR.tools.transparentImageData,width:15,title:b.lang.widget.move,height:15,role:"presentation"}),a.inline&&d.setAttribute("draggable","true"),c.append(d),a.wrapper.append(c));a.wrapper.on("dragover",function(a){a.data.preventDefault()});a.wrapper.on("mouseenter",a.updateDragHandlerPosition,a);setTimeout(function(){a.on("data",
a.updateDragHandlerPosition,a)},50);if(!a.inline&&(d.on("mousedown",N,a),CKEDITOR.env.ie&&9>CKEDITOR.env.version))d.on("dragstart",function(a){a.data.preventDefault(!0)});a.dragHandlerContainer=c}}function N(a){function b(){var c;for(p.reset();c=h.pop();)c.removeListener();var d=k;c=a.sender;var e=this.repository.finder,f=this.repository.liner,g=this.editor,l=this.editor.editable();CKEDITOR.tools.isEmpty(f.visible)||(d=e.getRange(d[0]),this.focus(),g.fire("drop",{dropRange:d,target:d.startContainer}));
l.removeClass("cke_widget_dragging");f.hideVisible();g.fire("dragend",{target:c})}var c=this.repository.finder,d=this.repository.locator,e=this.repository.liner,f=this.editor,g=f.editable(),h=[],k=[],l,m;this.repository._.draggedWidget=this;var n=c.greedySearch(),p=CKEDITOR.tools.eventsBuffer(50,function(){l=d.locate(n);k=d.sort(m,1);k.length&&(e.prepare(n,l),e.placeLine(k[0]),e.cleanup())});g.addClass("cke_widget_dragging");h.push(g.on("mousemove",function(a){m=a.data.$.clientY;p.input()}));f.fire("dragstart",
{target:a.sender});h.push(f.document.once("mouseup",b,this));g.isInline()||h.push(CKEDITOR.document.once("mouseup",b,this))}function G(a){var b,c,d=a.editables;a.editables={};if(a.editables)for(b in d)c=d[b],a.initEditable(b,"string"==typeof c?{selector:c}:c)}function X(a){if(a.mask){var b=a.wrapper.findOne(".cke_widget_mask");b||(b=new CKEDITOR.dom.element("img",a.editor.document),b.setAttributes({src:CKEDITOR.tools.transparentImageData,"class":"cke_reset cke_widget_mask"}),a.wrapper.append(b));
a.mask=b}}function R(a){if(a.parts){var b={},c,d;for(d in a.parts)c=a.wrapper.findOne(a.parts[d]),b[d]=c;a.parts=b}}function Q(a,b){Z(a);R(a);G(a);X(a);q(a);S(a);v(a);if(CKEDITOR.env.ie&&9>CKEDITOR.env.version)a.wrapper.on("dragstart",function(b){var c=b.data.getTarget();e.getNestedEditable(a,c)||a.inline&&e.isDomDragHandler(c)||b.data.preventDefault()});a.wrapper.removeClass("cke_widget_new");a.element.addClass("cke_widget_element");a.on("key",function(b){b=b.data.keyCode;if(13==b)a.edit();else{if(b==
CKEDITOR.CTRL+67||b==CKEDITOR.CTRL+88){J(a,b==CKEDITOR.CTRL+88);return}if(b in V||CKEDITOR.CTRL&b||CKEDITOR.ALT&b)return}return!1},null,null,999);a.on("doubleclick",function(b){a.edit()&&b.cancel()});if(b.data)a.on("data",b.data);if(b.edit)a.on("edit",b.edit)}function Z(a){(a.wrapper=a.element.getParent()).setAttribute("data-cke-widget-id",a.id)}function Y(a){a.element.data("cke-widget-data",encodeURIComponent(JSON.stringify(a.data)))}CKEDITOR.plugins.add("widget",{requires:"lineutils,clipboard,widgetselection",
onLoad:function(){CKEDITOR.addCss(".cke_widget_wrapper{position:relative;outline:none}.cke_widget_inline{display:inline-block}.cke_widget_wrapper:hover\x3e.cke_widget_element{outline:2px solid yellow;cursor:default}.cke_widget_wrapper:hover .cke_widget_editable{outline:2px solid yellow}.cke_widget_wrapper.cke_widget_focused\x3e.cke_widget_element,.cke_widget_wrapper .cke_widget_editable.cke_widget_editable_focused{outline:2px solid #ace}.cke_widget_editable{cursor:text}.cke_widget_drag_handler_container{position:absolute;width:15px;height:0;display:none;opacity:0.75;transition:height 0s 0.2s;line-height:0}.cke_widget_wrapper:hover\x3e.cke_widget_drag_handler_container{height:15px;transition:none}.cke_widget_drag_handler_container:hover{opacity:1}img.cke_widget_drag_handler{cursor:move;width:15px;height:15px;display:inline-block}.cke_widget_mask{position:absolute;top:0;left:0;width:100%;height:100%;display:block}.cke_editable.cke_widget_dragging, .cke_editable.cke_widget_dragging *{cursor:move !important}")},
beforeInit:function(b){b.widgets=new a(b)},afterInit:function(a){var b=a.widgets.registered,c,d,e;for(d in b)c=b[d],(e=c.button)&&a.ui.addButton&&a.ui.addButton(CKEDITOR.tools.capitalize(c.name,!0),{label:e,command:c.name,toolbar:"insert,10"});t(a)}});a.prototype={MIN_SELECTION_CHECK_INTERVAL:500,add:function(a,b){b=CKEDITOR.tools.prototypedCopy(b);b.name=a;b._=b._||{};this.editor.fire("widgetDefinition",b);b.template&&(b.template=new CKEDITOR.template(b.template));g(this.editor,b);l(this,b);return this.registered[a]=
b},addUpcastCallback:function(a){this._.upcastCallbacks.push(a)},checkSelection:function(){var a=this.editor.getSelection(),b=a.getSelectedElement(),c=D(this),d;if(b&&(d=this.getByElement(b,!0)))return c.focus(d).select(d).commit();a=a.getRanges()[0];if(!a||a.collapsed)return c.commit();a=new CKEDITOR.dom.walker(a);for(a.evaluator=e.isDomWidgetWrapper;b=a.next();)c.select(this.getByElement(b));c.commit()},checkWidgets:function(a){this.fire("checkWidgets",CKEDITOR.tools.copy(a||{}))},del:function(a){if(this.focused===
a){var b=a.editor,c=b.createRange(),d;(d=c.moveToClosestEditablePosition(a.wrapper,!0))||(d=c.moveToClosestEditablePosition(a.wrapper,!1));d&&b.getSelection().selectRanges([c])}a.wrapper.remove();this.destroy(a,!0)},destroy:function(a,b){this.widgetHoldingFocusedEditable===a&&x(this,a,null,b);a.destroy(b);delete this.instances[a.id];this.fire("instanceDestroyed",a)},destroyAll:function(a,b){var c,d,e=this.instances;if(b&&!a){d=b.find(".cke_widget_wrapper");for(var e=d.count(),f=0;f<e;++f)(c=this.getByElement(d.getItem(f),
!0))&&this.destroy(c)}else for(d in e)c=e[d],this.destroy(c,a)},finalizeCreation:function(a){(a=a.getFirst())&&e.isDomWidgetWrapper(a)&&(this.editor.insertElement(a),a=this.getByElement(a),a.ready=!0,a.fire("ready"),a.focus())},getByElement:function(){function a(c){return c.is(b)&&c.data("cke-widget-id")}var b={div:1,span:1};return function(b,c){if(!b)return null;var d=a(b);if(!c&&!d){var e=this.editor.editable();do b=b.getParent();while(b&&!b.equals(e)&&!(d=a(b)))}return this.instances[d]||null}}(),
initOn:function(a,b,c){b?"string"==typeof b&&(b=this.registered[b]):b=this.registered[a.data("widget")];if(!b)return null;var d=this.wrapElement(a,b.name);return d?d.hasClass("cke_widget_new")?(a=new e(this,this._.nextId++,a,b,c),a.isInited()?this.instances[a.id]=a:null):this.getByElement(a):null},initOnAll:function(a){a=(a||this.editor.editable()).find(".cke_widget_new");for(var b=[],c,d=a.count();d--;)(c=this.initOn(a.getItem(d).getFirst(e.isDomWidgetElement)))&&b.push(c);return b},onWidget:function(a){var b=
Array.prototype.slice.call(arguments);b.shift();for(var c in this.instances){var d=this.instances[c];d.name==a&&d.on.apply(d,b)}this.on("instanceCreated",function(c){c=c.data;c.name==a&&c.on.apply(c,b)})},parseElementClasses:function(a){if(!a)return null;a=CKEDITOR.tools.trim(a).split(/\s+/);for(var b,c={},d=0;b=a.pop();)-1==b.indexOf("cke_")&&(c[b]=d=1);return d?c:null},wrapElement:function(a,b){var d=null,e,g;if(a instanceof CKEDITOR.dom.element){b=b||a.data("widget");e=this.registered[b];if(!e)return null;
if((d=a.getParent())&&d.type==CKEDITOR.NODE_ELEMENT&&d.data("cke-widget-wrapper"))return d;a.hasAttribute("data-cke-widget-keep-attr")||a.data("cke-widget-keep-attr",a.data("widget")?1:0);a.data("widget",b);g=p(e,a.getName());d=new CKEDITOR.dom.element(g?"span":"div");d.setAttributes(c(g,b));d.data("cke-display-name",e.pathName?e.pathName:a.getName());a.getParent(!0)&&d.replace(a);a.appendTo(d)}else if(a instanceof CKEDITOR.htmlParser.element){b=b||a.attributes["data-widget"];e=this.registered[b];
if(!e)return null;if((d=a.parent)&&d.type==CKEDITOR.NODE_ELEMENT&&d.attributes["data-cke-widget-wrapper"])return d;"data-cke-widget-keep-attr"in a.attributes||(a.attributes["data-cke-widget-keep-attr"]=a.attributes["data-widget"]?1:0);b&&(a.attributes["data-widget"]=b);g=p(e,a.name);d=new CKEDITOR.htmlParser.element(g?"span":"div",c(g,b));d.attributes["data-cke-display-name"]=e.pathName?e.pathName:a.name;e=a.parent;var h;e&&(h=a.getIndex(),a.remove());d.add(a);e&&f(e,h,d)}return d},_tests_createEditableFilter:h};
CKEDITOR.event.implementOn(a.prototype);e.prototype={addClass:function(a){this.element.addClass(a);this.wrapper.addClass(e.WRAPPER_CLASS_PREFIX+a)},applyStyle:function(a){z(this,a,1)},checkStyleActive:function(a){a=P(a);var b;if(!a)return!1;for(;b=a.pop();)if(!this.hasClass(b))return!1;return!0},destroy:function(a){this.fire("destroy");if(this.editables)for(var b in this.editables)this.destroyEditable(b,a);a||("0"==this.element.data("cke-widget-keep-attr")&&this.element.removeAttribute("data-widget"),
this.element.removeAttributes(["data-cke-widget-data","data-cke-widget-keep-attr"]),this.element.removeClass("cke_widget_element"),this.element.replace(this.wrapper));this.wrapper=null},destroyEditable:function(a,b){var c=this.editables[a];c.removeListener("focus",O);c.removeListener("blur",L);this.editor.focusManager.remove(c);b||(this.repository.destroyAll(!1,c),c.removeClass("cke_widget_editable"),c.removeClass("cke_widget_editable_focused"),c.removeAttributes(["contenteditable","data-cke-widget-editable",
"data-cke-enter-mode"]));delete this.editables[a]},edit:function(){var a={dialog:this.dialog},b=this;if(!1===this.fire("edit",a)||!a.dialog)return!1;this.editor.openDialog(a.dialog,function(a){var c,d;!1!==b.fire("dialog",a)&&(c=a.on("show",function(){a.setupContent(b)}),d=a.on("ok",function(){var c,d=b.on("data",function(a){c=1;a.cancel()},null,null,0);b.editor.fire("saveSnapshot");a.commitContent(b);d.removeListener();c&&(b.fire("data",b.data),b.editor.fire("saveSnapshot"))}),a.once("hide",function(){c.removeListener();
d.removeListener()}))});return!0},getClasses:function(){return this.repository.parseElementClasses(this.element.getAttribute("class"))},hasClass:function(a){return this.element.hasClass(a)},initEditable:function(a,b){var c=this._findOneNotNested(b.selector);return c&&c.is(CKEDITOR.dtd.$editable)?(c=new d(this.editor,c,{filter:h.call(this.repository,this.name,a,b)}),this.editables[a]=c,c.setAttributes({contenteditable:"true","data-cke-widget-editable":a,"data-cke-enter-mode":c.enterMode}),c.filter&&
c.data("cke-filter",c.filter.id),c.addClass("cke_widget_editable"),c.removeClass("cke_widget_editable_focused"),b.pathName&&c.data("cke-display-name",b.pathName),this.editor.focusManager.add(c),c.on("focus",O,this),CKEDITOR.env.ie&&c.on("blur",L,this),c._.initialSetData=!0,c.setData(c.getHtml()),!0):!1},_findOneNotNested:function(a){a=this.wrapper.find(a);for(var b,c,d=0;d<a.count();d++)if(b=a.getItem(d),c=b.getAscendant(e.isDomWidgetWrapper),this.wrapper.equals(c))return b;return null},isInited:function(){return!(!this.wrapper||
!this.inited)},isReady:function(){return this.isInited()&&this.ready},focus:function(){var a=this.editor.getSelection();if(a){var b=this.editor.checkDirty();a.fake(this.wrapper);!b&&this.editor.resetDirty()}this.editor.focus()},removeClass:function(a){this.element.removeClass(a);this.wrapper.removeClass(e.WRAPPER_CLASS_PREFIX+a)},removeStyle:function(a){z(this,a,0)},setData:function(a,b){var c=this.data,d=0;if("string"==typeof a)c[a]!==b&&(c[a]=b,d=1);else{var e=a;for(a in e)c[a]!==e[a]&&(d=1,c[a]=
e[a])}d&&this.dataReady&&(Y(this),this.fire("data",c));return this},setFocused:function(a){this.wrapper[a?"addClass":"removeClass"]("cke_widget_focused");this.fire(a?"focus":"blur");return this},setSelected:function(a){this.wrapper[a?"addClass":"removeClass"]("cke_widget_selected");this.fire(a?"select":"deselect");return this},updateDragHandlerPosition:function(){var a=this.editor,b=this.element.$,c=this._.dragHandlerOffset,b={x:b.offsetLeft,y:b.offsetTop-15};c&&b.x==c.x&&b.y==c.y||(c=a.checkDirty(),
a.fire("lockSnapshot"),this.dragHandlerContainer.setStyles({top:b.y+"px",left:b.x+"px",display:"block"}),a.fire("unlockSnapshot"),!c&&a.resetDirty(),this._.dragHandlerOffset=b)}};CKEDITOR.event.implementOn(e.prototype);e.getNestedEditable=function(a,b){return!b||b.equals(a)?null:e.isDomNestedEditable(b)?b:e.getNestedEditable(a,b.getParent())};e.isDomDragHandler=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&a.hasAttribute("data-cke-widget-drag-handler")};e.isDomDragHandlerContainer=function(a){return a.type==
CKEDITOR.NODE_ELEMENT&&a.hasClass("cke_widget_drag_handler_container")};e.isDomNestedEditable=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&a.hasAttribute("data-cke-widget-editable")};e.isDomWidgetElement=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&a.hasAttribute("data-widget")};e.isDomWidgetWrapper=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&a.hasAttribute("data-cke-widget-wrapper")};e.isParserWidgetElement=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&!!a.attributes["data-widget"]};
e.isParserWidgetWrapper=function(a){return a.type==CKEDITOR.NODE_ELEMENT&&!!a.attributes["data-cke-widget-wrapper"]};e.WRAPPER_CLASS_PREFIX="cke_widget_wrapper_";d.prototype=CKEDITOR.tools.extend(CKEDITOR.tools.prototypedCopy(CKEDITOR.dom.element.prototype),{setData:function(a){this._.initialSetData||this.editor.widgets.destroyAll(!1,this);this._.initialSetData=!1;a=this.editor.dataProcessor.toHtml(a,{context:this.getName(),filter:this.filter,enterMode:this.enterMode});this.setHtml(a);this.editor.widgets.initOnAll(this)},
getData:function(){return this.editor.dataProcessor.toDataFormat(this.getHtml(),{context:this.getName(),filter:this.filter,enterMode:this.enterMode})}});var ca=/^(?:<(?:div|span)(?: data-cke-temp="1")?(?: id="cke_copybin")?(?: data-cke-temp="1")?>)?(?:<(?:div|span)(?: style="[^"]+")?>)?<span [^>]*data-cke-copybin-start="1"[^>]*>.?<\/span>([\s\S]+)<span [^>]*data-cke-copybin-end="1"[^>]*>.?<\/span>(?:<\/(?:div|span)>)?(?:<\/(?:div|span)>)?$/i,V={37:1,38:1,39:1,40:1,8:1,46:1};(function(){function a(){}
function b(a,c,d){return d&&this.checkElement(a)?(a=d.widgets.getByElement(a,!0))&&a.checkStyleActive(this):!1}CKEDITOR.style.addCustomHandler({type:"widget",setup:function(a){this.widget=a.widget},apply:function(a){a instanceof CKEDITOR.editor&&this.checkApplicable(a.elementPath(),a)&&a.widgets.focused.applyStyle(this)},remove:function(a){a instanceof CKEDITOR.editor&&this.checkApplicable(a.elementPath(),a)&&a.widgets.focused.removeStyle(this)},checkActive:function(a,b){return this.checkElementMatch(a.lastElement,
0,b)},checkApplicable:function(a,b){return b instanceof CKEDITOR.editor?this.checkElement(a.lastElement):!1},checkElementMatch:b,checkElementRemovable:b,checkElement:function(a){return e.isDomWidgetWrapper(a)?(a=a.getFirst(e.isDomWidgetElement))&&a.data("widget")==this.widget:!1},buildPreview:function(a){return a||this._.definition.name},toAllowedContentRules:function(a){if(!a)return null;a=a.widgets.registered[this.widget];var b,c={};if(!a)return null;if(a.styleableElements){b=this.getClassesArray();
if(!b)return null;c[a.styleableElements]={classes:b,propertiesOnly:!0};return c}return a.styleToAllowedContentRules?a.styleToAllowedContentRules(this):null},getClassesArray:function(){var a=this._.definition.attributes&&this._.definition.attributes["class"];return a?CKEDITOR.tools.trim(a).split(/\s+/):null},applyToRange:a,removeFromRange:a,applyToObject:a})})();CKEDITOR.plugins.widget=e;e.repository=a;e.nestedEditable=d}(),CKEDITOR.config.plugins="dialogui,dialog,clipboard,confighelper,entities,floatingspace,undo,lineutils,widgetselection,widget",
CKEDITOR.config.skin="minimalist",function(){var a=function(a,d){var g=CKEDITOR.getUrl("plugins/"+d);a=a.split(",");for(var l=0;l<a.length;l++)CKEDITOR.skin.icons[a[l]]={path:g,offset:-a[++l],bgsize:a[++l]}};CKEDITOR.env.hidpi?a("about,0,,bold,24,,italic,48,,strike,72,,subscript,96,,superscript,120,,underline,144,,bidiltr,168,,bidirtl,192,,blockquote,216,,copy-rtl,240,,copy,264,,cut-rtl,288,,cut,312,,paste-rtl,336,,paste,360,,codesnippet,384,,bgcolor,408,,textcolor,432,,copyformatting,456,,creatediv,480,,docprops-rtl,504,,docprops,528,,embed,552,,embedsemantic,576,,find-rtl,600,,find,624,,replace,648,,flash,672,,button,696,,checkbox,720,,form,744,,hiddenfield,768,,imagebutton,792,,radio,816,,select-rtl,840,,select,864,,textarea-rtl,888,,textarea,912,,textfield-rtl,936,,textfield,960,,horizontalrule,984,,iframe,1008,,image,1032,,indent-rtl,1056,,indent,1080,,outdent-rtl,1104,,outdent,1128,,justifyblock,1152,,justifycenter,1176,,justifyleft,1200,,justifyright,1224,,language,1248,,anchor-rtl,1272,,anchor,1296,,link,1320,,unlink,1344,,bulletedlist-rtl,1368,,bulletedlist,1392,,numberedlist-rtl,1416,,numberedlist,1440,,mathjax,1464,,maximize,1488,,newpage-rtl,1512,,newpage,1536,,pagebreak-rtl,1560,,pagebreak,1584,,pastefromword-rtl,1608,,pastefromword,1632,,pastetext-rtl,1656,,pastetext,1680,,placeholder,1704,,preview-rtl,1728,,preview,1752,,print,1776,,removeformat,1800,,save,1824,,selectall,1848,,showblocks-rtl,1872,,showblocks,1896,,smiley,1920,,source-rtl,1944,,source,1968,,sourcedialog-rtl,1992,,sourcedialog,2016,,specialchar,2040,,table,2064,,templates-rtl,2088,,templates,2112,,uicolor,2136,,redo-rtl,2160,,redo,2184,,undo-rtl,2208,,undo,2232,,simplebox,4512,auto",
"icons_hidpi.png"):a("about,0,auto,bold,24,auto,italic,48,auto,strike,72,auto,subscript,96,auto,superscript,120,auto,underline,144,auto,bidiltr,168,auto,bidirtl,192,auto,blockquote,216,auto,copy-rtl,240,auto,copy,264,auto,cut-rtl,288,auto,cut,312,auto,paste-rtl,336,auto,paste,360,auto,codesnippet,384,auto,bgcolor,408,auto,textcolor,432,auto,copyformatting,456,auto,creatediv,480,auto,docprops-rtl,504,auto,docprops,528,auto,embed,552,auto,embedsemantic,576,auto,find-rtl,600,auto,find,624,auto,replace,648,auto,flash,672,auto,button,696,auto,checkbox,720,auto,form,744,auto,hiddenfield,768,auto,imagebutton,792,auto,radio,816,auto,select-rtl,840,auto,select,864,auto,textarea-rtl,888,auto,textarea,912,auto,textfield-rtl,936,auto,textfield,960,auto,horizontalrule,984,auto,iframe,1008,auto,image,1032,auto,indent-rtl,1056,auto,indent,1080,auto,outdent-rtl,1104,auto,outdent,1128,auto,justifyblock,1152,auto,justifycenter,1176,auto,justifyleft,1200,auto,justifyright,1224,auto,language,1248,auto,anchor-rtl,1272,auto,anchor,1296,auto,link,1320,auto,unlink,1344,auto,bulletedlist-rtl,1368,auto,bulletedlist,1392,auto,numberedlist-rtl,1416,auto,numberedlist,1440,auto,mathjax,1464,auto,maximize,1488,auto,newpage-rtl,1512,auto,newpage,1536,auto,pagebreak-rtl,1560,auto,pagebreak,1584,auto,pastefromword-rtl,1608,auto,pastefromword,1632,auto,pastetext-rtl,1656,auto,pastetext,1680,auto,placeholder,1704,auto,preview-rtl,1728,auto,preview,1752,auto,print,1776,auto,removeformat,1800,auto,save,1824,auto,selectall,1848,auto,showblocks-rtl,1872,auto,showblocks,1896,auto,smiley,1920,auto,source-rtl,1944,auto,source,1968,auto,sourcedialog-rtl,1992,auto,sourcedialog,2016,auto,specialchar,2040,auto,table,2064,auto,templates-rtl,2088,auto,templates,2112,auto,uicolor,2136,auto,redo-rtl,2160,auto,redo,2184,auto,undo-rtl,2208,auto,undo,2232,auto,simplebox,2256,auto",
"icons.png")}(),CKEDITOR.lang.languages={en:1})})();
define("ckeditor", (function (global) {
    return function () {
        var ret, fn;
        return ret || global.CKEDITOR;
    };
}(this)));

/*
 Copyright (c) 2003-2016, CKSource - Frederico Knabben. All rights reserved.
 For licensing, see LICENSE.md or http://ckeditor.com/license
*/
(function(a){if("undefined"==typeof a)throw Error("jQuery should be loaded before CKEditor jQuery adapter.");if("undefined"==typeof CKEDITOR)throw Error("CKEditor should be loaded before CKEditor jQuery adapter.");CKEDITOR.config.jqueryOverrideVal="undefined"==typeof CKEDITOR.config.jqueryOverrideVal?!0:CKEDITOR.config.jqueryOverrideVal;a.extend(a.fn,{ckeditorGet:function(){var a=this.eq(0).data("ckeditorInstance");if(!a)throw"CKEditor is not initialized yet, use ckeditor() with a callback.";return a},
ckeditor:function(g,d){if(!CKEDITOR.env.isCompatible)throw Error("The environment is incompatible.");if(!a.isFunction(g)){var m=d;d=g;g=m}var k=[];d=d||{};this.each(function(){var b=a(this),c=b.data("ckeditorInstance"),f=b.data("_ckeditorInstanceLock"),h=this,l=new a.Deferred;k.push(l.promise());if(c&&!f)g&&g.apply(c,[this]),l.resolve();else if(f)c.once("instanceReady",function(){setTimeout(function(){c.element?(c.element.$==h&&g&&g.apply(c,[h]),l.resolve()):setTimeout(arguments.callee,100)},0)},
null,null,9999);else{if(d.autoUpdateElement||"undefined"==typeof d.autoUpdateElement&&CKEDITOR.config.autoUpdateElement)d.autoUpdateElementJquery=!0;d.autoUpdateElement=!1;b.data("_ckeditorInstanceLock",!0);c=a(this).is("textarea")?CKEDITOR.replace(h,d):CKEDITOR.inline(h,d);b.data("ckeditorInstance",c);c.on("instanceReady",function(d){var e=d.editor;setTimeout(function(){if(e.element){d.removeListener();e.on("dataReady",function(){b.trigger("dataReady.ckeditor",[e])});e.on("setData",function(a){b.trigger("setData.ckeditor",
[e,a.data])});e.on("getData",function(a){b.trigger("getData.ckeditor",[e,a.data])},999);e.on("destroy",function(){b.trigger("destroy.ckeditor",[e])});e.on("save",function(){a(h.form).submit();return!1},null,null,20);if(e.config.autoUpdateElementJquery&&b.is("textarea")&&a(h.form).length){var c=function(){b.ckeditor(function(){e.updateElement()})};a(h.form).submit(c);a(h.form).bind("form-pre-serialize",c);b.bind("destroy.ckeditor",function(){a(h.form).unbind("submit",c);a(h.form).unbind("form-pre-serialize",
c)})}e.on("destroy",function(){b.removeData("ckeditorInstance")});b.removeData("_ckeditorInstanceLock");b.trigger("instanceReady.ckeditor",[e]);g&&g.apply(e,[h]);l.resolve()}else setTimeout(arguments.callee,100)},0)},null,null,9999)}});var f=new a.Deferred;this.promise=f.promise();a.when.apply(this,k).then(function(){f.resolve()});this.editor=this.eq(0).data("ckeditorInstance");return this}});CKEDITOR.config.jqueryOverrideVal&&(a.fn.val=CKEDITOR.tools.override(a.fn.val,function(g){return function(d){if(arguments.length){var m=
this,k=[],f=this.each(function(){var b=a(this),c=b.data("ckeditorInstance");if(b.is("textarea")&&c){var f=new a.Deferred;c.setData(d,function(){f.resolve()});k.push(f.promise());return!0}return g.call(b,d)});if(k.length){var b=new a.Deferred;a.when.apply(this,k).done(function(){b.resolveWith(m)});return b.promise()}return f}var f=a(this).eq(0),c=f.data("ckeditorInstance");return f.is("textarea")&&c?c.getData():g.call(f)}}))})(window.jQuery);
define("ckeditor-jquery", ["jquery","ckeditor"], (function (global) {
    return function () {
        var ret, fn;
        return ret || global.$.fn.ckeditor;
    };
}(this)));


define('css/css!../bower_components/codemirror/lib/codemirror',[],function(){});

define('css/css!yui-combo',[],function(){});

define('css/css!../bower_components/At.js/dist/css/jquery.atwho',[],function(){});

define("local-deps", function(){});
