# !/usr/bin/env bash

set -euo pipefail

echo "[1/9] Activating virtual environment and running uv sync..."
source .venv/bin/activate
uv sync --group docs

echo "[2/9] Creating resources versions..."
uv run python manage.py resource_static

echo "[3/9] Collecting static files..."
rm -rf staticfiles/
uv run python manage.py collectstatic --noinput -v 0
uv run python manage.py fix_less_imports_collectstatic
uv run python manage.py compilejsi18n

echo "[4/9] Generating Webpack settings..."
uv run python manage.py generate_webpack_settings

echo "[5/9] Building assets with Webpack..."
yarn build || echo "Warning: command failed, continuing"

echo "[6/9] Compressing assets..."
uv run python manage.py compress -f

echo "[7/9] Rendering examples..."
uv run python manage.py export_mkdocs_examples

echo "[8/9] Copying all static assets to docs/static.."
mkdir -p docs/styleguide/static/
rsync -av --delete staticfiles/ docs/styleguide/static/

echo "[9/9] Reinstalling plugin mkdocs_django_assets.."
uv pip install -e mkdocs_django_assets

echo "✅ Build complete! Docs with assets ready in 'docs/styleguide'. Run uv run mkdocs serve --dev-addr=localhost:8001 "
