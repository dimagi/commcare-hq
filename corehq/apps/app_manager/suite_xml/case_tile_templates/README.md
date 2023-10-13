# Case Tile Templates

Each template consists of a `name.xml` template file and a `name.json` metadata
file in this directory, and a corresponding attribute on the `CaseTileTemplates`
choices class.

For new templates, I propose following these conventions:

* Name the template after its layout
* Define the template left to right, then top to bottom
* Use "header" as the field name for the main header
* Use "top", "middle", "bottom" to describe vertical positioning
* Use "left", "middle", "right" to describe horizontal positioning
* Vertical positioning should come first, eg "middle-left"
* Use "map" and "map_popup" for hidden fields that allow configuration of maps
  through the "Address" and "Address Popup" formats (see `has_map` below).

The `name.json` metadata file contains the following properties:

* `slug` is the value saved to `Detail.case_tile_template`. "custom" is a reserved value.
* `filename` is a file in this directory containing the detail's XML definition
* `has_map` if the template has hidden fields to support map configurations
* `fields` is a list of strings, which names the fields in the template and is used to populate the "Case Tile Mapping" dropdowns in the case list config
* `grid` is an object used to render an HTML preview of the visible fields of the tile. Keys are the values from `fields` and values are themselves objects with the following keys, which should all match their values for that field's `<grid>` or `<style>` block in the XML:
   * `x`
   * `y`
   * `width`
   * `height`
   * `horz-align`
   * `vert-align`
