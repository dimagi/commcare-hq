from mkdocs.plugins import BasePlugin
from pathlib import Path
import re


class DjangoAssetsPlugin(BasePlugin):
    # Regex to match "::: django-component <path>"
    COMPONENT_RE = re.compile(
        r":::\s*django-example-component\s+([^\s]+)\s*:::",
        re.MULTILINE
    )

    def on_post_page(self, output_content, **kwargs):
        """Inject head/body assets and replace django-component placeholders with rendered HTML inside an iframe."""

        print("Running DjangoAssetsPlugin on_post_page...")
        page = kwargs.get("page")  # mkdocs.nav.Page object
        if not page:
            return output_content

        print("Page name / src path:", page.file.src_path)
        file_name = Path(page.file.src_path).name
        print("File name:", file_name)
        print("Page title:", page.title)

        # Determine page name from the markdown file name
        page_name = file_name.replace('.md', '')
        print("Determined page name:", page_name)

        # --- Inject head and body assets for the specific page ---
        page_path = Path(f"docs/styleguide/_includes/bootstrap5/{page_name}.html")
        if page_path.exists():
            head_html = page_path.read_text(encoding="utf-8")
            # Extract head content from the base template
            head_match = re.search(r"<head>(.*?)</head>", head_html, re.DOTALL | re.IGNORECASE)
            head_content = head_match.group(1) if head_match else ""
            # Extract body content from the base template
            body_match = re.search(r"<body>(.*?)</body>", head_html, re.DOTALL | re.IGNORECASE)
            body_content = body_match.group(1) if body_match else ""
        else:
            print(f"Base template not found: {page_path}")
            head_content = ""
            body_content = ""

        # Find all component placeholders in the output_content
        component_re = re.compile(r":::\s*django-example-component\s+([^\s]+)\s*:::", re.MULTILINE)

        def make_iframe_html(component_html: str) -> str:
            """Compose a full HTML doc for the iframe using the existing webpack bundles."""
            doc = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    {head_content}
</head>
<body>
    {component_html}
    {body_content}
</body>
</html>"""
            return doc

        def replace_with_iframe(match):
            rel_path = Path(match.group(1).strip())
            docs_path = Path("docs") / rel_path
            print("Looking for component for iframe:", docs_path)
            if docs_path.exists():
                component_html = docs_path.read_text(encoding="utf-8")
                iframe_doc = make_iframe_html(component_html)
                # Fixed height iframe (500px)
                return (
                    f'<iframe '
                    f'srcdoc="{iframe_doc.replace("\"", "&quot;")}" '
                    f'style="width:100%; height:500px; border:1px solid #ccc; display:block;" '
                    f'loading="lazy"></iframe>'
                )
            print("Missing component for iframe!")
            return match.group(0)

        # Replace all component placeholders with iframes
        new_output = component_re.sub(replace_with_iframe, output_content)

        return new_output


#
# from mkdocs.plugins import BasePlugin
# from pathlib import Path
# import re
#
# class DjangoAssetsPlugin(BasePlugin):
#     # Regex to match "::: django-component <path>"
#     COMPONENT_RE = re.compile(
#         r":::\s*django-component\s+([^\s]+)\s*:::",
#         re.MULTILINE
#     )
#
#     def on_page_markdown(self, markdown, page, **kwargs):
#         """Replace django-component lines with actual demo HTML loaded by the plugin."""
#
#         print("Running DjangoAssetsPlugin.on_page_markdown...")
#         if page:
#             print("Page name / src path:", page.file.src_path)
#             print("Page title:", page.title)
#
#         def replace_component(match):
#             rel_path = Path(match.group(1).strip())
#             docs_path = Path("docs") / rel_path
#             print(f"Looking for component: {docs_path}")
#             if docs_path.exists():
#                 print(" → Found component file.")
#                 demo_html = docs_path.read_text(encoding="utf-8")
#                 return f"""<div class="django-demo-container" data-component-path="{rel_path}">
#                             <div class="django-demo-content">{demo_html}</div>
#                            </div>"""
#             print(" → Missing component file!")
#             return f"<!-- Missing component: {rel_path} -->"
#
#         new_markdown = self.COMPONENT_RE.sub(replace_component, markdown)
#         return new_markdown
#
#     def on_post_page(self, output_content, **kwargs):
#         """Inject head/body assets, CSS reset for demos, and shadow DOM enhancement."""
#
#         print("Running DjangoAssetsPlugin.on_post_page...")
#
#         page = kwargs.get("page")  # mkdocs.nav.Page object
#         if not page:
#             return output_content
#
#         print("Page name / src path:", page.file.src_path)
#         file_name = Path(page.file.src_path).name
#         print("File name:", file_name)
#         print("Page title:", page.title)
#
#         # Determine page name from the markdown file name
#         page_name = file_name.replace('.md', '')
#         print("Determined page name:", page_name)
#
#         # Map page names to their corresponding base HTML files
#         page_mapping = {
#             'selections_mk': 'selections_mk',
#             'tables': 'tables_mk',
#         }
#
#         base_page_name = page_mapping.get(page_name, 'selections_mk')  # Default fallback
#         print(f"Using base page: {base_page_name}")
#
#         # Collect CSS and JS assets from base template
#         demo_assets = self._extract_demo_assets(base_page_name)
#
#         # Inject CSS reset and demo assets in head
#         if demo_assets and "</head>" in output_content:
#             css_reset = self._get_css_reset()
#             head_injection = css_reset + demo_assets.get('head_content', '')
#             output_content = output_content.replace("</head>", head_injection + "\n</head>", 1)
#             print(f" → Injected CSS reset and head assets for {base_page_name}")
#
#         # Inject body assets and shadow DOM enhancer
#         if demo_assets and "</body>" in output_content:
#             body_content = demo_assets.get('body_content', '')
#             # shadow_enhancer = self._get_shadow_enhancer()
#             # body_injection = body_content + shadow_enhancer
#             output_content = output_content.replace("</body>", body_content + "\n</body>", 1)
#             print(f" → Injected body assets and shadow DOM enhancer for {base_page_name}")
#
#         return output_content
#
#     def _extract_demo_assets(self, base_page_name):
#         """Extract CSS and JS assets from base template."""
#         base_page_path = Path(f"docs/styleguide/base/{base_page_name}.html")
#         if not base_page_path.exists():
#             print(f"Base template not found: {base_page_path}")
#             return None
#
#         base_page_html = base_page_path.read_text(encoding="utf-8")
#         assets = {}
#
#         # Extract head content from the base template and mark with source
#         head_match = re.search(r"<head>(.*?)</head>", base_page_html, re.DOTALL | re.IGNORECASE)
#         if head_match:
#             head_content = head_match.group(1)
#             # Mark all link and style elements with data-source for identification
#             head_content = re.sub(
#                 r'<link([^>]*rel="stylesheet"[^>]*)>',
#                 r'<link\1 data-source="django-assets">',
#                 head_content
#             )
#             head_content = re.sub(
#                 r'<style([^>]*)>',
#                 r'<style\1 data-source="django-assets">',
#                 head_content
#             )
#             assets['head_content'] = head_content
#
#         # Extract body content from the base template
#         body_match = re.search(r"<body>(.*?)</body>", base_page_html, re.DOTALL | re.IGNORECASE)
#         if body_match:
#             assets['body_content'] = body_match.group(1)
#
#         return assets
#
#     def _get_css_reset(self):
#         return """
#         <style>
#             .django-demo-container,
#             .django-demo-container * {
#                   all: unset;        /* nukes all author styles */
#                   display: revert;   /* recover normal flow for block/inline elements */
#                   font: revert;      /* recover UA default fonts */
#             }
#         </style>
#         """
