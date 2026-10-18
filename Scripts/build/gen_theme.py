"""Writes Nike_Business_Theme.json (Power BI report theme)."""
import json, sys
from pathlib import Path

theme = {
    "name": "Nike Business Theme",
    "dataColors": ["#171717", "#525252", "#737373", "#A3A3A3", "#D4D4D4", "#22C55E", "#F59E0B", "#E11D48",
                   "#404040", "#9CA3AF", "#6B7280", "#E5E7EB"],
    "background": "#FFFFFF",
    "foreground": "#171717",
    "tableAccent": "#171717",
    "good": "#22C55E",
    "neutral": "#F59E0B",
    "bad": "#E11D48",
    "maximum": "#171717",
    "center": "#A3A3A3",
    "minimum": "#F5F6F8",
    "textClasses": {
        "callout": {"fontSize": 22, "fontFace": "Segoe UI Bold", "color": "#171717"},
        "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": "#171717"},
        "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#171717"},
        "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": "#6B7280"},
        "largeTitle": {"fontSize": 20, "fontFace": "Segoe UI Bold", "color": "#171717"},
        "semiboldLabel": {"fontSize": 10, "fontFace": "Segoe UI Semibold", "color": "#171717"},
        "smallLabel": {"fontSize": 8, "fontFace": "Segoe UI", "color": "#6B7280"}
    },
    "visualStyles": {
        "*": {
            "*": {
                "title": [{"show": True, "fontColor": {"solid": {"color": "#171717"}}, "fontSize": 12,
                           "fontFamily": "Segoe UI Semibold", "alignment": "left"}],
                "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": "#E7E9ED"}}, "radius": 12, "width": 1}],
                "dropShadow": [{"show": False}],
                "padding": [{"top": 8, "bottom": 8, "left": 12, "right": 12}],
                "visualHeader": [{"background": {"solid": {"color": "#FFFFFF"}},
                                  "foreground": {"solid": {"color": "#6B7280"}}, "transparency": 0}],
                "visualTooltip": [{"background": {"solid": {"color": "#FFFFFF"}},
                                   "titleFontColor": {"solid": {"color": "#6B7280"}},
                                   "valueFontColor": {"solid": {"color": "#171717"}}, "fontSize": 9}],
                "categoryAxis": [{"labelColor": {"solid": {"color": "#6B7280"}}, "fontSize": 9, "gridlineShow": False,
                                  "showAxisTitle": False}],
                "valueAxis": [{"labelColor": {"solid": {"color": "#6B7280"}}, "fontSize": 9,
                               "gridlineColor": {"solid": {"color": "#E7E9ED"}}, "gridlineStyle": "dashed",
                               "showAxisTitle": False}],
                "legend": [{"labelColor": {"solid": {"color": "#6B7280"}}, "fontSize": 9, "showTitle": False}],
                "labels": [{"color": {"solid": {"color": "#171717"}}, "fontSize": 9}]
            }
        },
        "page": {
            "*": {
                "background": [{"color": {"solid": {"color": "#F5F6F8"}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": "#F5F6F8"}}}]
            }
        },
        "card": {"*": {"labels": [{"color": {"solid": {"color": "#171717"}}, "fontSize": 20, "fontFamily": "Segoe UI Bold"}],
                       "categoryLabels": [{"color": {"solid": {"color": "#6B7280"}}, "fontSize": 9}]}},
        "tableEx": {"*": {"grid": [{"gridHorizontal": True, "gridHorizontalColor": {"solid": {"color": "#EEF0F3"}},
                                    "gridVertical": False, "rowPadding": 2}],
                          "columnHeaders": [{"fontColor": {"solid": {"color": "#6B7280"}}, "backColor": {"solid": {"color": "#FFFFFF"}},
                                             "fontFamily": "Segoe UI Semibold", "fontSize": 9}],
                          "values": [{"fontColorPrimary": {"solid": {"color": "#171717"}}, "backColorPrimary": {"solid": {"color": "#FFFFFF"}},
                                      "backColorSecondary": {"solid": {"color": "#FFFFFF"}}, "fontSize": 9}]}},
        "slicer": {"*": {"items": [{"fontColor": {"solid": {"color": "#171717"}}, "textSize": 10}],
                         "header": [{"fontColor": {"solid": {"color": "#6B7280"}}, "textSize": 9}]}},
        "lineChart": {"*": {"lineStyles": [{"strokeWidth": 3, "showMarker": True, "markerSize": 4}]}},
        "donutChart": {"*": {"slices": [{"innerRadiusRatio": 66}]}}
    }
}
out = Path(sys.argv[1])
out.write_text(json.dumps(theme, indent=2), encoding='utf-8')
json.loads(out.read_text())
print('theme ok', out)
