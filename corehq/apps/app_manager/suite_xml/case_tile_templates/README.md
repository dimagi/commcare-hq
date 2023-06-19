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
