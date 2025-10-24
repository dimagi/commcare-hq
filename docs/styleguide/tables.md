# Tables

This page demonstrates various **Table Components** using the enhanced MkDocs Django plugin that reuses the existing styleguide infrastructure.

## Overview

Tables are essential for displaying structured data in CommCare HQ. We use several approaches depending on the complexity and interactivity requirements:

- **Basic Tables** - Simple HTML tables for static data display
- **Sectioned Tables** - Tables with grouped sections for better organization
- **DataTables** - Interactive tables with sorting, searching, and pagination
- **Paginated Tables** - Custom pagination solutions for large datasets

## Basic Table

Simple HTML table for displaying basic tabular data without interactive features.

::: django-example-component styleguide/_includes/examples/bootstrap5/basic_table.html :::

## Sectioned Table

Tables with grouped sections to organize related data together, improving readability and navigation.

::: django-example-component styleguide/_includes/examples/bootstrap5/sectioned_table.html :::

## DataTables

Interactive tables powered by the DataTables jQuery plugin, providing built-in sorting, searching, and pagination capabilities.

::: django-example-component styleguide/_includes/examples/bootstrap5/datatables.html :::

!!! info "DataTables Features"
    DataTables provides many advanced features out of the box:
    - Column sorting
    - Global search
    - Pagination
    - Column filtering
    - Responsive design
    - Export capabilities

## Paginated Table

Custom pagination solution for large datasets that need server-side processing and custom styling.

::: django-example-component styleguide/_includes/examples/bootstrap5/paginated_table.html :::

## Usage Guidelines

### When to Use Each Table Type

- **Basic Table**: Use for simple, static data that doesn't require interaction (< 20 rows)
- **Sectioned Table**: Use when data can be logically grouped into sections
- **DataTables**: Use for medium datasets (20-1000 rows) that need client-side interaction
- **Paginated Table**: Use for large datasets (1000+ rows) requiring server-side processing

### Accessibility Considerations

All table components should:
- Include proper table headers (`<th>` elements)
- Use `scope` attributes for complex tables
- Provide clear column labels
- Support keyboard navigation for interactive elements
- Include ARIA labels for screen readers

### Performance Notes

For optimal performance:
- Use server-side pagination for datasets > 1000 rows
- Implement lazy loading for tables with many columns
- Consider virtual scrolling for very large datasets
- Cache frequently accessed data
