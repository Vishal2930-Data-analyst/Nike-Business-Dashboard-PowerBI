"""Single source of truth for the Nike semantic model: tables, columns, M queries,
relationships and DAX measures. Consumed by gen_model.py (TMSL), docs and QA."""

CUR0 = r'\$#,0;(\$#,0);\$#,0'
CUR2 = r'\$#,0.00;(\$#,0.00);\$#,0.00'
INT = '#,0'
PCT1 = '0.0%;-0.0%;0.0%'
DEC2 = '#,0.00'
ROASF = '0.00"x"'
DATEF = 'dd mmm yyyy'

DEFAULT_DATA_FOLDER = 'C:\\Nike_Business_Dashboard_Complete\\Data\\'

# ---------------------------------------------------------------- M functions
M_FUNCTIONS = {
    'fnLoadCsv': '''// Loads one CSV from the DataFolder parameter and promotes headers.
(FileName as text) as table =>
let
    Folder = if Text.EndsWith(DataFolder, "\\") then DataFolder else DataFolder & "\\",
    Source = Csv.Document(
        File.Contents(Folder & FileName),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted''',
    'fnCleanText': '''// Trims and removes non-printable characters from the listed text columns.
(InputTable as table, ColumnNames as list) as table =>
let
    Cleaned = Table.TransformColumns(
        InputTable,
        List.Transform(
            ColumnNames,
            (col) => {col, each if _ = null then null else Text.Clean(Text.Trim(_)), type text}
        )
    )
in
    Cleaned''',
    'fnRequireColumns': '''// Fails the refresh with a clear message if an expected source column is missing.
(InputTable as table, ColumnNames as list) as table =>
let
    Missing = List.Difference(ColumnNames, Table.ColumnNames(InputTable)),
    Result = if List.IsEmpty(Missing) then InputTable
             else error Error.Record("Schema check failed", "Missing columns: " & Text.Combine(Missing, ", "))
in
    Result''',
}

# ---------------------------------------------------------------- tables
# column spec: (name, m_type, model_dataType, formatString, summarizeBy, extra)
# m_type None => column is added by a later M step (still typed there)
def C(name, mtype, dtype, fmt=None, summ='none', **extra):
    return dict(name=name, mtype=mtype, dtype=dtype, fmt=fmt, summ=summ, **extra)

TEXT = ('type text', 'string')
DATE = ('type date', 'dateTime')
NUM = ('type number', 'double')
WHOLE = ('Int64.Type', 'int64')
BOOL = ('type logical', 'boolean')

def _t(spec):
    return spec[0], spec[1]

TABLES = []

def table(name, source_file, columns, steps, desc, extra_cols=(), date_table=False, hierarchies=None, calc_cols=()):
    TABLES.append(dict(name=name, file=source_file, columns=columns, steps=steps, desc=desc,
                       extra_cols=list(extra_cols), date_table=date_table,
                       hierarchies=hierarchies or [], calc_cols=list(calc_cols)))

# ---- DimProduct
table('DimProduct', 'Products.csv', [
    C('Product_ID', *TEXT), C('Product_Name', *TEXT), C('Category', *TEXT), C('Subcategory', *TEXT),
    C('Product_Line', *TEXT), C('Gender_Target', *TEXT), C('Color', *TEXT), C('Size_Range', *TEXT),
    C('Unit_Cost', *NUM, fmt=CUR2), C('List_Price', *NUM, fmt=CUR2), C('Launch_Date', *DATE, fmt=DATEF),
    C('Is_Active', *BOOL)],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Product_ID", "Product_Name", "Category", "Subcategory", "Product_Line", "Gender_Target", "Color", "Size_Range"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Product_ID] <> null and [Product_ID] <> "")'),
        ('Added List Margin %', 'Table.AddColumn({prev}, "List_Margin_Pct", each if [List_Price] = null or [List_Price] = 0 then null else ([List_Price] - [Unit_Cost]) / [List_Price], type number)'),
    ],
    extra_cols=[C('List_Margin_Pct', None, 'double', fmt=PCT1)],
    desc='Product dimension (150 rows). Category is the source of truth for product grouping; some synthetic product names do not match their category.')

# ---- DimCustomer
table('DimCustomer', 'Customers.csv', [
    C('Customer_ID', *TEXT), C('Customer_Label', *TEXT), C('Gender', *TEXT), C('Age_Group', *TEXT, sortBy='Age_Group_Sort'),
    C('Registration_Date', *DATE, fmt=DATEF), C('Customer_Segment', *TEXT), C('Country', *TEXT, dataCategory='Country'),
    C('City', *TEXT, dataCategory='City'), C('Loyalty_Tier', *TEXT, sortBy='Loyalty_Tier_Sort')],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Customer_ID", "Customer_Label", "Gender", "Age_Group", "Customer_Segment", "Country", "City", "Loyalty_Tier"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Customer_ID] <> null and [Customer_ID] <> "")'),
        ('Added Age Group Sort', 'Table.AddColumn({prev}, "Age_Group_Sort", each List.PositionOf({{"18-24", "25-34", "35-44", "45-54", "55+"}}, [Age_Group]) + 1, Int64.Type)'),
        ('Added Loyalty Tier Sort', 'Table.AddColumn({prev}, "Loyalty_Tier_Sort", each List.PositionOf({{"Bronze", "Silver", "Gold", "Platinum"}}, [Loyalty_Tier]) + 1, Int64.Type)'),
        ('Added Registration Year', 'Table.AddColumn({prev}, "Registration_Year", each Date.Year([Registration_Date]), Int64.Type)'),
    ],
    extra_cols=[C('Age_Group_Sort', None, 'int64', fmt='0', hidden=True), C('Loyalty_Tier_Sort', None, 'int64', fmt='0', hidden=True),
                C('Registration_Year', None, 'int64', fmt='0')],
    calc_cols=[dict(name='First_Purchase_Date', dtype='dateTime', fmt=DATEF,
                    expr='CALCULATE ( MIN ( FactSales[Transaction_Date] ), FactSales[Order_Status] = "Completed" )',
                    desc='First completed purchase inside the supplied data window (2024). Used by [New Customers].')],
    desc='Customer dimension (6,000 registered customers). Not every customer purchased in 2024 - use [Active Customers] for purchasers.')

# ---- DimStore
table('DimStore', 'Stores.csv', [
    C('Store_ID', *TEXT), C('Store_Name', *TEXT), C('Store_Type', *TEXT), C('City', *TEXT, dataCategory='City'),
    C('Country', *TEXT, dataCategory='Country'), C('Region', *TEXT), C('Opening_Date', *DATE, fmt=DATEF),
    C('Store_Size_SqFt', *WHOLE, fmt=INT)],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Store_ID", "Store_Name", "Store_Type", "City", "Country", "Region"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Store_ID] <> null and [Store_ID] <> "")'),
    ],
    desc='Store dimension (20 stores, 5 regions). Region filters sales and inventory through Store_ID.')

# ---- FactSales
table('FactSales', 'Sales.csv', [
    C('Transaction_ID', *TEXT), C('Transaction_Date', *DATE, fmt=DATEF), C('Product_ID', *TEXT, hidden=True),
    C('Customer_ID', *TEXT), C('Store_ID', *TEXT, hidden=True), C('Sales_Channel', *TEXT),
    C('Units_Sold', *WHOLE, fmt=INT), C('Unit_Selling_Price', *NUM, fmt=CUR2), C('Discount_Amount', *NUM, fmt=CUR2),
    C('Net_Sales', *NUM, fmt=CUR2), C('Unit_Cost', *NUM, fmt=CUR2), C('Cost_of_Goods_Sold', *NUM, fmt=CUR2),
    C('Gross_Profit', *NUM, fmt=CUR2), C('Order_Status', *TEXT), C('Return_Flag', *BOOL)],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Transaction_ID", "Product_ID", "Customer_ID", "Store_ID", "Sales_Channel", "Order_Status"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Transaction_ID] <> null and [Transaction_ID] <> "")'),
        ('Added Is Completed', 'Table.AddColumn({prev}, "Is_Completed", each [Order_Status] = "Completed", type logical)'),
        ('Added Gross Sales', 'Table.AddColumn({prev}, "Gross_Sales_Before_Discount", each [Net_Sales] + [Discount_Amount], type number)'),
    ],
    extra_cols=[C('Is_Completed', None, 'boolean'), C('Gross_Sales_Before_Discount', None, 'double', fmt=CUR2)],
    desc='Sales transaction-line fact (25,000 rows, 2024). Returned/Cancelled rows carry zero units and amounts by design (demo convention) - no further return adjustment is applied.')

# ---- FactMarketing
table('FactMarketing', 'Marketing_Campaigns.csv', [
    C('Campaign_ID', *TEXT), C('Campaign_Name', *TEXT), C('Campaign_Start_Date', *DATE, fmt=DATEF),
    C('Campaign_End_Date', *DATE, fmt=DATEF), C('Marketing_Channel', *TEXT), C('Campaign_Budget', *NUM, fmt=CUR0),
    C('Attributed_Revenue', *NUM, fmt=CUR0), C('Attributed_Orders', *WHOLE, fmt=INT), C('Impressions', *WHOLE, fmt=INT),
    C('Clicks', *WHOLE, fmt=INT), C('Conversions', *WHOLE, fmt=INT), C('ROAS', *NUM, fmt=ROASF, summ='none', model=False)],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Campaign_ID", "Campaign_Name", "Marketing_Channel"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Campaign_ID] <> null and [Campaign_ID] <> "")'),
        ('Added Campaign Days', 'Table.AddColumn({prev}, "Campaign_Days", each Duration.Days([Campaign_End_Date] - [Campaign_Start_Date]) + 1, Int64.Type)'),
        ('Renamed Stored ROAS', 'Table.RenameColumns({prev}, {{{{"ROAS", "Source_ROAS"}}}})'),
    ],
    extra_cols=[C('Campaign_Days', None, 'int64', fmt=INT), C('Source_ROAS', None, 'double', fmt=ROASF)],
    desc='Campaign-level aggregates (10 campaigns). No product/store/transaction keys: never joined to FactSales. Date filtering uses period overlap in DAX.')

# ---- FactInventory
table('FactInventory', 'Inventory.csv', [
    C('Inventory_Date', *DATE, fmt=DATEF), C('Store_ID', *TEXT, hidden=True), C('Product_ID', *TEXT, hidden=True),
    C('Opening_Stock', *WHOLE, fmt=INT), C('Units_Received', *WHOLE, fmt=INT), C('Units_Sold', *WHOLE, fmt=INT),
    C('Units_Returned', *WHOLE, fmt=INT), C('Closing_Stock', *WHOLE, fmt=INT), C('Reorder_Level', *WHOLE, fmt=INT),
    C('Inventory_Status', *TEXT, sortBy='Status_Sort')],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Store_ID", "Product_ID", "Inventory_Status"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Store_ID] <> null and [Product_ID] <> null)'),
        ('Added Status Sort', 'Table.AddColumn({prev}, "Status_Sort", each List.PositionOf({{"In Stock", "Low Stock", "Out of Stock"}}, [Inventory_Status]) + 1, Int64.Type)'),
        ('Added Inventory Key', 'Table.AddColumn({prev}, "Inventory_Key", each [Store_ID] & "|" & [Product_ID], type text)'),
    ],
    extra_cols=[C('Status_Sort', None, 'int64', fmt='0', hidden=True), C('Inventory_Key', None, 'string', hidden=True)],
    desc='Inventory snapshot dated 2024-12-31 at store-product grain (3,000 rows). Never summed across dates; measures always read the latest snapshot.')

# ---- FactSustainability
table('FactSustainability', 'Sustainability.csv', [
    C('Date', *DATE, fmt=DATEF), C('Product_ID', *TEXT, hidden=True),
    C('Recycled_Material_Percentage', *NUM, fmt='0.0'), C('Carbon_Emissions_Kg', *NUM, fmt=DEC2),
    C('Water_Usage_Liters', *NUM, fmt='#,0.0'), C('Sustainable_Units_Sold', *WHOLE, fmt=INT)],
    steps=[
        ('Cleaned Text', 'fnCleanText({prev}, {{"Product_ID"}})'),
        ('Removed Blank Keys', 'Table.SelectRows({prev}, each [Product_ID] <> null and [Product_ID] <> "")'),
        ('Added Quarter Label', 'Table.AddColumn({prev}, "Quarter_Label", each "Q" & Number.ToText(Date.QuarterOfYear([Date])) & " " & Number.ToText(Date.Year([Date])), type text)'),
    ],
    extra_cols=[C('Quarter_Label', None, 'string')],
    desc='Synthetic sustainability metrics at product x quarter grain (600 rows; quarter-end dates). Demonstration data only.')

# ---- DimDate (generated)
DIMDATE_M = '''let
    // Reporting calendar: covers every date used by the fact tables (all 2024).
    StartDate = #date(2024, 1, 1),
    EndDate = #date(2024, 12, 31),
    Dates = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1, 0, 0, 0)),
    AsTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    AddYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
    AddQuarterNo = Table.AddColumn(AddYear, "Quarter Number", each Date.QuarterOfYear([Date]), Int64.Type),
    AddQuarter = Table.AddColumn(AddQuarterNo, "Quarter", each "Q" & Number.ToText([Quarter Number]), type text),
    AddYearQuarter = Table.AddColumn(AddQuarter, "Year-Quarter", each Number.ToText([Year]) & " Q" & Number.ToText([Quarter Number]), type text),
    AddMonthNo = Table.AddColumn(AddYearQuarter, "Month Number", each Date.Month([Date]), Int64.Type),
    AddMonthName = Table.AddColumn(AddMonthNo, "Month Name", each Date.ToText([Date], "MMMM", "en-US"), type text),
    AddMonthShort = Table.AddColumn(AddMonthName, "Month Short", each Date.ToText([Date], "MMM", "en-US"), type text),
    AddYearMonth = Table.AddColumn(AddMonthShort, "Year-Month", each Date.ToText([Date], "yyyy-MM", "en-US"), type text),
    AddMonthYear = Table.AddColumn(AddYearMonth, "Month-Year", each Date.ToText([Date], "MMM yyyy", "en-US"), type text),
    AddSortKey = Table.AddColumn(AddMonthYear, "Month-Year Sort Key", each [Year] * 100 + [Month Number], Int64.Type),
    AddMonthStart = Table.AddColumn(AddSortKey, "Month Start", each Date.StartOfMonth([Date]), type date),
    AddDay = Table.AddColumn(AddMonthStart, "Day", each Date.Day([Date]), Int64.Type),
    AddDowNo = Table.AddColumn(AddDay, "Day of Week Number", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),
    AddDowName = Table.AddColumn(AddDowNo, "Day Name", each Date.ToText([Date], "ddd", "en-US"), type text),
    AddWeek = Table.AddColumn(AddDowName, "Week of Year", each Date.WeekOfYear([Date], Day.Monday), Int64.Type),
    AddWeekend = Table.AddColumn(AddWeek, "Is Weekend", each [Day of Week Number] >= 6, type logical)
in
    AddWeekend'''

DIMDATE_COLS = [
    C('Date', None, 'dateTime', fmt=DATEF), C('Year', None, 'int64', fmt='0'), C('Quarter Number', None, 'int64', fmt='0', hidden=True),
    C('Quarter', None, 'string', sortBy='Quarter Number'), C('Year-Quarter', None, 'string'),
    C('Month Number', None, 'int64', fmt='0', hidden=True), C('Month Name', None, 'string', sortBy='Month Number'),
    C('Month Short', None, 'string', sortBy='Month Number'), C('Year-Month', None, 'string', sortBy='Month-Year Sort Key'),
    C('Month-Year', None, 'string', sortBy='Month-Year Sort Key'), C('Month-Year Sort Key', None, 'int64', fmt='0', hidden=True),
    C('Month Start', None, 'dateTime', fmt=DATEF), C('Day', None, 'int64', fmt='0'),
    C('Day of Week Number', None, 'int64', fmt='0', hidden=True), C('Day Name', None, 'string', sortBy='Day of Week Number'),
    C('Week of Year', None, 'int64', fmt='0'), C('Is Weekend', None, 'boolean')]

TABLES.insert(0, dict(name='DimDate', file=None, columns=DIMDATE_COLS, m=DIMDATE_M, steps=[], extra_cols=[],
                      date_table=True, calc_cols=[],
                      hierarchies=[('Calendar', ['Year', 'Quarter', 'Month Short', 'Date'])],
                      desc='Calendar dimension (1 Jan - 31 Dec 2024), marked as the model Date table.'))

# M type map used for TransformColumnTypes
def m_query(t):
    if t.get('m'):
        return t['m']
    src = [c for c in t['columns'] if c['mtype']]
    names = ', '.join(f'"{c["name"]}"' for c in src)
    types = ', '.join(f'{{"{c["name"]}", {c["mtype"]}}}' for c in src)
    lines = [
        'let',
        f'    // Source: {t["file"]} (synthetic demo data; preserved unchanged on disk)',
        f'    Source = fnLoadCsv("{t["file"]}"),',
        f'    #"Checked Schema" = fnRequireColumns(Source, {{{names}}}),',
        f'    #"Changed Type" = Table.TransformColumnTypes(#"Checked Schema", {{{types}}}, "en-US"),',
    ]
    prev = '#"Changed Type"'
    for i, (step, expr) in enumerate(t['steps']):
        lines.append(f'    #"{step}" = ' + expr.format(prev=prev) + ',')
        prev = f'#"{step}"'
    lines[-1] = lines[-1].rstrip(',')
    lines += ['in', f'    {prev}']
    return '\n'.join(lines)

# ---------------------------------------------------------------- relationships
# (fromTable, fromColumn) many -> (toTable, toColumn) one
RELATIONSHIPS = [
    ('FactSales', 'Transaction_Date', 'DimDate', 'Date', True),
    ('FactSales', 'Product_ID', 'DimProduct', 'Product_ID', True),
    ('FactSales', 'Customer_ID', 'DimCustomer', 'Customer_ID', True),
    ('FactSales', 'Store_ID', 'DimStore', 'Store_ID', True),
    ('FactInventory', 'Product_ID', 'DimProduct', 'Product_ID', True),
    ('FactInventory', 'Store_ID', 'DimStore', 'Store_ID', True),
    ('FactInventory', 'Inventory_Date', 'DimDate', 'Date', False),
    ('FactSustainability', 'Product_ID', 'DimProduct', 'Product_ID', True),
    ('FactSustainability', 'Date', 'DimDate', 'Date', True),
    ('FactMarketing', 'Campaign_Start_Date', 'DimDate', 'Date', False),
]

# ---------------------------------------------------------------- measures
MEASURES = []
def M(folder, name, expr, fmt=None, desc=''):
    MEASURES.append(dict(folder=folder, name=name, expr=expr.strip('\n'), fmt=fmt, desc=desc))

COMPLETED = 'KEEPFILTERS ( FactSales[Order_Status] = "Completed" )'

F = '01 Sales'
M(F, 'Total Net Sales', 'SUM ( FactSales[Net_Sales] )', CUR0, 'Net sales after discounts. Returned/cancelled rows are already zero in the source.')
M(F, 'Total Units Sold', 'SUM ( FactSales[Units_Sold] )', INT)
M(F, 'Total Orders', f'CALCULATE ( DISTINCTCOUNT ( FactSales[Transaction_ID] ), {COMPLETED} )', INT,
  'Completed transaction lines. The dataset has no separate order header, so one Transaction_ID = one order line.')
M(F, 'Total Transactions', 'COUNTROWS ( FactSales )', INT, 'All transaction lines incl. returned and cancelled.')
M(F, 'Returned Transactions', 'CALCULATE ( COUNTROWS ( FactSales ), KEEPFILTERS ( FactSales[Order_Status] = "Returned" ) )', INT)
M(F, 'Cancelled Transactions', 'CALCULATE ( COUNTROWS ( FactSales ), KEEPFILTERS ( FactSales[Order_Status] = "Cancelled" ) )', INT)
M(F, 'Return Rate %', 'DIVIDE ( [Returned Transactions], [Total Transactions] )', PCT1)
M(F, 'Average Order Value', 'DIVIDE ( [Total Net Sales], [Total Orders] )', CUR2)
M(F, 'Average Selling Price', 'DIVIDE ( [Total Net Sales], [Total Units Sold] )', CUR2)
M(F, 'Total Cost of Goods Sold', 'SUM ( FactSales[Cost_of_Goods_Sold] )', CUR0)
M(F, 'Gross Profit', 'SUM ( FactSales[Gross_Profit] )', CUR0, 'Equals Net_Sales - Cost_of_Goods_Sold (validated row by row).')
M(F, 'Gross Profit Margin %', 'DIVIDE ( [Gross Profit], [Total Net Sales] )', PCT1)
M(F, 'Total Discount Amount', 'SUM ( FactSales[Discount_Amount] )', CUR0)
M(F, 'Gross Sales Before Discount', '[Total Net Sales] + [Total Discount Amount]', CUR0)
M(F, 'Discount Rate %', 'DIVIDE ( [Total Discount Amount], [Gross Sales Before Discount] )', PCT1)
M(F, 'Active Customers', f'CALCULATE ( DISTINCTCOUNT ( FactSales[Customer_ID] ), {COMPLETED} )', INT,
  'Distinct customers with at least one completed transaction in the filter context (not the size of DimCustomer).')
M(F, 'Active Stores', f'CALCULATE ( DISTINCTCOUNT ( FactSales[Store_ID] ), {COMPLETED} )', INT)
M(F, 'Sales per Store', 'DIVIDE ( [Total Net Sales], [Active Stores] )', CUR0)
M(F, 'Net Sales % of Total', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], ALLSELECTED () ) )', PCT1,
  'Share of the total visible after slicers/filters (used for region, channel and category shares).')
M(F, 'Units % of Total', 'DIVIDE ( [Total Units Sold], CALCULATE ( [Total Units Sold], ALLSELECTED () ) )', PCT1)
M(F, 'Selected Period Label', '''
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
RETURN
    FORMAT ( _min, "d mmm yyyy" ) & " - " & FORMAT ( _max, "d mmm yyyy" )''')

F = '02 Time Intelligence'
M(F, 'Sales MTD', 'TOTALMTD ( [Total Net Sales], DimDate[Date] )', CUR0)
M(F, 'Sales QTD', 'TOTALQTD ( [Total Net Sales], DimDate[Date] )', CUR0)
M(F, 'Sales YTD', 'TOTALYTD ( [Total Net Sales], DimDate[Date] )', CUR0)
M(F, 'Previous Month Sales', 'CALCULATE ( [Total Net Sales], DATEADD ( DimDate[Date], -1, MONTH ) )', CUR0,
  'Blank for January 2024 because no December 2023 data exists.')
M(F, 'Previous Year Sales', 'CALCULATE ( [Total Net Sales], SAMEPERIODLASTYEAR ( DimDate[Date] ) )', CUR0,
  'Always blank with the supplied data (2024 only). Kept so the model works when 2023 data is added.')
M(F, 'Sales YoY Growth %', '''
VAR _py = [Previous Year Sales]
RETURN
    IF ( ISBLANK ( _py ), BLANK (), DIVIDE ( [Total Net Sales] - _py, _py ) )''', PCT1, 'N/A (blank) until a prior-year dataset exists.')

def prev_period(base, name, fmt):
    M(F, name, f'''
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
VAR _days = DATEDIFF ( _min, _max, DAY ) + 1
VAR _prevEnd = _min - 1
VAR _prevStart = _min - _days
VAR _calendarStart = CALCULATE ( MIN ( DimDate[Date] ), REMOVEFILTERS ( DimDate ) )
RETURN
    IF (
        _prevStart < _calendarStart,
        BLANK (),
        CALCULATE ( {base}, DATESBETWEEN ( DimDate[Date], _prevStart, _prevEnd ) )
    )''', fmt, 'Equal-length period immediately before the selected dates. Blank (N/A) when it falls before the first date in the data.')

prev_period('[Total Net Sales]', 'Previous Period Sales', CUR0)
prev_period('[Total Units Sold]', 'Previous Period Units', INT)
prev_period('[Gross Profit]', 'Previous Period Gross Profit', CUR0)
M(F, 'Sales Growth %', 'DIVIDE ( [Total Net Sales] - [Previous Period Sales], [Previous Period Sales] )', PCT1,
  'Vs the previous equal-length period. Blank for the full year 2024 (no 2023 data).')
M(F, 'Units Sold Growth %', 'DIVIDE ( [Total Units Sold] - [Previous Period Units], [Previous Period Units] )', PCT1)
M(F, 'Gross Profit Growth %', 'DIVIDE ( [Gross Profit] - [Previous Period Gross Profit], [Previous Period Gross Profit] )', PCT1)

F = '03 KPI Comparison (MoM)'
M(F, 'MoM Comparison Label', '''
VAR _ref = MAX ( DimDate[Date] )
RETURN
    FORMAT ( _ref, "mmm" ) & " vs " & FORMAT ( EOMONTH ( _ref, -1 ), "mmm" )''',
  desc='Describes the KPI comparison: last calendar month in the selection vs the month before it.')
MOM = [('Sales', '[Total Net Sales]', CUR0), ('Units', '[Total Units Sold]', INT), ('Customers', '[Active Customers]', INT),
       ('AOV', '[Average Order Value]', CUR2), ('Gross Profit', '[Gross Profit]', CUR0)]
for label, base, fmt in MOM:
    M(F, f'{label} Last Month', f'''
VAR _ref = MAX ( DimDate[Date] )
RETURN
    CALCULATE ( {base}, DATESBETWEEN ( DimDate[Date], DATE ( YEAR ( _ref ), MONTH ( _ref ), 1 ), EOMONTH ( _ref, 0 ) ) )''', fmt,
      'Full calendar month containing the last selected date.')
    M(F, f'{label} Prior Month', f'''
VAR _end = EOMONTH ( MAX ( DimDate[Date] ), -1 )
VAR _start = DATE ( YEAR ( _end ), MONTH ( _end ), 1 )
VAR _calendarStart = CALCULATE ( MIN ( DimDate[Date] ), REMOVEFILTERS ( DimDate ) )
RETURN
    IF ( _start < _calendarStart, BLANK (), CALCULATE ( {base}, DATESBETWEEN ( DimDate[Date], _start, _end ) ) )''', fmt)
    M(F, f'{label} MoM Growth %', f'''
VAR _cur = [{label} Last Month]
VAR _prev = [{label} Prior Month]
RETURN
    IF ( ISBLANK ( _cur ) || ISBLANK ( _prev ), BLANK (), DIVIDE ( _cur - _prev, _prev ) )''', PCT1)
    M(F, f'{label} MoM KPI Text', f'''
VAR _g = [{label} MoM Growth %]
RETURN
    IF (
        ISBLANK ( _g ),
        "N/A (no prior month)",
        IF ( _g >= 0, UNICHAR ( 9650 ) & " ", UNICHAR ( 9660 ) & " " ) & FORMAT ( ABS ( _g ), "0.0%" ) & "  " & [MoM Comparison Label]
    )''', desc='Text shown under the KPI value, e.g. "\u25b2 3.9%  Dec vs Nov 2024".')
    M(F, f'{label} MoM KPI Color', f'''
VAR _g = [{label} MoM Growth %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _g ), "#6B7280", _g >= 0, "#22C55E", "#E11D48" )''')
M(F, 'Gross Margin KPI Text', '''FORMAT ( [Gross Profit Margin %], "0.0%" ) & " gross margin"''')

F = '04 Product'
M(F, 'Product Revenue', '[Total Net Sales]', CUR0)
M(F, 'Product Units Sold', '[Total Units Sold]', INT)
M(F, 'Product Gross Profit', '[Gross Profit]', CUR0)
M(F, 'Product Gross Margin %', '[Gross Profit Margin %]', PCT1)
M(F, 'Products Sold', f'CALCULATE ( DISTINCTCOUNT ( FactSales[Product_ID] ), {COMPLETED} )', INT)
M(F, 'Product Revenue Contribution %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], ALLSELECTED ( DimProduct ) ) )', PCT1)
M(F, 'Product Rank by Revenue', '''
IF (
    HASONEVALUE ( DimProduct[Product_ID] ) && NOT ISBLANK ( [Total Net Sales] ),
    RANKX ( ALLSELECTED ( DimProduct ), [Total Net Sales], , DESC, SKIP )
)''', '0', 'Rank among the products visible after slicers. Iterates whole DimProduct rows so extra columns (e.g. Category) in a table do not distort the rank.')
M(F, 'Top Five Products', 'VAR _r = [Product Rank by Revenue] RETURN IF ( NOT ISBLANK ( _r ) && _r <= 5, 1 )', '0', 'Flag = 1 for the top five products by net sales in the current selection.')
M(F, 'Top5 Product Rank', 'IF ( [Top Five Products] = 1, [Product Rank by Revenue] )', '0')
M(F, 'Top5 Product Net Sales', 'IF ( [Top Five Products] = 1, [Total Net Sales] )', CUR0)
M(F, 'Top5 Product Units', 'IF ( [Top Five Products] = 1, [Total Units Sold] )', INT)
M(F, 'Top5 Product Gross Profit', 'IF ( [Top Five Products] = 1, [Gross Profit] )', CUR0)

F = '05 Customer'
M(F, 'Registered Customers', 'COUNTROWS ( DimCustomer )', INT, 'Rows in the customer dimension (registered, not necessarily purchasing).')
M(F, 'Customer Revenue', '[Total Net Sales]', CUR0)
M(F, 'Revenue per Active Customer', 'DIVIDE ( [Total Net Sales], [Active Customers] )', CUR2)
M(F, 'Avg Orders per Customer', 'DIVIDE ( [Total Orders], [Active Customers] )', '0.00')
M(F, 'New Customers', '''
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
RETURN
    COUNTROWS (
        FILTER (
            DimCustomer,
            NOT ISBLANK ( DimCustomer[First_Purchase_Date] )
                && DimCustomer[First_Purchase_Date] >= _min
                && DimCustomer[First_Purchase_Date] <= _max
        )
    )''', INT, 'Customers whose FIRST completed purchase in the supplied data falls in the selected period. Registration_Date is not used because 1,084 customers register after their first purchase (synthetic data inconsistency).')
M(F, 'Active Customer Share %', 'DIVIDE ( [Active Customers], CALCULATE ( [Active Customers], ALLSELECTED ( DimCustomer ) ) )', PCT1,
  'Share of active (purchasing) customers - used for gender and age-group splits.')
M(F, 'Revenue by Gender %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], ALLSELECTED ( DimCustomer[Gender] ) ) )', PCT1)
M(F, 'Revenue by Age Group %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], ALLSELECTED ( DimCustomer[Age_Group] ) ) )', PCT1)
M(F, 'Revenue by Customer Segment %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], ALLSELECTED ( DimCustomer[Customer_Segment] ) ) )', PCT1)
M(F, 'Loyalty Tier Distribution %', 'DIVIDE ( [Active Customers], CALCULATE ( [Active Customers], ALLSELECTED ( DimCustomer[Loyalty_Tier] ) ) )', PCT1)

F = '06 Store'
M(F, 'Store Net Sales', '[Total Net Sales]', CUR0)
M(F, 'Store Gross Profit', '[Gross Profit]', CUR0)
M(F, 'Store Units Sold', '[Total Units Sold]', INT)
M(F, 'Store Revenue Contribution %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], ALLSELECTED ( DimStore ) ) )', PCT1)
M(F, 'Store Rank by Sales', '''
IF (
    HASONEVALUE ( DimStore[Store_ID] ) && NOT ISBLANK ( [Total Net Sales] ),
    RANKX ( ALLSELECTED ( DimStore ), [Total Net Sales], , DESC, SKIP )
)''', '0')
M(F, 'Store Growth %', '[Sales Growth %]', PCT1, 'Vs previous equal-length period; N/A for full-year 2024 (no prior-year data).')
M(F, 'Store MoM Growth %', '[Sales MoM Growth %]', PCT1)
M(F, 'Sales per Sq Ft', 'DIVIDE ( [Total Net Sales], SUM ( DimStore[Store_Size_SqFt] ) )', CUR2)
M(F, 'Top Five Stores', 'VAR _r = [Store Rank by Sales] RETURN IF ( NOT ISBLANK ( _r ) && _r <= 5, 1 )', '0')
M(F, 'Top5 Store Rank', 'IF ( [Top Five Stores] = 1, [Store Rank by Sales] )', '0')
M(F, 'Top5 Store Net Sales', 'IF ( [Top Five Stores] = 1, [Total Net Sales] )', CUR0)
M(F, 'Top5 Store Units', 'IF ( [Top Five Stores] = 1, [Total Units Sold] )', INT)

F = '07 Marketing'
def mk(name, col, fmt, agg='SUM'):
    M(F, name, f'''
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
RETURN
    CALCULATE (
        {agg} ( FactMarketing[{col}] ),
        FILTER (
            FactMarketing,
            FactMarketing[Campaign_Start_Date] <= _max
                && FactMarketing[Campaign_End_Date] >= _min
        )
    )''', fmt, 'Campaigns whose run overlaps the selected dates. Campaign-level synthetic attribution; NOT reconciled to FactSales and never added to sales revenue.')
mk('Campaign Spend', 'Campaign_Budget', CUR0)
mk('Attributed Revenue', 'Attributed_Revenue', CUR0)
mk('Attributed Orders', 'Attributed_Orders', INT)
mk('Campaign Impressions', 'Impressions', INT)
mk('Campaign Clicks', 'Clicks', INT)
mk('Campaign Conversions', 'Conversions', INT)
mk('Campaign Count', 'Campaign_ID', INT, agg='DISTINCTCOUNT')
M(F, 'ROAS', 'DIVIDE ( [Attributed Revenue], [Campaign Spend] )', ROASF, 'Attributed revenue / campaign budget.')
M(F, 'Click-Through Rate', 'DIVIDE ( [Campaign Clicks], [Campaign Impressions] )', '0.00%')
M(F, 'Conversion Rate', 'DIVIDE ( [Campaign Conversions], [Campaign Clicks] )', '0.00%')
M(F, 'Cost per Acquisition', 'DIVIDE ( [Campaign Spend], [Campaign Conversions] )', CUR2)
M(F, 'Campaign Rank by Attributed Revenue', '''
IF (
    HASONEVALUE ( FactMarketing[Campaign_ID] ) && NOT ISBLANK ( [Attributed Revenue] ),
    RANKX ( ALLSELECTED ( FactMarketing ), [Attributed Revenue], , DESC, SKIP )
)''', '0', 'Ranking rule for the Overview campaign table: attributed revenue, descending.')
M(F, 'Top Five Campaigns', 'VAR _r = [Campaign Rank by Attributed Revenue] RETURN IF ( NOT ISBLANK ( _r ) && _r <= 5, 1 )', '0')
M(F, 'Top5 Campaign Budget', 'IF ( [Top Five Campaigns] = 1, [Campaign Spend] )', CUR0)
M(F, 'Top5 Campaign Attributed Revenue', 'IF ( [Top Five Campaigns] = 1, [Attributed Revenue] )', CUR0)
M(F, 'Top5 Campaign ROAS', 'IF ( [Top Five Campaigns] = 1, [ROAS] )', '0.0"x"')
M(F, 'ROAS Color', '''
VAR _r = [ROAS]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _r ), "#6B7280", _r >= 4.5, "#22C55E", _r >= 3.5, "#171717", "#F59E0B" )''',
  desc='Green >= 4.5x, charcoal 3.5-4.5x, amber < 3.5x.')

F = '08 Inventory'
LATEST = '''VAR _latest = CALCULATE ( MAX ( FactInventory[Inventory_Date] ), REMOVEFILTERS ( FactInventory ) )'''
M(F, 'Latest Snapshot Date', 'CALCULATE ( MAX ( FactInventory[Inventory_Date] ), REMOVEFILTERS ( FactInventory ) )', DATEF)
M(F, 'Current Stock', f'''
{LATEST}
RETURN
    CALCULATE ( SUM ( FactInventory[Closing_Stock] ), FactInventory[Inventory_Date] = _latest )''', INT,
  'Closing stock in the latest snapshot only (never summed across dates). Not affected by the date slicer.')
M(F, 'Inventory Value', f'''
{LATEST}
RETURN
    CALCULATE (
        SUMX ( FactInventory, FactInventory[Closing_Stock] * RELATED ( DimProduct[Unit_Cost] ) ),
        FactInventory[Inventory_Date] = _latest
    )''', CUR0, 'Closing stock valued at product unit cost.')
M(F, 'Stock Value by Store', '[Inventory Value]', CUR0)
M(F, 'Inventory Records', f'''
{LATEST}
RETURN
    CALCULATE ( COUNTROWS ( FactInventory ), FactInventory[Inventory_Date] = _latest )''', INT,
  'Store-product positions in the latest snapshot (grain = Store_ID x Product_ID).')
for st, nm in [('In Stock', 'In-Stock Product Count'), ('Low Stock', 'Low-Stock Product Count'), ('Out of Stock', 'Out-of-Stock Product Count')]:
    M(F, nm, f'CALCULATE ( [Inventory Records], KEEPFILTERS ( FactInventory[Inventory_Status] = "{st}" ) )', INT,
      f'Store-product positions with status "{st}" in the latest snapshot.')
M(F, 'Low-Stock SKUs', f'''
{LATEST}
RETURN
    CALCULATE (
        DISTINCTCOUNT ( FactInventory[Product_ID] ),
        FactInventory[Inventory_Date] = _latest,
        KEEPFILTERS ( FactInventory[Inventory_Status] IN {{ "Low Stock", "Out of Stock" }} )
    )''', INT, 'Distinct products that are low or out of stock in at least one store.')
M(F, 'Inventory Status %', 'DIVIDE ( [Inventory Records], CALCULATE ( [Inventory Records], ALLSELECTED ( FactInventory[Inventory_Status] ) ) )', PCT1)
M(F, 'In Stock %', 'DIVIDE ( [In-Stock Product Count], [Inventory Records] )', '0%')
M(F, 'Exception Stock Units', f'''
{LATEST}
RETURN
    CALCULATE (
        SUM ( FactInventory[Closing_Stock] ),
        FactInventory[Inventory_Date] = _latest,
        KEEPFILTERS ( FactInventory[Inventory_Status] <> "In Stock" )
    )''', INT, 'Closing stock for low/out-of-stock positions only; blank for healthy positions so exception tables hide them.')
M(F, 'Exception Reorder Level', '''
IF ( ISBLANK ( [Exception Stock Units] ), BLANK (), SUM ( FactInventory[Reorder_Level] ) )''', INT)

F = '09 Sustainability'
M(F, 'Average Recycled Material %', 'DIVIDE ( AVERAGE ( FactSustainability[Recycled_Material_Percentage] ), 100 )', PCT1,
  'Simple mean across product-quarter records (synthetic demonstration metric).')
M(F, 'Weighted Recycled Material %', '''
DIVIDE (
    SUMX ( FactSustainability, FactSustainability[Recycled_Material_Percentage] * FactSustainability[Sustainable_Units_Sold] ),
    SUM ( FactSustainability[Sustainable_Units_Sold] )
) / 100''', PCT1, 'Recycled share weighted by sustainable units sold.')
M(F, 'Total Carbon Emissions', 'SUM ( FactSustainability[Carbon_Emissions_Kg] )', '#,0 "kg"')
M(F, 'Total Water Usage', 'SUM ( FactSustainability[Water_Usage_Liters] )', '#,0 "L"')
M(F, 'Sustainable Units Sold', 'SUM ( FactSustainability[Sustainable_Units_Sold] )', INT)
M(F, 'Avg Carbon per Product-Quarter', 'AVERAGE ( FactSustainability[Carbon_Emissions_Kg] )', '#,0.00 "kg"')

F = '10 Formatting'
M(F, 'Profit Color', '''
VAR _m = [Gross Profit Margin %]
VAR _overall = CALCULATE ( [Gross Profit Margin %], ALLSELECTED () )
RETURN
    IF ( _m >= _overall, "#16A34A", "#171717" )''', desc='Green when margin is at/above the selection average.')
M(F, 'Status Color', '''
SWITCH ( SELECTEDVALUE ( FactInventory[Inventory_Status] ), "In Stock", "#22C55E", "Low Stock", "#F59E0B", "Out of Stock", "#E11D48", "#6B7280" )''')
M(F, 'Data Disclaimer', '"Synthetic demonstration data - not official Nike business figures."')

# ---------------------------------------------------------------- KPI sub-line text measures (dynamic tile captions)
F = '11 KPI Captions'
def arrow(g):
    return f'IF ( {g} >= 0, UNICHAR ( 9650 ) & " ", UNICHAR ( 9660 ) & " " )'
M(F, 'Period Growth KPI Text', f'''
VAR _g = [Sales Growth %]
RETURN
    IF ( ISBLANK ( _g ), "N/A vs prev. period (no 2023)", {arrow('_g')} & FORMAT ( ABS ( _g ), "0.0%" ) & " vs previous period" )''')
M(F, 'Period Growth KPI Color', '''
VAR _g = [Sales Growth %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _g ), "#6B7280", _g >= 0, "#22C55E", "#E11D48" )''')
M(F, 'Return Rate KPI Text', 'FORMAT ( [Return Rate %], "0.0%" ) & " of lines returned"')
M(F, 'Discount KPI Text', 'FORMAT ( [Total Discount Amount], "$#,0" ) & " in discounts"')
M(F, 'Orders KPI Text', 'FORMAT ( [Total Transactions], "#,0" ) & " lines incl. returns/cancels"')
M(F, 'Products Sold KPI Text', '"of " & FORMAT ( COUNTROWS ( ALL ( DimProduct ) ), "#,0" ) & " catalogue products"')
M(F, 'Activation KPI Text', 'FORMAT ( DIVIDE ( [Active Customers], [Registered Customers] ), "0.0%" ) & " purchased in period"')
M(F, 'Stores KPI Text', '"of " & FORMAT ( COUNTROWS ( ALL ( DimStore ) ), "#,0" ) & " stores in network"')
M(F, 'Campaign Count KPI Text', 'FORMAT ( [Campaign Count], "0" ) & " campaigns overlap period"')
M(F, 'Attributed Orders KPI Text', 'FORMAT ( [Attributed Orders], "#,0" ) & " attributed orders"')
M(F, 'Clicks KPI Text', 'FORMAT ( [Campaign Clicks], "#,0" ) & " clicks"')
M(F, 'CPA KPI Text', '"CPA " & FORMAT ( [Cost per Acquisition], "$#,0.00" )')
M(F, 'Inventory Positions KPI Text', 'FORMAT ( [In-Stock Product Count], "#,0" ) & " of " & FORMAT ( [Inventory Records], "#,0" ) & " positions"')
M(F, 'Low Stock SKUs KPI Text', 'FORMAT ( [Low-Stock SKUs], "#,0" ) & " products affected"')
M(F, 'Snapshot KPI Text', '"Snapshot " & FORMAT ( [Latest Snapshot Date], "d mmm yyyy" )')
M(F, 'Weighted Recycled KPI Text', '"Weighted: " & FORMAT ( [Weighted Recycled Material %], "0.0%" )')
M(F, 'Period KPI Text', '[Selected Period Label]')
M(F, 'Growth Bar Color', '''
VAR _g = [Sales MoM Growth %]
RETURN
    IF ( ISBLANK ( _g ), "#D4D4D4", IF ( _g >= 0, "#22C55E", "#E11D48" ) )''')
M(F, 'Share of All Products %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], REMOVEFILTERS ( DimProduct ) ) )', PCT1)
M(F, 'Share of All Stores %', 'DIVIDE ( [Total Net Sales], CALCULATE ( [Total Net Sales], REMOVEFILTERS ( DimStore ) ) )', PCT1)
M(F, 'Share KPI Text', '"of all-store sales in period"')
M(F, 'Drill Product Label', '"Product: " & SELECTEDVALUE ( DimProduct[Product_Name], "none - use right-click > Drill through" )')
M(F, 'Drill Store Label', '"Store: " & SELECTEDVALUE ( DimStore[Store_Name], "none - use right-click > Drill through" )')
