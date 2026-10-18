"""Layout + content specification for every report page (1600 x 900 canvas).
Background elements (bg) are rendered into the page wallpaper PNG; native visuals (vis)
become PBIR visual.json files bound to the semantic model."""
import hashlib

W, H = 1600, 900
X0, MAINW, G = 216, 1368, 16           # main area start, width, gutter
SIDEBAR_W = 200

C_BG, C_CARD, C_SIDE = '#F5F6F8', '#FFFFFF', '#111111'
C_TEXT, C_TEXT2, C_BORDER = '#171717', '#6B7280', '#E7E9ED'
C_POS, C_WARN, C_NEG, C_GRAY = '#22C55E', '#F59E0B', '#E11D48', '#A3A3A3'
SHADES5 = ['#171717', '#404040', '#737373', '#A3A3A3', '#D4D4D4']

def pid(name):
    return hashlib.md5(name.encode()).hexdigest()[:20]

NAV = [  # (label, icon, page key)
    ('Overview', 'house', 'overview'), ('Sales', 'circle-dollar-sign', 'sales'), ('Products', 'shirt', 'products'),
    ('Customers', 'users', 'customers'), ('Stores', 'store', 'stores'), ('Marketing', 'megaphone', 'marketing'),
    ('Inventory', 'warehouse', 'inventory'), ('Sustainability', 'leaf', 'sustainability'), ('Reports', 'file-text', 'reports')]
NAV_Y0, NAV_H, NAV_STEP = 92, 38, 42

# ---------------------------------------------------------------- field helpers
def m(name, label=None):
    return ('_Measures', name, 'M', label)

def c(table, col, label=None):
    return (table, col, 'C', label)

class Page:
    def __init__(self, key, display, title=None, subtitle=None, active_nav=None, hidden=False,
                 drill_field=None, banner=False):
        self.key, self.display, self.title, self.subtitle = key, display, title, subtitle
        self.name = pid(key)
        self.active_nav = active_nav if active_nav is not None else key
        self.hidden, self.drill_field, self.banner = hidden, drill_field, banner
        self.bg, self.vis = [], []

    # ---------- background primitives
    def shell(self, x, y, w, h, title=None, subtitle=None, link=None, link_target=None):
        self.bg.append(dict(t='shell', x=x, y=y, w=w, h=h, title=title, subtitle=subtitle, link=link))
        if link and link_target:
            # transparent navigation button over the "View All" text
            self.vis.append(dict(kind='nav', pos=(x + w - 96, y + 8, 84, 26), target=link_target,
                                 tip=f'Open {link}'))
        return (x, y, w, h)

    def text(self, x, y, text, size=12, weight=400, color=C_TEXT2, w=None, align='left'):
        self.bg.append(dict(t='text', x=x, y=y, text=text, size=size, weight=weight, color=color, w=w, align=align))

    def body(self, sh, top=48, pad=10, bottom=8):
        x, y, w, h = sh
        return (x + pad, y + top, w - 2 * pad, h - top - bottom)

    # ---------- KPI tile
    def kpi(self, x, y, w, h, label, icon, value, units=0, precision=0, sub=None, sub_color=None,
            spark=None, sub_static_color=None):
        self.bg.append(dict(t='kpi', x=x, y=y, w=w, h=h, label=label, icon=icon, spark=bool(spark)))
        right = 84 if spark else 14
        bx, bw = x + 62, w - 62 - right
        self.vis.append(dict(kind='card', pos=(bx, y + 22, bw, h - 50), field=value, units=units, precision=precision,
                             size=19 if h >= 86 else 18, color=C_TEXT, bold=True, name_hint=label))
        if sub:
            sx, sw = (x + 56, w - 142) if spark else (bx - 6, bw + 12)
            self.vis.append(dict(kind='card', pos=(sx, y + h - 28, sw, 20), field=sub, size=8.5,
                                 color=sub_static_color or C_TEXT2, color_measure=sub_color, bold=False,
                                 name_hint=label + ' sub'))
        if spark:
            self.vis.append(dict(kind='spark', pos=(x + w - 82, y + 20, 70, h - 36), field=spark))

    def add(self, **v):
        self.vis.append(v)


def kpi_row(page, y, h, specs):
    n = len(specs)
    w = (MAINW - (n - 1) * G) / n
    for i, s in enumerate(specs):
        page.kpi(X0 + i * (w + G), y, w, h, **s)

def cols(widths):
    xs, x = [], X0
    for w in widths:
        xs.append((x, w))
        x += w + G
    assert abs(x - G - (X0 + MAINW)) < 0.01, (widths, x)
    return xs

DATE_RANGE = c('DimDate', 'Date')
MONTH = c('DimDate', 'Month Short', 'Month')

# ---------------------------------------------------------------- common header (all pages)
def header(p):
    p.bg.append(dict(t='header'))
    p.add(kind='slicer', pos=(252, 14, 340, 36), field=c('DimProduct', 'Product_Name', 'Product'),
          mode='Dropdown', search=True, sync='syncProduct', tip='Search for a product')
    p.add(kind='clear', pos=(1000, 14, 92, 36))
    p.add(kind='slicer', pos=(1130, 13, 220, 38), field=DATE_RANGE, mode='Between', sync='syncDate')
    p.add(kind='slicer', pos=(1394, 14, 118, 36), field=c('DimStore', 'Region'), mode='Dropdown',
          sync='syncRegion', tip='Geography')
    for i, (label, icon, key) in enumerate(NAV):
        p.add(kind='nav', pos=(12, NAV_Y0 + i * NAV_STEP, 176, NAV_H), target=key, tip=f'Go to {label}')

def title_band(p, slicers=()):
    p.text(X0, 64, p.title, size=22, weight=700, color=C_TEXT)
    p.text(X0, 94, p.subtitle, size=12, color=C_TEXT2)
    x = X0 + MAINW
    for label, field in reversed(slicers):
        w = 250
        x -= w
        p.bg.append(dict(t='slicerbox', x=x, y=66, w=w, h=36, label=label))
        p.add(kind='slicer', pos=(x + 92, 66 + 1, w - 96, 34), field=field, mode='Dropdown', search=False,
              tip=f'Filter by {label}', placeholder=label)
        x -= 12

KPI_Y, KPI_H = 118, 82
ROWA_Y, ROWA_H = 212, 330
ROWB_Y, ROWB_H = 554, 334

# ---------------------------------------------------------------- shared visual builders
def line(p, sh, y_fields, tooltips=(), cat=MONTH, colors=None, legend=False, units=1000, top=48, drill=None):
    p.add(kind='line', pos=p.body(sh, top=top), cat=cat, y=y_fields, tooltips=list(tooltips), colors=colors,
          legend=legend, units=units, drill=drill or [])

def bar(p, sh, cat, y, tooltips=(), colors=None, color_measure=None, labels_units=0, top=48, chart='barChart',
        label_fmt=None, legend=False, series_colors=None, labels=True):
    p.add(kind='bar', chart=chart, pos=p.body(sh, top=top), cat=cat, y=y if isinstance(y, list) else [y],
          tooltips=list(tooltips), colors=colors, color_measure=color_measure, units=labels_units, legend=legend,
          series_colors=series_colors, labels=labels)

def donut(p, pos, cat, y, colors, legend=True, tooltips=()):
    p.add(kind='donut', pos=pos, cat=cat, y=y, colors=colors, legend=legend, tooltips=list(tooltips))

def table(p, pos, columns, sort, widths, color_rules=None, totals=False, font=9, sort_dir='Descending', formats=None):
    p.add(kind='table', pos=pos, columns=columns, sort=sort, widths=widths, color_rules=color_rules or {},
          totals=totals, font=font, sort_dir=sort_dir, formats=formats or {})

CAT_COLORS = {'Footwear': '#171717', 'Apparel': '#525252', 'Accessories': '#A3A3A3', 'Equipment': '#D4D4D4'}
REGION_COLORS = dict(zip(['North America', 'Europe', 'Asia Pacific', 'Middle East & Africa', 'Latin America'], SHADES5))
CHANNEL_COLORS = dict(zip(['Retail Stores', 'Online', 'Nike App', 'Wholesale', 'Others'], SHADES5))
STATUS_COLORS = {'In Stock': C_POS, 'Low Stock': C_WARN, 'Out of Stock': C_NEG}
TIER_COLORS = {'Platinum': '#171717', 'Gold': '#525252', 'Silver': '#A3A3A3', 'Bronze': '#D4D4D4'}
STORETYPE_COLORS = {'Flagship': '#171717', 'Retail': '#A3A3A3'}

PAGES = []

# ================================================================ 1. OVERVIEW
p = Page('overview', 'Overview', banner=True)
header(p)
p.bg.append(dict(t='banner', x=X0, y=62, w=MAINW, h=76,
                 title='Nike Business Dashboard',
                 subtitle='Sales performance, product trends and customer insights across global markets.'))
kpi_row(p, 148, 88, [
    dict(label='TOTAL SALES', icon='shopping-bag', value=m('Total Net Sales', 'Total Sales'), units=1000000, precision=2,
         sub=m('Sales MoM KPI Text'), sub_color=m('Sales MoM KPI Color'), spark=m('Total Net Sales')),
    dict(label='UNITS SOLD', icon='package', value=m('Total Units Sold'), units=1, precision=0,
         sub=m('Units MoM KPI Text'), sub_color=m('Units MoM KPI Color'), spark=m('Total Units Sold')),
    dict(label='ACTIVE CUSTOMERS', icon='users', value=m('Active Customers'), units=1, precision=0,
         sub=m('Customers MoM KPI Text'), sub_color=m('Customers MoM KPI Color'), spark=m('Active Customers')),
    dict(label='AVG. ORDER VALUE', icon='shopping-cart', value=m('Average Order Value'), units=1, precision=2,
         sub=m('AOV MoM KPI Text'), sub_color=m('AOV MoM KPI Color'), spark=m('Average Order Value')),
    dict(label='GROSS PROFIT', icon='trending-up', value=m('Gross Profit'), units=1000000, precision=2,
         sub=m('Gross Margin KPI Text'), spark=m('Gross Profit')),
])
(a, aw), (b, bw), (cc, cw) = cols([540, 420, 376])
sh = p.shell(a, 248, aw, 216, 'Sales Trend', 'Monthly net sales  ·  drill up for quarterly  ·  hover for units, profit, MoM')
line(p, sh, [m('Total Net Sales', 'Net Sales')], tooltips=[m('Total Units Sold', 'Units'), m('Gross Profit'),
                                                          m('Sales MoM Growth %', 'MoM growth')],
     drill=[c('DimDate', 'Quarter')])
sh = p.shell(b, 248, bw, 216, 'Sales by Region', 'Share of net sales  ·  store region')
bar(p, sh, c('DimStore', 'Region'), m('Net Sales % of Total', 'Share of net sales'),
    tooltips=[m('Total Net Sales', 'Net Sales'), m('Gross Profit Margin %', 'Gross margin')], colors=REGION_COLORS)
sh = p.shell(cc, 248, cw, 216, 'Top Product Categories', 'Net sales by category')
x, y, w, h = p.body(sh, top=48)
donut(p, (x, y, w, h), c('DimProduct', 'Category'), m('Total Net Sales', 'Net Sales'), CAT_COLORS,
      tooltips=[m('Net Sales % of Total', 'Share')])
p.add(kind='card', pos=(x + w / 2 - 52, y + (h - 26) / 2 - 22, 104, 44), field=m('Total Net Sales', 'Total Sales'),
      units=1000000, precision=2, size=13, color=C_TEXT, bold=True, category=True, name_hint='donut center')

sh = p.shell(a, 476, aw, 206, 'Top Products by Revenue', 'Top 5 by net sales in the current selection', link='View All', link_target='products')
table(p, p.body(sh, top=50), [m('Top5 Product Rank', '#'), c('DimProduct', 'Product_Name', 'Product'),
                              c('DimProduct', 'Category'), m('Top5 Product Net Sales', 'Net Sales'),
                              m('Top5 Product Units', 'Units'), m('Top5 Product Gross Profit', 'Gross Profit')],
      sort=m('Top5 Product Net Sales'), widths=[26, 168, 84, 84, 56, 92],
      color_rules={'Top5 Product Gross Profit': 'Profit Color'})
sh = p.shell(b, 476, bw, 206, 'Sales by Channel', 'Share of net sales')
bar(p, sh, c('FactSales', 'Sales_Channel', 'Channel'), m('Net Sales % of Total', 'Share of net sales'),
    tooltips=[m('Total Net Sales', 'Net Sales'), m('Total Orders', 'Orders')], colors=CHANNEL_COLORS)
sh = p.shell(cc, 476, cw, 206, 'Customer Demographics', 'Share of active (purchasing) customers')
x, y, w, h = p.body(sh, top=48)
p.text(x + 4, y - 2, 'Gender', size=10, weight=600, color=C_TEXT2)
p.text(x + 168, y - 2, 'Age group', size=10, weight=600, color=C_TEXT2)
p.add(kind='bar', chart='barChart', pos=(x, y + 14, 156, h - 14), cat=c('DimCustomer', 'Gender'),
      y=[m('Active Customer Share %', 'Share of active customers')], tooltips=[m('Active Customers'), m('Total Net Sales', 'Net Sales')],
      colors={'Male': '#171717', 'Female': '#525252', 'Prefer not to say': '#A3A3A3', 'Non-binary': '#D4D4D4'},
      color_measure=None, units=0, legend=False, series_colors=None, cat_font=8)
p.add(kind='bar', chart='columnChart', pos=(x + 164, y + 14, w - 164, h - 14), cat=c('DimCustomer', 'Age_Group', 'Age group'),
      y=[m('Active Customer Share %', 'Share of active customers')], tooltips=[m('Active Customers'), m('Total Net Sales', 'Net Sales')],
      colors=None, color_measure=None, units=0, legend=False, series_colors=None, single_color='#171717', cat_font=8)

sh = p.shell(a, 694, aw, 194, 'Store Performance', 'Top 5 stores by net sales  ·  no YoY shown (2024 data only)', link='View All', link_target='stores')
table(p, p.body(sh, top=50), [m('Top5 Store Rank', '#'), c('DimStore', 'Store_Name', 'Store'), c('DimStore', 'City'),
                              c('DimStore', 'Country'), m('Top5 Store Net Sales', 'Net Sales'), m('Top5 Store Units', 'Units')],
      sort=m('Top5 Store Net Sales'), widths=[22, 140, 82, 130, 76, 46])
sh = p.shell(b, 694, bw, 194, 'Marketing Campaign Performance', 'Top 5 by attributed revenue (synthetic attribution)', link='View All', link_target='marketing')
table(p, p.body(sh, top=50), [c('FactMarketing', 'Campaign_Name', 'Campaign'), c('FactMarketing', 'Marketing_Channel', 'Channel'),
                              m('Top5 Campaign Budget', 'Budget'), m('Top5 Campaign Attributed Revenue', 'Attr. revenue'),
                              m('Top5 Campaign ROAS', 'ROAS')],
      sort=m('Top5 Campaign Attributed Revenue'), widths=[114, 84, 56, 66, 44], color_rules={'Top5 Campaign ROAS': 'ROAS Color'},
      formats={'Top5 Campaign Budget': 'K', 'Top5 Campaign Attributed Revenue': 'K'})
sh = p.shell(cc, 694, cw, 194, 'Inventory Status', 'Store-product positions  ·  31 Dec 2024 snapshot')
x, y, w, h = p.body(sh, top=48)
donut(p, (x - 6, y, 140, h), c('FactInventory', 'Inventory_Status', 'Status'), m('Inventory Records', 'Positions'),
      STATUS_COLORS, legend=False, tooltips=[m('Inventory Status %', 'Share'), m('Inventory Value')])
p.add(kind='card', pos=(x + 64 - 40, y + h / 2 - 22, 80, 44), field=m('In Stock %', 'In Stock'), units=1, precision=0,
      size=14, color=C_TEXT, bold=True, category=True, name_hint='inventory center')
table(p, (x + 138, y + 18, w - 138, h - 30), [c('FactInventory', 'Inventory_Status', 'Status'),
                                              m('Inventory Status %', 'Share'), m('Inventory Records', 'Positions')],
      sort=c('FactInventory', 'Inventory_Status'), widths=[88, 50, 64], color_rules={'FactInventory.Inventory_Status': 'Status Color'},
      sort_dir='Ascending')
PAGES.append(p)

# ================================================================ 2. SALES
p = Page('sales', 'Sales', 'Sales Analysis', 'Revenue, profitability and growth across channels and regions  ·  synthetic demo data')
header(p); title_band(p, [('Channel', c('FactSales', 'Sales_Channel', 'Channel'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='NET SALES', icon='circle-dollar-sign', value=m('Total Net Sales'), units=1000000, precision=2,
         sub=m('Sales MoM KPI Text'), sub_color=m('Sales MoM KPI Color')),
    dict(label='GROSS PROFIT', icon='trending-up', value=m('Gross Profit'), units=1000000, precision=2,
         sub=m('Gross Profit MoM KPI Text'), sub_color=m('Gross Profit MoM KPI Color')),
    dict(label='GROSS MARGIN', icon='percent', value=m('Gross Profit Margin %'), units=1, precision=1,
         sub=m('Period Growth KPI Text'), sub_color=m('Period Growth KPI Color')),
    dict(label='COMPLETED ORDERS', icon='receipt', value=m('Total Orders'), units=1, precision=0, sub=m('Return Rate KPI Text')),
    dict(label='DISCOUNT RATE', icon='tag', value=m('Discount Rate %'), units=1, precision=1, sub=m('Discount KPI Text')),
])
(a, aw), (b, bw) = cols([900, 452])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Monthly Net Sales & Gross Profit', 'Calendar 2024 by month')
line(p, sh, [m('Total Net Sales', 'Net Sales'), m('Gross Profit')], tooltips=[m('Total Units Sold', 'Units'), m('Gross Profit Margin %', 'Gross margin')],
     colors={'Total Net Sales': '#171717', 'Gross Profit': '#A3A3A3'}, legend=True, drill=[c('DimDate', 'Quarter')])
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Net Sales by Channel', 'Net sales, with share and margin in tooltip')
bar(p, sh, c('FactSales', 'Sales_Channel', 'Channel'), m('Total Net Sales', 'Net Sales'),
    tooltips=[m('Net Sales % of Total', 'Share'), m('Gross Profit Margin %', 'Gross margin'), m('Total Orders', 'Orders')],
    colors=CHANNEL_COLORS, labels_units=1000)
(a, aw), (b, bw) = cols([660, 692])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'Month-over-Month Sales Growth', 'Each month vs the month before  ·  January has no prior month (N/A)')
bar(p, sh, MONTH, m('Sales MoM Growth %', 'MoM growth'), tooltips=[m('Total Net Sales', 'Net Sales'), m('Previous Month Sales', 'Previous month')],
    color_measure=m('Growth Bar Color'), chart='columnChart')
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Regional Performance', 'Net sales, profitability and orders by store region')
table(p, p.body(sh), [c('DimStore', 'Region'), m('Total Net Sales', 'Net Sales'), m('Net Sales % of Total', 'Share'),
                      m('Gross Profit'), m('Gross Profit Margin %', 'Margin'), m('Total Orders', 'Orders'),
                      m('Average Order Value', 'AOV')],
      sort=m('Total Net Sales'), widths=[140, 92, 60, 92, 62, 64, 66], color_rules={'Gross Profit Margin %': 'Profit Color'}, totals=True, font=10)
PAGES.append(p)

# ================================================================ 3. PRODUCTS
p = Page('products', 'Products', 'Product Performance', 'Category mix, product lines and product ranking  ·  right-click a product to drill through')
header(p); title_band(p, [('Category', c('DimProduct', 'Category'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='PRODUCTS SOLD', icon='package-check', value=m('Products Sold'), units=1, sub=m('Products Sold KPI Text')),
    dict(label='NET SALES', icon='circle-dollar-sign', value=m('Total Net Sales'), units=1000000, precision=2,
         sub=m('Sales MoM KPI Text'), sub_color=m('Sales MoM KPI Color')),
    dict(label='UNITS SOLD', icon='package', value=m('Total Units Sold'), units=1,
         sub=m('Units MoM KPI Text'), sub_color=m('Units MoM KPI Color')),
    dict(label='AVG. SELLING PRICE', icon='tag', value=m('Average Selling Price'), units=1, precision=2),
    dict(label='GROSS MARGIN', icon='percent', value=m('Gross Profit Margin %'), units=1, precision=1),
])
(a, aw), (b, bw), (cc, cw) = cols([420, 440, 476])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Revenue by Category', 'Net sales and share of total')
donut(p, p.body(sh), c('DimProduct', 'Category'), m('Total Net Sales', 'Net Sales'), CAT_COLORS, tooltips=[m('Gross Profit Margin %', 'Gross margin')])
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Net Sales by Product Line', 'Product line, net sales')
bar(p, sh, c('DimProduct', 'Product_Line', 'Product line'), m('Total Net Sales', 'Net Sales'), tooltips=[m('Total Units Sold', 'Units')],
    labels_units=1000, colors=None)
sh = p.shell(cc, ROWA_Y, cw, ROWA_H, 'Gross Margin by Subcategory', 'Gross profit as % of net sales')
bar(p, sh, c('DimProduct', 'Subcategory'), m('Product Gross Margin %', 'Gross margin'), tooltips=[m('Total Net Sales', 'Net Sales')])
sh = p.shell(X0, ROWB_Y, MAINW, ROWB_H, 'Product Ranking', 'All products ranked by net sales in the current selection')
table(p, p.body(sh), [m('Product Rank by Revenue', 'Rank'), c('DimProduct', 'Product_Name', 'Product'), c('DimProduct', 'Category'),
                      c('DimProduct', 'Subcategory'), c('DimProduct', 'Product_Line', 'Product line'), m('Total Net Sales', 'Net Sales'),
                      m('Product Revenue Contribution %', 'Share'), m('Total Units Sold', 'Units'), m('Gross Profit'),
                      m('Product Gross Margin %', 'Margin'), m('Average Selling Price', 'Avg. price')],
      sort=m('Total Net Sales'), widths=[50, 230, 110, 110, 110, 120, 80, 80, 120, 80, 100], color_rules={'Product Gross Margin %': 'Profit Color'}, font=10)
PAGES.append(p)

# ================================================================ 4. CUSTOMERS
p = Page('customers', 'Customers', 'Customer Insights', 'Purchasing customers, demographics, segments and loyalty tiers')
header(p); title_band(p, [('Segment', c('DimCustomer', 'Customer_Segment', 'Segment'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='ACTIVE CUSTOMERS', icon='user-check', value=m('Active Customers'), units=1,
         sub=m('Customers MoM KPI Text'), sub_color=m('Customers MoM KPI Color')),
    dict(label='REGISTERED CUSTOMERS', icon='users', value=m('Registered Customers'), units=1, sub=m('Activation KPI Text')),
    dict(label='NEW CUSTOMERS', icon='user-plus', value=m('New Customers'), units=1),
    dict(label='REVENUE / CUSTOMER', icon='wallet', value=m('Revenue per Active Customer'), units=1, precision=2),
    dict(label='ORDERS / CUSTOMER', icon='repeat', value=m('Avg Orders per Customer'), units=1, precision=2),
])
(a, aw), (b, bw), (cc, cw) = cols([444, 444, 448])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Revenue by Customer Segment', 'Net sales  ·  share in tooltip')
bar(p, sh, c('DimCustomer', 'Customer_Segment', 'Segment'), m('Total Net Sales', 'Net Sales'),
    tooltips=[m('Revenue by Customer Segment %', 'Share'), m('Active Customers')], labels_units=1000)
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Loyalty Tier Distribution', 'Active customers by loyalty tier')
donut(p, p.body(sh), c('DimCustomer', 'Loyalty_Tier', 'Loyalty tier'), m('Active Customers'), TIER_COLORS,
      tooltips=[m('Loyalty Tier Distribution %', 'Share'), m('Total Net Sales', 'Net Sales')])
sh = p.shell(cc, ROWA_Y, cw, ROWA_H, 'Active Customers by Gender', 'Share of active customers')
bar(p, sh, c('DimCustomer', 'Gender'), m('Active Customer Share %', 'Share of active customers'),
    tooltips=[m('Active Customers'), m('Revenue by Gender %', 'Revenue share')])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'Age Group Profile', 'Share of active customers by age group')
bar(p, sh, c('DimCustomer', 'Age_Group', 'Age group'), m('Active Customer Share %', 'Share of active customers'),
    tooltips=[m('Active Customers'), m('Revenue by Age Group %', 'Revenue share')], chart='columnChart')
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Revenue by Customer Country', 'Customer home country (not store country)')
bar(p, sh, c('DimCustomer', 'Country'), m('Total Net Sales', 'Net Sales'), tooltips=[m('Active Customers')], labels_units=1000)
sh = p.shell(cc, ROWB_Y, cw, ROWB_H, 'Segment Summary', 'Segment and loyalty tier map 1:1 in this dataset')
table(p, p.body(sh), [c('DimCustomer', 'Customer_Segment', 'Segment'), c('DimCustomer', 'Loyalty_Tier', 'Tier'),
                      m('Active Customers', 'Customers'), m('Total Net Sales', 'Net Sales'),
                      m('Revenue by Customer Segment %', 'Share'), m('Average Order Value', 'AOV')],
      sort=m('Total Net Sales'), widths=[70, 64, 70, 84, 52, 62], totals=True, font=10)
PAGES.append(p)

# ================================================================ 5. STORES
p = Page('stores', 'Stores', 'Store Performance', 'Store and regional comparison  ·  growth shown month-over-month (no prior-year data)')
header(p); title_band(p, [('Store type', c('DimStore', 'Store_Type', 'Store type'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='ACTIVE STORES', icon='store', value=m('Active Stores'), units=1, sub=m('Stores KPI Text')),
    dict(label='NET SALES', icon='circle-dollar-sign', value=m('Total Net Sales'), units=1000000, precision=2,
         sub=m('Sales MoM KPI Text'), sub_color=m('Sales MoM KPI Color')),
    dict(label='SALES PER STORE', icon='coins', value=m('Sales per Store'), units=1000, precision=1),
    dict(label='UNITS SOLD', icon='package', value=m('Total Units Sold'), units=1),
    dict(label='SALES PER SQ FT', icon='ruler', value=m('Sales per Sq Ft'), units=1, precision=2),
])
(a, aw), (b, bw) = cols([920, 432])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Store Ranking', 'All stores by net sales  ·  right-click a store to drill through')
table(p, p.body(sh), [m('Store Rank by Sales', 'Rank'), c('DimStore', 'Store_Name', 'Store'), c('DimStore', 'Store_Type', 'Type'),
                      c('DimStore', 'City'), c('DimStore', 'Country'), c('DimStore', 'Region'), m('Total Net Sales', 'Net Sales'),
                      m('Store Revenue Contribution %', 'Share'), m('Total Units Sold', 'Units'), m('Store MoM Growth %', 'MoM %')],
      sort=m('Total Net Sales'), widths=[44, 150, 70, 92, 130, 120, 90, 56, 56, 92], font=9)
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Net Sales by Region', 'Store region')
bar(p, sh, c('DimStore', 'Region'), m('Total Net Sales', 'Net Sales'), tooltips=[m('Net Sales % of Total', 'Share'), m('Active Stores')],
    colors=REGION_COLORS, labels_units=1000)
(a, aw), (b, bw), (cc, cw) = cols([660, 320, 356])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'Net Sales by Store', 'All 20 stores')
bar(p, sh, c('DimStore', 'Store_Name', 'Store'), m('Total Net Sales', 'Net Sales'), tooltips=[m('Total Units Sold', 'Units')], labels_units=1000)
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Sales by Store Type', 'Flagship vs retail')
donut(p, p.body(sh), c('DimStore', 'Store_Type', 'Store type'), m('Total Net Sales', 'Net Sales'), STORETYPE_COLORS, tooltips=[m('Active Stores')])
sh = p.shell(cc, ROWB_Y, cw, ROWB_H, 'Sales per Sq Ft by Region', 'Net sales / total store floor area')
bar(p, sh, c('DimStore', 'Region'), m('Sales per Sq Ft'), colors=REGION_COLORS)
PAGES.append(p)

# ================================================================ 6. MARKETING
p = Page('marketing', 'Marketing', 'Marketing Analytics', 'Campaign-level synthetic attribution  ·  not reconciled to sales and never added to sales revenue')
header(p); title_band(p, [('Channel', c('FactMarketing', 'Marketing_Channel', 'Marketing channel'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='CAMPAIGN SPEND', icon='wallet', value=m('Campaign Spend'), units=1000000, precision=2, sub=m('Campaign Count KPI Text')),
    dict(label='ATTRIBUTED REVENUE', icon='circle-dollar-sign', value=m('Attributed Revenue'), units=1000000, precision=2,
         sub=m('Attributed Orders KPI Text')),
    dict(label='ROAS', icon='target', value=m('ROAS'), units=1, precision=2),
    dict(label='CLICK-THROUGH RATE', icon='mouse-pointer-click', value=m('Click-Through Rate'), units=1, precision=2, sub=m('Clicks KPI Text')),
    dict(label='CONVERSION RATE', icon='badge-percent', value=m('Conversion Rate'), units=1, precision=2, sub=m('CPA KPI Text')),
])
sh = p.shell(X0, ROWA_Y, MAINW, ROWA_H, 'Campaign Performance', 'Campaigns whose run overlaps the selected dates  ·  sorted by attributed revenue')
table(p, p.body(sh), [c('FactMarketing', 'Campaign_Name', 'Campaign'), c('FactMarketing', 'Marketing_Channel', 'Channel'),
                      c('FactMarketing', 'Campaign_Start_Date', 'Start'), c('FactMarketing', 'Campaign_End_Date', 'End'),
                      m('Campaign Spend', 'Budget'), m('Attributed Revenue', 'Attributed revenue'), m('ROAS'),
                      m('Attributed Orders', 'Attr. orders'), m('Click-Through Rate', 'CTR'), m('Conversion Rate', 'Conv. rate'),
                      m('Cost per Acquisition', 'CPA')],
      sort=m('Attributed Revenue'), widths=[170, 120, 100, 100, 110, 140, 70, 100, 80, 90, 90], color_rules={'ROAS': 'ROAS Color'}, totals=True, font=10)
(a, aw), (b, bw) = cols([660, 692])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'ROAS by Campaign', 'Green >= 4.5x  ·  charcoal 3.5-4.5x  ·  amber < 3.5x')
bar(p, sh, c('FactMarketing', 'Campaign_Name', 'Campaign'), m('ROAS'), tooltips=[m('Campaign Spend', 'Budget'), m('Attributed Revenue')],
    color_measure=m('ROAS Color'))
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Spend vs Attributed Revenue by Channel', 'Campaign budget and attributed revenue')
bar(p, sh, c('FactMarketing', 'Marketing_Channel', 'Marketing channel'), [m('Campaign Spend', 'Budget'), m('Attributed Revenue')],
    tooltips=[m('ROAS')], chart='clusteredBarChart', labels_units=1000, legend=True,
    series_colors={'Campaign Spend': '#A3A3A3', 'Attributed Revenue': '#171717'})
PAGES.append(p)

# ================================================================ 7. INVENTORY
p = Page('inventory', 'Inventory', 'Inventory Management', 'Snapshot as of 31 Dec 2024 (store x product)  ·  not affected by the date slicer')
header(p); title_band(p, [('Category', c('DimProduct', 'Category')), ('Status', c('FactInventory', 'Inventory_Status', 'Status'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='CURRENT STOCK (UNITS)', icon='boxes', value=m('Current Stock'), units=1, sub=m('Snapshot KPI Text')),
    dict(label='INVENTORY VALUE', icon='coins', value=m('Inventory Value'), units=1000000, precision=2),
    dict(label='IN-STOCK RATE', icon='package-check', value=m('In Stock %'), units=1, precision=1, sub=m('Inventory Positions KPI Text')),
    dict(label='LOW-STOCK POSITIONS', icon='triangle-alert', value=m('Low-Stock Product Count'), units=1, sub=m('Low Stock SKUs KPI Text')),
    dict(label='OUT-OF-STOCK POSITIONS', icon='package-x', value=m('Out-of-Stock Product Count'), units=1),
])
(a, aw), (b, bw) = cols([420, 932])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Stock Status', 'Share of store-product positions')
donut(p, p.body(sh), c('FactInventory', 'Inventory_Status', 'Status'), m('Inventory Records', 'Positions'), STATUS_COLORS,
      tooltips=[m('Inventory Status %', 'Share'), m('Inventory Value')])
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Inventory Value by Store', 'Closing stock valued at unit cost')
bar(p, sh, c('DimStore', 'Store_Name', 'Store'), m('Inventory Value'), tooltips=[m('Current Stock'), m('Low-Stock Product Count', 'Low-stock positions')],
    labels_units=1000, chart='columnChart', labels=False)
(a, aw), (b, bw) = cols([900, 452])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'Low & Out-of-Stock Positions', 'Exceptions only  ·  closing stock at or below reorder level')
table(p, p.body(sh), [c('DimStore', 'Store_Name', 'Store'), c('DimProduct', 'Product_Name', 'Product'), c('DimProduct', 'Category'),
                      c('FactInventory', 'Inventory_Status', 'Status'), m('Exception Stock Units', 'Closing stock'),
                      m('Exception Reorder Level', 'Reorder level')],
      sort=m('Exception Stock Units'), widths=[170, 220, 120, 110, 110, 110], color_rules={'FactInventory.Inventory_Status': 'Status Color'},
      sort_dir='Ascending', font=10)
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Stock Value by Category', 'Inventory value at unit cost')
bar(p, sh, c('DimProduct', 'Category'), m('Inventory Value'), tooltips=[m('Current Stock')], colors=CAT_COLORS, labels_units=1000)
PAGES.append(p)

# ================================================================ 8. SUSTAINABILITY
p = Page('sustainability', 'Sustainability', 'Sustainability', 'Synthetic demonstration metrics  ·  product x quarter records (quarter-end dates)')
header(p); title_band(p, [('Category', c('DimProduct', 'Category'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='AVG. RECYCLED MATERIAL', icon='recycle', value=m('Average Recycled Material %'), units=1, precision=1,
         sub=m('Weighted Recycled KPI Text')),
    dict(label='CARBON EMISSIONS', icon='factory', value=m('Total Carbon Emissions'), units=1000, precision=1),
    dict(label='WATER USAGE', icon='droplets', value=m('Total Water Usage'), units=1000, precision=1),
    dict(label='SUSTAINABLE UNITS SOLD', icon='sprout', value=m('Sustainable Units Sold'), units=1000000, precision=2),
    dict(label='AVG. CARBON / RECORD', icon='cloud', value=m('Avg Carbon per Product-Quarter'), units=1, precision=2),
])
(a, aw), (b, bw) = cols([660, 692])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Sustainable Units Sold by Quarter', 'Quarterly product records')
bar(p, sh, c('DimDate', 'Quarter'), m('Sustainable Units Sold'), tooltips=[m('Total Carbon Emissions'), m('Total Water Usage')],
    chart='columnChart', labels_units=1000)
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Recycled Material by Quarter', 'Simple vs units-weighted average')
line(p, sh, [m('Average Recycled Material %', 'Average'), m('Weighted Recycled Material %', 'Weighted')], cat=c('DimDate', 'Quarter'),
     colors={'Average Recycled Material %': '#171717', 'Weighted Recycled Material %': '#22C55E'}, legend=True, units=0)
(a, aw), (b, bw), (cc, cw) = cols([420, 460, 456])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'Recycled Material by Category', 'Average recycled material %')
bar(p, sh, c('DimProduct', 'Category'), m('Average Recycled Material %', 'Avg. recycled'), colors=CAT_COLORS)
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Product Line Footprint', 'Totals across product-quarter records')
table(p, p.body(sh), [c('DimProduct', 'Product_Line', 'Product line'), m('Sustainable Units Sold', 'Units'),
                      m('Average Recycled Material %', 'Recycled'), m('Total Carbon Emissions', 'Carbon'), m('Total Water Usage', 'Water')],
      sort=m('Sustainable Units Sold'), widths=[100, 84, 70, 82, 90], totals=True, font=10)
sh = p.shell(cc, ROWB_Y, cw, ROWB_H, 'Top Products by Sustainable Units', 'All quarters in selection')
table(p, p.body(sh), [c('DimProduct', 'Product_Name', 'Product'), c('DimProduct', 'Category'), m('Sustainable Units Sold', 'Units'),
                      m('Average Recycled Material %', 'Recycled')],
      sort=m('Sustainable Units Sold'), widths=[170, 86, 80, 76], font=10)
PAGES.append(p)

# ================================================================ 9. REPORTS
p = Page('reports', 'Reports', 'Reports', 'KPI summary and transaction-level detail  ·  use the filters to build an extract')
header(p); title_band(p, [('Category', c('DimProduct', 'Category')), ('Channel', c('FactSales', 'Sales_Channel', 'Channel'))])
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='NET SALES', icon='circle-dollar-sign', value=m('Total Net Sales'), units=1000000, precision=2, sub=m('Period KPI Text')),
    dict(label='COMPLETED ORDERS', icon='receipt', value=m('Total Orders'), units=1, sub=m('Orders KPI Text')),
    dict(label='ACTIVE CUSTOMERS', icon='users', value=m('Active Customers'), units=1),
    dict(label='AVG. ORDER VALUE', icon='shopping-cart', value=m('Average Order Value'), units=1, precision=2),
    dict(label='GROSS MARGIN', icon='percent', value=m('Gross Profit Margin %'), units=1, precision=1),
])
sh = p.shell(X0, ROWA_Y, MAINW, ROWA_H, 'Monthly KPI Summary', 'All core KPIs by month  ·  totals row = selection')
table(p, p.body(sh), [c('DimDate', 'Month-Year', 'Month'), m('Total Net Sales', 'Net Sales'), m('Total Units Sold', 'Units'),
                      m('Total Orders', 'Orders'), m('Average Order Value', 'AOV'), m('Gross Profit'), m('Gross Profit Margin %', 'Margin'),
                      m('Active Customers', 'Active customers'), m('Discount Rate %', 'Discount rate'), m('Return Rate %', 'Return rate')],
      sort=c('DimDate', 'Month-Year'), widths=[130, 150, 110, 110, 110, 150, 100, 140, 120, 120], totals=True, font=10, sort_dir='Ascending')
sh = p.shell(X0, ROWB_Y, MAINW, ROWB_H, 'Transaction Detail', 'One row per transaction line (25,000 rows)  ·  returned/cancelled lines show zero by design')
table(p, p.body(sh), [c('FactSales', 'Transaction_ID', 'Transaction'), c('FactSales', 'Transaction_Date', 'Date'),
                      c('DimProduct', 'Product_Name', 'Product'), c('DimProduct', 'Category'), c('DimStore', 'Store_Name', 'Store'),
                      c('DimStore', 'Region'), c('FactSales', 'Sales_Channel', 'Channel'), c('FactSales', 'Order_Status', 'Status'),
                      m('Total Units Sold', 'Units'), m('Total Net Sales', 'Net Sales'), m('Gross Profit')],
      sort=c('FactSales', 'Transaction_ID'), widths=[100, 100, 210, 100, 170, 140, 110, 90, 70, 110, 110], font=9, sort_dir='Ascending')
PAGES.append(p)

# ================================================================ 10. PRODUCT DETAILS (drill-through, hidden)
p = Page('product_details', 'Product Details', 'Product Details', 'Drill-through page  ·  right-click a product anywhere and choose Drill through > Product Details',
         active_nav='products', hidden=True, drill_field=c('DimProduct', 'Product_Name'))
header(p); title_band(p)
p.add(kind='back', pos=(X0 + MAINW - 120, 66, 120, 36))
p.bg.append(dict(t='pill', x=X0 + MAINW - 120, y=66, w=120, h=36, text='Back', icon='arrow-left'))
p.bg.append(dict(t='slicerbox', x=X0 + MAINW - 640, y=66, w=504, h=36, label=''))
p.add(kind='card', pos=(X0 + MAINW - 636, 67, 496, 34), field=m('Drill Product Label'), size=11, color=C_TEXT, bold=True, name_hint='drill label')
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='NET SALES', icon='circle-dollar-sign', value=m('Total Net Sales'), units=1000, precision=1, sub=m('Sales MoM KPI Text'), sub_color=m('Sales MoM KPI Color')),
    dict(label='UNITS SOLD', icon='package', value=m('Total Units Sold'), units=1),
    dict(label='GROSS MARGIN', icon='percent', value=m('Gross Profit Margin %'), units=1, precision=1),
    dict(label='SHARE OF ALL PRODUCTS', icon='layers', value=m('Share of All Products %'), units=1, precision=2),
    dict(label='CURRENT STOCK', icon='boxes', value=m('Current Stock'), units=1, sub=m('Snapshot KPI Text')),
])
(a, aw), (b, bw) = cols([900, 452])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Monthly Net Sales', 'Selected product')
line(p, sh, [m('Total Net Sales', 'Net Sales')], tooltips=[m('Total Units Sold', 'Units')], units=1000)
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Net Sales by Channel', 'Selected product')
bar(p, sh, c('FactSales', 'Sales_Channel', 'Channel'), m('Total Net Sales', 'Net Sales'), colors=CHANNEL_COLORS)
sh = p.shell(X0, ROWB_Y, MAINW, ROWB_H, 'Store Breakdown', 'Sales and current stock by store for the selected product')
table(p, p.body(sh), [c('DimStore', 'Store_Name', 'Store'), c('DimStore', 'Region'), m('Total Net Sales', 'Net Sales'),
                      m('Total Units Sold', 'Units'), m('Gross Profit'), m('Current Stock', 'Current stock')],
      sort=m('Total Net Sales'), widths=[300, 220, 200, 180, 200, 180], totals=True, font=10)
PAGES.append(p)

# ================================================================ 11. STORE DETAILS (drill-through, hidden)
p = Page('store_details', 'Store Details', 'Store Details', 'Drill-through page  ·  right-click a store anywhere and choose Drill through > Store Details',
         active_nav='stores', hidden=True, drill_field=c('DimStore', 'Store_Name'))
header(p); title_band(p)
p.add(kind='back', pos=(X0 + MAINW - 120, 66, 120, 36))
p.bg.append(dict(t='pill', x=X0 + MAINW - 120, y=66, w=120, h=36, text='Back', icon='arrow-left'))
p.bg.append(dict(t='slicerbox', x=X0 + MAINW - 640, y=66, w=504, h=36, label=''))
p.add(kind='card', pos=(X0 + MAINW - 636, 67, 496, 34), field=m('Drill Store Label'), size=11, color=C_TEXT, bold=True, name_hint='drill label')
kpi_row(p, KPI_Y, KPI_H, [
    dict(label='NET SALES', icon='circle-dollar-sign', value=m('Total Net Sales'), units=1000, precision=1, sub=m('Sales MoM KPI Text'), sub_color=m('Sales MoM KPI Color')),
    dict(label='COMPLETED ORDERS', icon='receipt', value=m('Total Orders'), units=1),
    dict(label='ACTIVE CUSTOMERS', icon='users', value=m('Active Customers'), units=1),
    dict(label='SHARE OF ALL STORES', icon='layers', value=m('Share of All Stores %'), units=1, precision=2),
    dict(label='INVENTORY VALUE', icon='coins', value=m('Inventory Value'), units=1000, precision=1, sub=m('Snapshot KPI Text')),
])
(a, aw), (b, bw) = cols([900, 452])
sh = p.shell(a, ROWA_Y, aw, ROWA_H, 'Monthly Net Sales', 'Selected store')
line(p, sh, [m('Total Net Sales', 'Net Sales')], tooltips=[m('Total Orders', 'Orders')], units=1000)
sh = p.shell(b, ROWA_Y, bw, ROWA_H, 'Category Mix', 'Selected store')
donut(p, p.body(sh), c('DimProduct', 'Category'), m('Total Net Sales', 'Net Sales'), CAT_COLORS)
(a, aw), (b, bw) = cols([900, 452])
sh = p.shell(a, ROWB_Y, aw, ROWB_H, 'Top Products in Store', 'Ranked by net sales')
table(p, p.body(sh), [c('DimProduct', 'Product_Name', 'Product'), c('DimProduct', 'Category'), m('Total Net Sales', 'Net Sales'),
                      m('Total Units Sold', 'Units'), m('Gross Profit'), m('Gross Profit Margin %', 'Margin')],
      sort=m('Total Net Sales'), widths=[260, 120, 140, 100, 140, 100], font=10)
sh = p.shell(b, ROWB_Y, bw, ROWB_H, 'Net Sales by Channel', 'Selected store')
bar(p, sh, c('FactSales', 'Sales_Channel', 'Channel'), m('Total Net Sales', 'Net Sales'), colors=CHANNEL_COLORS)
PAGES.append(p)

PAGE_BY_KEY = {pg.key: pg for pg in PAGES}
