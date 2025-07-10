import dash
from dash import dcc, html, dash_table, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
import base64
import datetime
import re
from dateutil.parser import parse as date_parser
from sklearn.metrics import mean_absolute_error, mean_squared_error
import os
import subprocess
import uuid

# --- Helper Functions ---
def get_filter_choices(data_series, default_all_text, placeholder_value="N/A"):
    choices = [{'label': default_all_text, 'value': 'All'}]
    if data_series is None or data_series.empty:
        return choices
    unique_values = data_series.astype(str).unique()
    valid_values = [
        val for val in unique_values
        if pd.notna(val) and val != placeholder_value and str(val).strip() != "" and str(val).lower() != 'nan'
    ]
    if valid_values:
        choices.extend([{'label': val, 'value': val} for val in sorted(valid_values)])
    return choices

def get_original_col_name_by_keyword(original_names_list, normalized_names_list, concept_keywords_list):
    if not original_names_list or not normalized_names_list: return None
    for keyword in concept_keywords_list:
        for i, norm_name in enumerate(normalized_names_list):
            if re.search(keyword, norm_name, re.IGNORECASE): return original_names_list[i]
    return None

# --- Main Application ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
server = app.server

# --- UI Layout ---
# Corrected style for dropdowns
dropdown_style = {'color': '#333'}

sidebar_upload_view_controls = html.Div([
    html.Hr(className="text-white"),
    html.H4("1. Upload Sales Data", style={"padding-top": "10px"}),
    dcc.Upload(id='upload-data', children=html.Div(['Drag and Drop or ', html.A('Select Files')]), style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0', 'background-color': '#f0f0f0', 'color': '#333'}, multiple=True, accept=".xlsx,.xls,.csv"),
    html.Div(id='file-info', style={"fontSize": "0.9em", "fontStyle": "italic", "color": "#eee"}),
    html.P("Ensure your files have 'Date', 'Sales', and optionally 'Sales Organization', 'Material Group', 'Distribution Channel', 'Material'.", style={"fontSize": "0.9em", "padding": "0 5px", "color": "#ddd"}),
    html.Div(id="filter-controls-container", children=[
        html.Hr(className="text-white"),
        html.H4("2. Filter Data", style={"padding-top": "10px"}),
        dcc.Dropdown(id='filter-sales-org', placeholder="Filter by Sales Organization", className="mb-2", style=dropdown_style),
        dcc.Dropdown(id='filter-matrl-group', placeholder="Filter by Material Group", className="mb-2", style=dropdown_style),
        dcc.Dropdown(id='filter-dist-channel', placeholder="Filter by Distribution Channel", className="mb-2", style=dropdown_style),
        dcc.Dropdown(id='filter-material', placeholder="Filter by Material", className="mb-2", style=dropdown_style),
    ], style={'display': 'none'}),
    # Corrected Footer
    html.Div([html.P(text, style={'margin': '0'}) for text in ["© 2025 IOCL Sales Forecaster.", "Powered by Python Dash."]],
             className="footer text-white",
             style={'textAlign': 'center', 'marginTop': '40px', 'paddingBottom': '20px', 'fontSize': '0.8em'})
])

sidebar_forecast_controls = html.Div([
    html.Hr(className="text-white"),
    html.H4("1. Upload Sales Data (if not done)", style={"padding-top": "10px"}),
    dcc.Upload(id='upload-data-forecast-tab', children=html.Div(['Drag and Drop or ', html.A('Select Files')]), style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0', 'background-color': '#f0f0f0', 'color': '#333'}, multiple=True, accept=".xlsx,.xls,.csv"),
    html.Div(id='file-info-forecast-tab', style={"fontSize": "0.9em", "fontStyle": "italic", "color": "#eee"}),
    html.P("Ensure your files have 'Date', 'Sales', and optionally 'Sales Organization', 'Material Group', 'Distribution Channel', 'Material'.", style={"fontSize": "0.9em", "padding": "0 5px", "color": "#ddd"}),
    html.Div(id="forecast-params-container", children=[
        html.Hr(className="text-white"),
        html.H4("4. Forecasting Controls", style={"padding-top": "10px"}),
        dbc.Label("Forecast Periods (Months):"),
        dbc.Input(id='forecast-periods', type='number', value=12, min=1, max=60, step=1, className="mb-2"),
        dbc.Button("Generate Forecast", id='generate-forecast-btn', color="success", className="w-100 mt-2"),
        html.Hr(className="text-white mt-4"),
        html.H4("6. Measure Accuracy (Optional)", style={"padding-top": "10px"}),
        dcc.Upload(id='upload-actuals-accuracy', children=html.Div(['Upload Future Actuals ', html.A('Select File')]), style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0', 'background-color': '#f0f0f0', 'color': '#333'}, multiple=False, accept=".xlsx,.xls,.csv"),
        html.Div(id='file-info-accuracy', style={"fontSize": "0.9em", "fontStyle": "italic", "color": "#eee"}),
        dbc.Button("Calculate Accuracy", id='calculate-accuracy-btn', color="info", className="w-100 mt-2", disabled=True)
    ], style={'display': 'none'}),
    # Corrected Footer
    html.Div([html.P(text, style={'margin':'0'}) for text in ["© 2025 IOCL Sales Forecaster.", "Powered by Python Dash."]],
             className="footer text-white",
             style={'textAlign': 'center', 'marginTop': '40px', 'paddingBottom': '20px', 'fontSize': '0.8em'})
])

tab_style = {
    'borderBottom': '1px solid #005382', 'padding': '8px', 'color': '#b0bec5',
    'backgroundColor': '#00629b', 'borderLeft': '1px solid #005382',
    'borderRight': '1px solid #005382',
}
selected_tab_style = {
    'borderTop': '2px solid white', 'borderBottom': '1px solid #0073b7',
    'borderLeft': '1px solid #005382', 'borderRight': '1px solid #005382',
    'backgroundColor': '#0073b7', 'color': 'white', 'padding': '8px', 'fontWeight': 'bold'
}
sidebar = dbc.Col([
    html.H2("IOCL Sales Forecaster", className="text-white", style={"fontSize":"1.5rem"}),
    html.Hr(className="text-white"),
    dcc.Tabs(id="tabs", value='tab-upload-view', vertical=False, children=[
        dcc.Tab(label='1. Upload & View Data', value='tab-upload-view', style=tab_style, selected_style=selected_tab_style),
        dcc.Tab(label='2. Forecast Sales', value='tab-forecast-sales', style=tab_style, selected_style=selected_tab_style),
    ]),
    html.Div(id="sidebar-tab1-controls-wrapper", children=sidebar_upload_view_controls, style={'display': 'block'}),
    html.Div(id="sidebar-tab2-controls-wrapper", children=sidebar_forecast_controls, style={'display': 'none'}),
], width=12, md=3, style={"background-color": "#0073b7", "padding": "20px", "height": "100vh", "color":"white", "position": "relative", "overflow-y": "auto"})

content = dbc.Col(html.Div(id='page-content'), width=12, md=9, style={"padding": "20px", "backgroundColor": "#ecf0f5", "height": "100vh", "overflowY": "auto"})

app.layout = dbc.Container([
    dbc.Row([sidebar, content], className="g-0"),
    dcc.Store(id='store-raw-data'),
    dcc.Store(id='store-processed-data'),
    dcc.Store(id='store-forecast-results'),
    dcc.Store(id='store-column-names'),
    dcc.Store(id='store-accuracy-actuals'),
    dbc.Alert(id="alert-notifications", is_open=False, duration=5000, style={"position": "fixed", "top": "10px", "right": "10px", "zIndex": "1050"}),
], fluid=True, style={"height":"100vh", "overflowY":"hidden"})

# --- Callbacks ---
# ... (All callbacks from toggle_sidebar_controls_visibility to the end of the file are unchanged from the previous version) ...
@app.callback(
    [Output('sidebar-tab1-controls-wrapper', 'style'), Output('sidebar-tab2-controls-wrapper', 'style')],
    [Input('tabs', 'value')]
)
def toggle_sidebar_controls_visibility(tab_value):
    if tab_value == 'tab-upload-view':
        return {'display': 'block'}, {'display': 'none'}
    elif tab_value == 'tab-forecast-sales':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'none'}, {'display': 'none'}

@app.callback(
    [Output('store-raw-data', 'data'), Output('store-column-names', 'data'), Output('alert-notifications', 'children'), Output('alert-notifications', 'is_open'), Output('alert-notifications', 'color'), Output('file-info', 'children'), Output('file-info-forecast-tab', 'children')],
    [Input('upload-data', 'contents'), Input('upload-data-forecast-tab', 'contents')],
    [State('upload-data', 'filename'), State('upload-data-forecast-tab', 'filename')],
    prevent_initial_call=True
)
def update_file_upload(contents_upload, contents_forecast, filenames_upload, filenames_forecast):
    ctx = dash.callback_context
    outputs = [None, None, dash.no_update, False, dash.no_update, dash.no_update, dash.no_update]
    if not ctx.triggered or not ctx.triggered[0] or 'prop_id' not in ctx.triggered[0]:
        outputs[2], outputs[3], outputs[4] = "Callback triggered unexpectedly.", True, "warning"
        return tuple(outputs)
    trigger_prop_id = ctx.triggered[0]['prop_id']
    trigger_input_id = trigger_prop_id.split('.')[0]
    list_of_contents, list_of_names = None, None
    if trigger_input_id == 'upload-data':
        list_of_contents, list_of_names = contents_upload, filenames_upload
    elif trigger_input_id == 'upload-data-forecast-tab':
        list_of_contents, list_of_names = contents_forecast, filenames_forecast

    current_file_info_text_target_idx = 5 if trigger_input_id == 'upload-data' else (6 if trigger_input_id == 'upload-data-forecast-tab' else -1)
    if list_of_contents is None:
        outputs[2], outputs[3], outputs[4] = "No files selected or upload cancelled.", True, "warning"
        if current_file_info_text_target_idx != -1: outputs[current_file_info_text_target_idx] = outputs[2]
        return tuple(outputs)
    if len(list_of_contents) > 10:
        outputs[2], outputs[3], outputs[4] = "Please upload a maximum of 10 files.", True, "warning"
        if current_file_info_text_target_idx != -1: outputs[current_file_info_text_target_idx] = outputs[2]
        return tuple(outputs)
    all_selected_dfs, error_files, processed_file_names = [], [], []
    date_keywords = [r"date", r"orderdate", r"transactiondate", r"timestamp"]
    sales_org_keywords = [r"salesorganization", r"salesorg", r"salesoffice", r"sorg", r"organization", r"branch", r"region", r"division", r"so", r"salesdistrictoffice"]
    matrl_group_keywords = [r"matlgroup", r"materialgroup", r"matrlgroup", r"matgroup", r"productgroup", r"itemgroup", r"productcategory", r"category", r"matrlgrp", r"mg", r"materialdescription"]
    dist_channel_keywords = [r"distributionchannel", r"distchannel", r"distrchannel", r"dchannel", r"channel"]
    material_keywords = [r"material", r"materialnumber", r"materialcode", r"materialid", r"itemcode", r"productcode"]
    sales_keywords = [r"net", r"netsales", r"netvalue", r"salesintons", r"revenue", r"salesamount", r"salesvalue", r"sales", r"quantity", r"amount", r"value", r"volume", r"tons"]
    mapped_cols_local = {}

    for i, (content, name) in enumerate(zip(list_of_contents, list_of_names)):
        try:
            content_type, content_string = content.split(',')
            decoded = base64.b64decode(content_string)
            if 'csv' in name.lower():
                df_single_file = pd.read_csv(io.StringIO(decoded.decode('utf-8')), low_memory=False)
            elif 'xls' in name.lower() or 'xlsx' in name.lower():
                df_single_file = pd.read_excel(io.BytesIO(decoded))
            else:
                error_files.append(f"{name} (unsupported format)")
                continue

            processed_file_names.append(name)
            original_column_names = list(df_single_file.columns)
            normalized_column_names_from_file = [re.sub(r"[^a-zA-Z0-9]", "", col).lower() for col in original_column_names]
            temp_orig_names, temp_norm_names = list(original_column_names), list(normalized_column_names_from_file)

            def find_and_mark_used(orig_names, norm_names, keywords_list):
                found_orig = get_original_col_name_by_keyword(orig_names, norm_names, keywords_list)
                new_orig_names, new_norm_names = list(orig_names), list(norm_names)
                if found_orig:
                    try:
                        idx = new_orig_names.index(found_orig)
                        new_orig_names.pop(idx)
                        new_norm_names.pop(idx)
                    except ValueError:
                        pass
                return found_orig, new_orig_names, new_norm_names

            actual_date_col_orig, temp_orig_names, temp_norm_names = find_and_mark_used(temp_orig_names, temp_norm_names, date_keywords)
            actual_sales_col_orig, temp_orig_names, temp_norm_names = find_and_mark_used(temp_orig_names, temp_norm_names, sales_keywords)
            actual_sales_org_col_orig, temp_orig_names, temp_norm_names = find_and_mark_used(temp_orig_names, temp_norm_names, sales_org_keywords)
            actual_matrl_group_col_orig, temp_orig_names, temp_norm_names = find_and_mark_used(temp_orig_names, temp_norm_names, matrl_group_keywords)
            actual_dist_channel_col_orig, temp_orig_names, temp_norm_names = find_and_mark_used(temp_orig_names, temp_norm_names, dist_channel_keywords)
            actual_material_col_orig, _, __ = find_and_mark_used(temp_orig_names, temp_norm_names, material_keywords)

            if not actual_date_col_orig or not actual_sales_col_orig:
                error_files.append(f"{name} (missing Date or Sales column)")
                continue
            if not mapped_cols_local:
                mapped_cols_local = {'Date': actual_date_col_orig, 'Sales': actual_sales_col_orig, 'Sales_Organization': actual_sales_org_col_orig, 'Material_Group': actual_matrl_group_col_orig, 'Distribution_Channel': actual_dist_channel_col_orig, 'Material': actual_material_col_orig}

            current_df_renamed = pd.DataFrame()
            try:
                dates_raw = df_single_file[actual_date_col_orig]
                dates = pd.to_datetime(dates_raw, errors='coerce')
                if dates.isna().sum() > len(dates) * 0.5:
                    if pd.api.types.is_numeric_dtype(dates_raw):
                        if not dates_raw[(dates_raw > 10000) & (dates_raw < 80000)].empty:
                            dates = pd.to_datetime(dates_raw, unit='D', origin='1899-12-30', errors='coerce')
                if dates.isna().sum() > len(dates) * 0.8:
                    dates = dates_raw.apply(lambda x: date_parser(str(x)) if pd.notna(x) else pd.NaT)
                current_df_renamed['Date'] = dates
            except Exception as e:
                error_files.append(f"{name} (Date parsing error: {str(e)})")
                continue

            current_df_renamed['Sales'] = pd.to_numeric(df_single_file[actual_sales_col_orig].astype(str).str.replace(r'[^\d.\-]', '', regex=True), errors='coerce')
            for target_col, actual_col_orig_name in [('Sales_Organization', actual_sales_org_col_orig), ('Material_Group', actual_matrl_group_col_orig), ('Distribution_Channel', actual_dist_channel_col_orig), ('Material', actual_material_col_orig)]:
                current_df_renamed[target_col] = df_single_file[actual_col_orig_name].astype(str).str.strip() if actual_col_orig_name and actual_col_orig_name in df_single_file.columns else "N/A"

            current_df_renamed.replace(["", "nan"], "N/A", inplace=True)
            current_df_renamed.dropna(subset=['Date', 'Sales'], inplace=True)
            if not current_df_renamed.empty:
                all_selected_dfs.append(current_df_renamed)
        except Exception as e:
            error_files.append(f"{name} (Outer processing error: {str(e)})")
            print(f"Error processing file {name}: {e}")

    final_current_file_info_text = ""
    if not all_selected_dfs:
        outputs[0], outputs[1] = None, None
        outputs[2] = f"No valid data processed. Errors: {', '.join(error_files) if error_files else 'None'}"
        outputs[3], outputs[4] = True, "danger"
        final_current_file_info_text = "No files processed or errors."
    else:
        combined_df = pd.concat(all_selected_dfs, ignore_index=True)
        outputs[0], outputs[1] = combined_df.to_dict('records'), mapped_cols_local
        outputs[2] = f"Successfully processed {len(all_selected_dfs)} file(s)."
        outputs[4] = "success"
        if error_files:
            outputs[2] += f" Some errors with: {', '.join(error_files)}"
            outputs[4] = "warning"
        outputs[3] = True
        final_current_file_info_text = f"Processed: {', '.join(processed_file_names) if processed_file_names else 'None'}"
        if error_files:
            final_current_file_info_text += f" | Failed: {', '.join(error_files)}"
    if current_file_info_text_target_idx != -1:
        outputs[current_file_info_text_target_idx] = final_current_file_info_text
    return tuple(outputs)

@app.callback(
    [Output('filter-sales-org', 'options'), Output('filter-sales-org', 'value'),
     Output('filter-matrl-group', 'options'), Output('filter-matrl-group', 'value'),
     Output('filter-dist-channel', 'options'), Output('filter-dist-channel', 'value'),
     Output('filter-material', 'options'), Output('filter-material', 'value'),
     Output('filter-controls-container', 'style'), Output('forecast-params-container', 'style')],
    [Input('store-raw-data', 'data')]
)
def update_filter_options(raw_data_json):
    no_data_style, visible_style = {'display': 'none'}, {'display': 'block'}
    df = pd.DataFrame()
    if raw_data_json is not None and bool(raw_data_json):
        df = pd.DataFrame(raw_data_json)

    sales_org_opts = get_filter_choices(df.get('Sales_Organization'), "All Sales Organizations")
    matrl_group_opts = get_filter_choices(df.get('Material_Group'), "All Material Groups")
    dist_channel_opts = get_filter_choices(df.get('Distribution_Channel'), "All Distribution Channels")
    material_opts = get_filter_choices(df.get('Material'), "All Materials")

    current_style = visible_style if not df.empty else no_data_style
    return (sales_org_opts, 'All', matrl_group_opts, 'All', dist_channel_opts, 'All', material_opts, 'All', current_style, current_style)

@app.callback(
    Output('store-processed-data', 'data'),
    [Input('store-raw-data', 'data'), Input('filter-sales-org', 'value'), Input('filter-matrl-group', 'value'), Input('filter-dist-channel', 'value'), Input('filter-material', 'value')]
)
def filter_and_process_data(raw_data_json, sales_org, matrl_group, dist_channel, material):
    empty_processed_df = pd.DataFrame(columns=['Month_Year', 'Total_Sales', 'Month_Year_Display']).to_dict('records')
    if raw_data_json is None:
        return None
    df_orig = pd.DataFrame(raw_data_json)
    if df_orig.empty:
        return empty_processed_df
    try:
        df_orig['Date'] = pd.to_datetime(df_orig['Date'])
    except Exception as e:
        print(f"Error converting 'Date' column to datetime in filter_and_process_data: {e}")
        return empty_processed_df
    df_filtered = df_orig.copy()
    if sales_org and sales_org != 'All':
        df_filtered = df_filtered[df_filtered['Sales_Organization'] == sales_org]
    if matrl_group and matrl_group != 'All':
        df_filtered = df_filtered[df_filtered['Material_Group'] == matrl_group]
    if dist_channel and dist_channel != 'All':
        df_filtered = df_filtered[df_filtered['Distribution_Channel'] == dist_channel]
    if material and material != 'All':
        df_filtered = df_filtered[df_filtered['Material'] == material]
    if df_filtered.empty:
        return empty_processed_df
    monthly_df = df_filtered.groupby(df_filtered['Date'].dt.to_period("M"))['Sales'].sum().reset_index()
    monthly_df.rename(columns={'Date': 'Month_Year', 'Sales': 'Total_Sales'}, inplace=True)
    monthly_df.sort_values('Month_Year', inplace=True)
    monthly_df['Month_Year_Display'] = monthly_df['Month_Year'].dt.strftime('%Y-%m')
    monthly_df['Month_Year'] = monthly_df['Month_Year'].astype(str)
    return monthly_df.to_dict('records')

accuracy_results_card = html.Div(id="accuracy-results-container", className="content-box mt-4", style={'display': 'none'}, children=[
    html.H4("7. Forecast Accuracy"),
    dcc.Loading(html.Div(id="accuracy-results-display"))
])

@app.callback(Output('page-content', 'children'),
              [Input('tabs', 'value'), Input('store-raw-data', 'data'), Input('store-forecast-results', 'data')])
def render_page_content(tab_value, raw_data_json, forecast_results_json):
    data_loaded = raw_data_json is not None and bool(raw_data_json)
    forecast_generated = forecast_results_json is not None and bool(forecast_results_json)
    jumbotron_like_className = "p-4 mb-4 bg-light rounded-3 text-center jumbotron-style"
    container_props = {"fluid": True, "className": "mt-4"}
    try:
        if tab_value == 'tab-upload-view':
            if not data_loaded:
                return dbc.Container(html.Div([html.H3("Welcome to the IOCL Sales Forecaster"), html.P("Please upload your sales data using the panel on the left to begin."), html.P([html.I(className="fas fa-arrow-left me-2"), " Use the 'Upload Sales Excel/CSV' button."])], className=jumbotron_like_className), **container_props)
            return dbc.Container([dbc.Row(dbc.Col(html.Div([html.H4("3. Monthly Sales Data (Filtered)"), dbc.Row([dbc.Col(dcc.Loading(dash_table.DataTable(id='monthly-sales-table', style_cell={'textAlign': 'center', 'padding': '5px'}, style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'}, page_size=10, style_table={'overflowX': 'auto'})), width=12, lg=5, className="content-box"), dbc.Col(dcc.Loading(dcc.Graph(id='monthly-sales-plot')), width=12, lg=7, className="content-box")])], className="content-box"), width=12))], **container_props)

        elif tab_value == 'tab-forecast-sales':
            if not data_loaded:
                return dbc.Container(html.Div([html.H3("Upload Data to Forecast"), html.P("Please upload your sales data first via the 'Upload & View Data' tab or the sidebar.")], className=jumbotron_like_className), **container_props)
            if not forecast_generated:
                 return dbc.Container(html.Div([html.H3("Ready to Forecast"), html.P("Adjust 'Forecast Periods' in the sidebar and click 'Generate Forecast'.")], className=jumbotron_like_className), **container_props)
            return dbc.Container([
                dbc.Row(dbc.Col(html.Div([
                    html.H4("5. Sales Forecast (Based on Filtered Data)"),
                    dcc.Loading(dcc.Graph(id='forecast-plot')),
                    dbc.Row([
                        dbc.Col(html.Div([html.H5("Forecasted Sales Values:"), dcc.Loading(dash_table.DataTable(id='forecast-table', style_cell={'textAlign': 'center', 'padding': '5px'}, style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'}, page_size=12, style_table={'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'}))], className="content-box"), width=12, lg=7),
                        dbc.Col(html.Div([html.H5("SARIMA Model Details:"), dcc.Loading(html.Pre(id='model-details-text', style={'maxHeight': '350px', 'overflowY': 'auto'}))], className="content-box"), width=12, lg=5)
                    ]),
                    accuracy_results_card
                ], className="content-box"), width=12))
            ], **container_props)

        return html.P("Select a tab or an unexpected error occurred in page rendering.")
    except Exception as e:
        print(f"!!! EXCEPTION in render_page_content for tab {tab_value}: {e}")
        import traceback
        print("Traceback for render_page_content error:")
        print(traceback.format_exc())
        return html.Div(f"Error rendering page content for tab {tab_value}: {str(e)}",
                        style={'color': 'red', 'padding': '20px', 'border': '1px solid red', 'margin': '20px', 'whiteSpace': 'pre-wrap'})

@app.callback(
    [Output('monthly-sales-table', 'data'), Output('monthly-sales-table', 'columns')],
    Input('store-processed-data', 'data')
)
def update_monthly_sales_table(processed_data_json):
    if processed_data_json is None or not processed_data_json: return [], []
    df = pd.DataFrame(processed_data_json)
    if df.empty or 'Total_Sales' not in df.columns or df['Total_Sales'].isnull().all(): return [{"Message": "No data to display for current filters."}], [{"name": "Message", "id": "Message"}]
    display_df = df[['Month_Year_Display', 'Total_Sales']].copy()
    display_df.rename(columns={'Month_Year_Display': 'Month-Year', 'Total_Sales': 'Total Sales'}, inplace=True)
    display_df['Total Sales'] = pd.to_numeric(display_df['Total Sales'], errors='coerce').round(2)
    columns = [{"name": i, "id": i} for i in display_df.columns]
    return display_df.to_dict('records'), columns

@app.callback(Output('monthly-sales-plot', 'figure'), Input('store-processed-data', 'data'))
def update_monthly_sales_plot(processed_data_json):
    empty_figure = {'data': [], 'layout': {"title": "Monthly Sales Trend", "xaxis_title": "Month-Year", "yaxis_title": "Total Sales", "annotations": [{"text": "No data to plot.", "showarrow": False, "xref": "paper", "yref": "paper", "x":0.5, "y":0.5}]}}
    if processed_data_json is None or not processed_data_json: return empty_figure
    df = pd.DataFrame(processed_data_json)
    try:
        df['Month_Year'] = pd.to_datetime(df['Month_Year'])
        df['Total_Sales'] = pd.to_numeric(df['Total_Sales'], errors='coerce')
    except Exception:
        empty_figure['layout']['annotations'][0]['text'] = "Error processing data for plot."
        return empty_figure
    df_plot = df.dropna(subset=['Month_Year', 'Total_Sales'])
    if df_plot.empty or len(df_plot) < 2:
        empty_figure['layout']['annotations'][0]['text'] = "Not enough valid data points to plot trend."
        return empty_figure
    try:
        fig = px.line(df_plot, x='Month_Year', y='Total_Sales', markers=True, labels={'Month_Year': 'Month-Year', 'Total_Sales': 'Total Sales'}, title="Monthly Sales Trend")
        fig.update_xaxes(tickformat="%Y-%m", dtick="M6", tickangle=45, automargin=True)
        fig.update_yaxes(automargin=True)
        fig.update_layout(hovermode="x unified", title_x=0.5, title_font=dict(weight="bold"))
        return fig
    except Exception as e:
        empty_figure['layout']['annotations'][0]['text'] = "Error generating plot."
        return empty_figure

# --- FINAL FORECASTING CALLBACK USING SUBPROCESS ---
@app.callback(
    [Output('store-forecast-results', 'data'), Output('alert-notifications', 'children', allow_duplicate=True), Output('alert-notifications', 'is_open', allow_duplicate=True), Output('alert-notifications', 'color', allow_duplicate=True)],
    [Input('generate-forecast-btn', 'n_clicks')],
    [State('store-processed-data', 'data'), State('forecast-periods', 'value')],
    prevent_initial_call=True
)
def generate_forecast(n_clicks, processed_data_json, forecast_periods):
    if n_clicks is None:
        return dash.no_update, dash.no_update, False, dash.no_update
    if processed_data_json is None:
        return None, "No data available for forecasting.", True, "warning"

    monthly_sales_data = pd.DataFrame(processed_data_json)
    if monthly_sales_data.empty:
        return None, "No data available for forecasting.", True, "warning"

    min_obs_forecast = 24
    if len(monthly_sales_data) < min_obs_forecast:
        return None, f"Not enough historical data ({len(monthly_sales_data)} months).", True, "warning"
        
    # --- Subprocess Logic ---
    run_id = str(uuid.uuid4())
    input_file = f'forecast_input_{run_id}.csv'
    output_file = f'forecast_output_{run_id}.csv'
    summary_file = f'forecast_summary_{run_id}.txt'
    
    try:
        monthly_sales_data[['Month_Year_Display', 'Total_Sales']].to_csv(input_file, index=False, header=['Month_Year', 'Total_Sales'])
        
        command = [
            'Rscript', 'forecast_script.R',
            input_file, str(forecast_periods), output_file, summary_file
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        forecast_df = pd.read_csv(output_file)
        with open(summary_file, 'r') as f:
            model_details_str = f.read()

        if model_details_str.lower().startswith("error in r script"):
            return None, model_details_str, True, "danger"

        last_period = pd.to_datetime(monthly_sales_data['Month_Year']).dt.to_period('M').max()
        future_periods_idx = pd.period_range(start=last_period + 1, periods=forecast_periods, freq='M')
        
        if len(forecast_df) != len(future_periods_idx):
            return None, "Forecast output length mismatch from R script.", True, "danger"
            
        forecast_df['Month_Year'] = future_periods_idx
        forecast_df['Month_Year_Display'] = forecast_df['Month_Year'].dt.strftime('%Y-%m')
        forecast_df['Month_Year'] = forecast_df['Month_Year'].astype(str)

        forecast_df.rename(columns={
            'Point.Forecast': 'Forecasted_Sales',
            'Lo.80': 'Lower_80', 'Hi.80': 'Upper_80',
            'Lo.95': 'Lower_95', 'Hi.95': 'Upper_95'
        }, inplace=True)

        actual_df_out = monthly_sales_data[['Month_Year', 'Total_Sales', 'Month_Year_Display']].copy()
        
        results = {'actual': actual_df_out.to_dict('records'),
                   'forecast': forecast_df.to_dict('records'),
                   'model_details': model_details_str}
        
        return results, "Forecast generated successfully using R script!", True, "success"

    except FileNotFoundError:
        return None, "Error: 'Rscript' command not found. Please ensure R is installed and in your system's PATH.", True, "danger"
    except subprocess.CalledProcessError as e:
        error_message = f"Error running R script: {e.stderr}"
        return None, error_message, True, "danger"
    except Exception as e:
        return None, f"An unexpected error occurred: {str(e)}", True, "danger"
    finally:
        for f in [input_file, output_file, summary_file]:
            if os.path.exists(f):
                os.remove(f)

# ... (The rest of the callbacks from update_forecast_plot to the end remain unchanged) ...
@app.callback(Output('forecast-plot', 'figure'), Input('store-forecast-results', 'data'))
def update_forecast_plot(forecast_results_json):
    empty_figure = {'data':[], 'layout':{"title": "Actual vs. Forecasted Sales", "annotations": [{"text": "No forecast data to plot.", "showarrow": False, "xref":"paper", "yref":"paper", "x":0.5, "y":0.5}]}}
    if not forecast_results_json: return empty_figure
    actual_df = pd.DataFrame(forecast_results_json['actual'])
    forecast_df = pd.DataFrame(forecast_results_json['forecast'])
    try:
        actual_df['Month_Year'] = pd.to_datetime(actual_df['Month_Year'])
        forecast_df['Month_Year'] = pd.to_datetime(forecast_df['Month_Year'])
        actual_df['Total_Sales'] = pd.to_numeric(actual_df['Total_Sales'], errors='coerce')
        forecast_df['Forecasted_Sales'] = pd.to_numeric(forecast_df['Forecasted_Sales'], errors='coerce')
    except:
        empty_figure['layout']['annotations'][0]['text'] = "Error parsing dates/sales for plot."
        return empty_figure
    fig = go.Figure()
    actual_df_plot = actual_df.dropna(subset=['Month_Year', 'Total_Sales'])
    if not actual_df_plot.empty: fig.add_trace(go.Scatter(x=actual_df_plot['Month_Year'], y=actual_df_plot['Total_Sales'], mode='lines+markers', name='Actual Sales', line=dict(color='#0073b7')))
    forecast_df_plot = forecast_df.dropna(subset=['Month_Year', 'Forecasted_Sales'])
    if not forecast_df_plot.empty:
        fig.add_trace(go.Scatter(x=forecast_df_plot['Month_Year'], y=forecast_df_plot['Forecasted_Sales'], mode='lines+markers', name='Forecasted Sales', line=dict(color='orange')))
        for ci_val_str, ci_alpha_val in [('95', 0.2), ('80', 0.3)]:
            lower_col, upper_col = f'Lower_{ci_val_str}', f'Upper_{ci_val_str}'
            if lower_col in forecast_df_plot and upper_col in forecast_df_plot:
                plot_ci_df = forecast_df_plot.dropna(subset=[lower_col, upper_col])
                if not plot_ci_df.empty:
                    fig.add_trace(go.Scatter(x=plot_ci_df['Month_Year'].tolist() + plot_ci_df['Month_Year'].tolist()[::-1],
                                             y=pd.to_numeric(plot_ci_df[upper_col], errors='coerce').tolist() + pd.to_numeric(plot_ci_df[lower_col], errors='coerce').tolist()[::-1],
                                             fill='toself', fillcolor=f'rgba(255,165,0,{ci_alpha_val})',
                                             line=dict(color='rgba(255,255,255,0)'),
                                             hoverinfo="skip", name=f'{ci_val_str}% CI'))
    fig.update_layout(title="Actual vs. Forecasted Sales", xaxis_title="Month-Year", yaxis_title="Sales", hovermode="x unified", title_x=0.5, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(tickformat="%Y-%m", dtick="M6", automargin=True)
    fig.update_yaxes(automargin=True)
    return fig

@app.callback(
    [Output('forecast-table', 'data'), Output('forecast-table', 'columns')],
    Input('store-forecast-results', 'data')
)
def update_forecast_table(forecast_results_json):
    if not forecast_results_json or 'forecast' not in forecast_results_json: return [], []
    df = pd.DataFrame(forecast_results_json['forecast'])
    if df.empty: return [{"Message": "No future forecast data to display."}], [{"name": "Message", "id": "Message"}]
    display_df = df[['Month_Year_Display', 'Forecasted_Sales', 'Lower_80', 'Upper_80', 'Lower_95', 'Upper_95']].copy()
    display_df.rename(columns={'Month_Year_Display': 'Month-Year', 'Forecasted_Sales': 'Forecasted Sales', 'Lower_80': 'Lower 80% CI', 'Upper_80': 'Upper 80% CI', 'Lower_95': 'Lower 95% CI', 'Upper_95': 'Upper 95% CI'}, inplace=True)
    for col in ['Forecasted Sales', 'Lower 80% CI', 'Upper 80% CI', 'Lower 95% CI', 'Upper 95% CI']:
        if col in display_df: display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(2)
    columns = [{"name": i, "id": i} for i in display_df.columns]
    return display_df.to_dict('records'), columns

@app.callback(Output('model-details-text', 'children'), Input('store-forecast-results', 'data'))
def update_model_details_text(forecast_results_json):
    if not forecast_results_json or 'model_details' not in forecast_results_json:
        return "Model details are not available."
    return forecast_results_json['model_details']

@app.callback(
    [Output('store-accuracy-actuals', 'data'),
     Output('file-info-accuracy', 'children'),
     Output('calculate-accuracy-btn', 'disabled'),
     Output('alert-notifications', 'children', allow_duplicate=True),
     Output('alert-notifications', 'is_open', allow_duplicate=True),
     Output('alert-notifications', 'color', allow_duplicate=True)],
    [Input('upload-actuals-accuracy', 'contents')],
    [State('upload-actuals-accuracy', 'filename'),
     State('store-column-names', 'data'),
     State('filter-sales-org', 'value'),
     State('filter-matrl-group', 'value'),
     State('filter-dist-channel', 'value'),
     State('filter-material', 'value')],
    prevent_initial_call=True
)
def handle_accuracy_upload(contents, filename, mapped_cols, sales_org, matrl_group, dist_channel, material):
    if contents is None:
        return None, "Awaiting next year's actuals file...", True, dash.no_update, False, dash.no_update

    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        if 'csv' in filename.lower():
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), low_memory=False)
        elif 'xls' in filename.lower() or 'xlsx' in filename.lower():
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None, f"Unsupported file format: {filename}", True, "Unsupported file format.", True, "warning"

        actual_date_col = mapped_cols.get('Date')
        actual_sales_col = mapped_cols.get('Sales')

        if not actual_date_col or not actual_sales_col:
            return None, "Column mapping not found. Please re-upload initial data.", True, "Column mapping error.", True, "danger"

        df_processed = pd.DataFrame()
        df_processed['Date'] = pd.to_datetime(df[actual_date_col], errors='coerce')
        df_processed['Sales'] = pd.to_numeric(df[actual_sales_col].astype(str).str.replace(r'[^\d.\-]', '', regex=True), errors='coerce')

        for target_col, actual_col in [
            ('Sales_Organization', mapped_cols.get('Sales_Organization')),
            ('Material_Group', mapped_cols.get('Material_Group')),
            ('Distribution_Channel', mapped_cols.get('Distribution_Channel')),
            ('Material', mapped_cols.get('Material'))]:
            df_processed[target_col] = df[actual_col].astype(str).str.strip() if actual_col and actual_col in df.columns else "N/A"

        df_processed.dropna(subset=['Date', 'Sales'], inplace=True)

        df_filtered = df_processed.copy()
        if sales_org and sales_org != 'All':
            df_filtered = df_filtered[df_filtered['Sales_Organization'] == sales_org]
        if matrl_group and matrl_group != 'All':
            df_filtered = df_filtered[df_filtered['Material_Group'] == matrl_group]
        if dist_channel and dist_channel != 'All':
            df_filtered = df_filtered[df_filtered['Distribution_Channel'] == dist_channel]
        if material and material != 'All':
            df_filtered = df_filtered[df_filtered['Material'] == material]

        if df_filtered.empty:
            return None, f"No data in '{filename}' matches current filters.", True, "No matching data in file.", True, "warning"

        monthly_df = df_filtered.groupby(df_filtered['Date'].dt.to_period("M"))['Sales'].sum().reset_index()
        monthly_df.rename(columns={'Date': 'Month_Year', 'Sales': 'Actual_Sales'}, inplace=True)
        monthly_df['Month_Year'] = monthly_df['Month_Year'].astype(str)

        return monthly_df.to_dict('records'), f"Ready: {filename}", False, "Actuals file processed. Ready for accuracy calculation.", True, "success"

    except Exception as e:
        return None, f"Error processing '{filename}'", True, f"File processing error: {e}", True, "danger"

@app.callback(
    [Output('accuracy-results-container', 'style'),
     Output('accuracy-results-display', 'children'),
     Output('alert-notifications', 'children', allow_duplicate=True),
     Output('alert-notifications', 'is_open', allow_duplicate=True),
     Output('alert-notifications', 'color', allow_duplicate=True)],
    [Input('calculate-accuracy-btn', 'n_clicks')],
    [State('store-forecast-results', 'data'),
     State('store-accuracy-actuals', 'data')],
    prevent_initial_call=True
)
def calculate_and_display_accuracy(n_clicks, forecast_data_json, accuracy_actuals_json):
    if n_clicks is None or not forecast_data_json or not accuracy_actuals_json:
        return {'display': 'none'}, "", "Missing data for accuracy calculation.", True, "warning"

    try:
        forecast_df = pd.DataFrame(forecast_data_json['forecast'])
        actuals_df = pd.DataFrame(accuracy_actuals_json)

        comparison_df = pd.merge(
            forecast_df[['Month_Year_Display', 'Forecasted_Sales']],
            actuals_df[['Month_Year', 'Actual_Sales']],
            left_on='Month_Year_Display',
            right_on='Month_Year',
            how='inner'
        )

        if comparison_df.empty:
            return {'display': 'block'}, "No overlapping periods found between forecast and actuals.", "No overlapping data.", True, "warning"

        y_true = comparison_df['Actual_Sales']
        y_pred = comparison_df['Forecasted_Sales']

        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mape = np.mean(np.abs((y_true - y_pred) / np.where(y_true == 0, 1, y_true))) * 100

        comparison_df['% Difference'] = ((y_true - y_pred) / y_true) * 100
        comparison_df.replace([np.inf, -np.inf], np.nan, inplace=True)

        display_df = comparison_df[['Month_Year_Display', 'Actual_Sales', 'Forecasted_Sales', '% Difference']].copy()
        display_df.rename(columns={
            'Month_Year_Display': 'Month-Year',
            'Actual_Sales': 'Actual Sales',
            'Forecasted_Sales': 'Forecasted Sales',
            '% Difference': '% Difference'
        }, inplace=True)

        display_df['Actual Sales'] = display_df['Actual Sales'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
        display_df['Forecasted Sales'] = display_df['Forecasted Sales'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
        display_df['% Difference'] = display_df['% Difference'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")

        metric_cards = dbc.Row([
            dbc.Col(dbc.Card([dbc.CardHeader("MAE"), dbc.CardBody(f"{mae:,.2f}")], color="primary", inverse=True), width=4),
            dbc.Col(dbc.Card([dbc.CardHeader("RMSE"), dbc.CardBody(f"{rmse:,.2f}")], color="secondary", inverse=True), width=4),
            dbc.Col(dbc.Card([dbc.CardHeader("MAPE"), dbc.CardBody(f"{mape:.2f}%")], color="dark", inverse=True), width=4),
        ])

        accuracy_table = dash_table.DataTable(
            data=display_df.to_dict('records'),
            columns=[{'name': i, 'id': i} for i in display_df.columns],
            style_cell={'textAlign': 'center', 'padding': '5px'},
            style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
            style_table={'marginTop': '20px'},
            style_data_conditional=[
                {'if': {'column_id': col}, 'textAlign': 'right'}
                for col in ['Actual Sales', 'Forecasted Sales', '% Difference']
            ]
        )

        results_layout = html.Div([
            metric_cards,
            html.H5("Detailed Comparison:", className="mt-4"),
            accuracy_table
        ])

        return {'display': 'block'}, results_layout, "Accuracy calculated successfully.", True, "success"

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {'display': 'block'}, f"An error occurred during accuracy calculation: {e}", "Accuracy calculation failed.", True, "danger"

# ✅ Required for Render deployment
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=True, host="0.0.0.0", port=port)