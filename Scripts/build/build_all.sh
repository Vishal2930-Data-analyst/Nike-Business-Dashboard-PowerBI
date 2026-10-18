#!/usr/bin/env bash
# Rebuilds the whole Nike Business Dashboard project from the supplied CSVs.
# Paths below are those of the original build machine - override the variables to rebuild elsewhere.
# Requires: Python 3 (pandas, pillow, playwright, jsonschema, referencing), Node 18+, npm packages lucide-static,
# echarts, @fontsource/inter; github.com/microsoft/json-schemas and github.com/microsoft/powerbi-desktop-samples
# (folder "Report Theme JSON Schema") for validation; CY24SU10.json base theme from any Power BI project.
set -euo pipefail
G=${G:-/home/claude/gen}; SRC=${SRC:-/home/claude/src/Nike_Business_Dashboard_Datasets}
ROOT=${ROOT:-/home/claude/build/Nike_Business_Dashboard_Complete}; PBI=$ROOT/PowerBI; PRE=$ROOT/Dashboard_Preview
BASE_THEME=${BASE_THEME:-"/home/claude/pbi_file_formats/04_pbir/Adventure Works.Report/StaticResources/SharedResources/BaseThemes/CY24SU10.json"}
SCHEMAS=${SCHEMAS:-/home/claude/json-schemas}
THEME_SCHEMA=${THEME_SCHEMA:-"/home/claude/pbids/Report Theme JSON Schema/reportThemeSchema-2.159.json"}
BG=${BG:-/home/claude/assets/bg}
mkdir -p $PBI $PRE/assets
python3 $G/gen_model.py $PBI
python3 $G/check_model.py $PBI/Nike_Business_Dashboard.SemanticModel/model.bim $SRC
python3 $G/gen_theme.py $PBI/Nike_Business_Theme.json
python3 $G/render_bg.py $BG > /dev/null
python3 $G/layout_check.py
python3 $G/gen_report.py $PBI $BG "$BASE_THEME" $PBI/Nike_Business_Theme.json
python3 $G/validate_pbir.py $PBI/Nike_Business_Dashboard.Report $PBI/Nike_Business_Dashboard.SemanticModel/model.bim $SCHEMAS "$THEME_SCHEMA"
python3 $G/gen_docs.py $PBI
python3 $G/export_preview_data.py $SRC $PRE/assets
python3 - "$BG" "$PRE/assets" <<'PY'
import sys
from PIL import Image
from pathlib import Path
for f in sorted(Path(sys.argv[1]).glob('bg_*.png')):
    Image.open(f).convert('RGB').save(Path(sys.argv[2]) / (f.stem + '.webp'), 'WEBP', quality=88, method=6)
PY
node $G/qa/engine_test.js $PRE/assets $G/expected.json | tail -1
python3 $G/make_standalone.py $PRE $PRE/Nike_Dashboard_Preview_Standalone.html
mkdir -p $PBI/Design/backgrounds_png $PBI/Design/backgrounds_html
cp $BG/bg_*.png $PBI/Design/backgrounds_png/ && cp $BG/html/*.html $PBI/Design/backgrounds_html/
mkdir -p $ROOT/Scripts/build $ROOT/Scripts/qa
cp $G/{model_def,gen_model,report_def,gen_report,render_bg,gen_theme,gen_docs,export_preview_data,make_standalone,expected}.py $G/build_all.sh $ROOT/Scripts/build/
cp $G/{check_model,validate_pbir,layout_check}.py $G/qa/engine_test.js $G/qa/ui_test.py $ROOT/Scripts/qa/
echo BUILD OK
