import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from allIndices import STOCK_INFO   # import your dict

# --- Initialize Dash ---
app = dash.Dash(
    __name__,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0"}
    ]
)
server = app.server

# --- Load CSV ---
df = pd.read_csv("AllFnOStocks_Opc_trend_analysis.csv")
df["Date"] = pd.to_datetime(df["Date"])

# --- Merge STOCK_INFO ---
info_df = pd.DataFrame.from_dict(STOCK_INFO, orient="index").reset_index()
info_df.rename(columns={"index": "Symbol"}, inplace=True)
df = df.merge(info_df, on="Symbol", how="left")

# --- App Layout ---
app.layout = html.Div(
    style={
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "stretch",
        "height": "100vh",
        "overflow": "hidden"
    },
    children=[
        # Top Controls
        html.Div(
            style={
                "display": "flex",
                "flexWrap": "wrap",
                "alignItems": "center",
                "justifyContent": "flex-start",
                "gap": "10px",
                "padding": "10px"
            },
            children=[
                dcc.Checklist(
                    id="holding-filter",
                    options=[{"label": "Hlds Only", "value": "holding"}],
                    value=[],
                    inputStyle={"margin-right": "5px"}
                ),
                # Group-by dropdown
                dcc.Dropdown(
                    id="groupby-dropdown",
                    options=[
                        {"label": "Symbol", "value": "Symbol"},
                        {"label": "Sector", "value": "sector"},
                        {"label": "Industry", "value": "industry"},
                        {"label": "Basic Industry", "value": "basicIndustry"},
                        {"label": "Macro", "value": "macro"},
                    ],
                    value="Symbol",
                    clearable=False,
                    style={"width": "180px"}
                ),
                # Symbol or group dropdown
                dcc.Dropdown(
                    id="symbol-dropdown",
                    options=[{"label": s, "value": s} for s in sorted(df["Symbol"].unique())],
                    value=sorted(df["Symbol"].unique())[0],
                    clearable=False,
                    style={"width": "250px", "minWidth": "200px"}
                ),
                html.Div(
                    id="stats-output",
                    style={"fontWeight": "bold", "marginLeft": "20px", "flexGrow": "1"}
                )
            ]
        ),
        # Graph Section
        html.Div(
            style={"flexGrow": "1", "padding": "5px"},
            children=[
                dcc.Graph(
                    id="trend-graph",
                    style={
                        "height": "85vh",
                        "width": "100%",
                        "maxWidth": "100%",
                        "flexGrow": "1"
                    },
                    config={"responsive": True}
                )
            ]
        )
    ]
)

# --- Update dropdown options based on groupby ---
@app.callback(
    Output("symbol-dropdown", "options"),
    [Input("holding-filter", "value"),
     Input("groupby-dropdown", "value")]
)
def update_dropdown(holding_values, groupby):
    data = df.copy()
    if "holding" in holding_values:
        data = data[data["Type"] == "Holding"]
    values = sorted(data[groupby].dropna().unique())
    return [{"label": s, "value": s} for s in values]

# --- Update graph and stats ---
@app.callback(
    [Output("trend-graph", "figure"),
     Output("stats-output", "children")],
    [Input("symbol-dropdown", "value"),
     Input("groupby-dropdown", "value")]
)
def update_graph(selected_value, groupby):
    if selected_value is None:
        fig = go.Figure()
        fig.update_layout(title="No selection")
        return fig, "No data to display"

    if groupby == "Symbol":
        data = df[df["Symbol"] == selected_value].sort_values("Date").reset_index(drop=True)
    else:
        # Aggregate all stocks in this group by Date
        group_data = (
            df[df[groupby] == selected_value]
            .groupby("Date", as_index=False)
            .agg({
                "CMP": "mean",
                "Support": "mean",
                "Resistance": "mean",
                "strikePrice": "mean",
                "PCR": "mean",
                "RSI" : "mean",
                "BB_HI" : "mean",
                "BB_LO" : "mean"
            })
        )
        data = group_data.sort_values("Date").reset_index(drop=True)

    if data.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No data available for this selection",
            plot_bgcolor="#f5f5f5",
            paper_bgcolor="#f5f5f5"
        )
        return fig, "No data to display"

    x_pos = list(range(len(data)))
    ticktext = [d.strftime("%d") if d.day != 1 else d.strftime("%d-%b") for d in data["Date"]]

    traces = [
        ("CMP", data["CMP"], "blue", "y", "solid"),
        ("Support", data["Support"], "green", "y", "dot"),
        ("Resistance", data["Resistance"], "red", "y", "dot"),
        ("Strike Price", data["strikePrice"], "olive", "y", "solid"),
        ("PCR", data["PCR"], "orange", "y2", "solid"),
#        ("RSI", data["RSI"], "orange", "y2", "solid"),
        ("BB_HI", data["BB_HI"], "black", "y", "solid"),
        ("BB_LO", data["BB_LO"], "black", "y", "solid")                       
    ]

    fig = go.Figure()

    # --- CMP, Support, Resistance, etc. ---
    # 1️⃣ Plot Support line first (lower boundary)
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["Support"],
        name="Support",
        line=dict(color="green", dash="dot"),
        yaxis="y",
        hoverinfo="x+y+name",
        fill=None  # lower line only
    ))

    # 2️⃣ Plot Resistance line with fill between it and Support
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["Resistance"],
        name="Resistance",
        line=dict(color="red", dash="dot"),
        yaxis="y",
        hoverinfo="x+y+name",
        fill='tonexty',  # fill between this and previous trace
        fillcolor="rgba(0, 200, 0, 0.1)"  # translucent red shade
    ))

    # 3️⃣ Add CMP line
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["CMP"],
        name="CMP",
        line=dict(color="blue", dash="solid"),
        yaxis="y",
        hoverinfo="x+y+name"
    ))

    # 4️⃣ Add Strike Price
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["strikePrice"],
        name="Strike Price",
        line=dict(color="olive", dash="solid"),
        yaxis="y",
        hoverinfo="x+y+name"
    ))

    # 5️⃣ Add PCR line (secondary axis)
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["PCR"],
        name="PCR",
        line=dict(color="orange", dash="solid"),
        yaxis="y2",
        hoverinfo="x+y+name"
    ))

    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["BB_HI"],
        name="BB_HI",
        line=dict(color="black", dash="solid"),
        yaxis="y",
        hoverinfo="x+y+name",
        fill=None  # lower line only
    ))

    # 2️⃣ Plot Resistance line with fill between it and Support
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=data["BB_LO"],
        name="BB_LO",
        line=dict(color="black", dash="solid"),
        yaxis="y",
        hoverinfo="x+y+name",
        fill=None,  # fill between this and previous trace
    ))

    annotations = [
        dict(
            x=x_pos[-1] + 0.3,
            y=y.iloc[-1],
            xref="x",
            yref="y" if name != "PCR" else "y2",
            text=name,
            font=dict(color="White", size=12, family="Arial Black, Arial, sans-serif"),
            showarrow=False,
            align="right",
            bgcolor="rgba(0,0,0,0.8)",
            bordercolor=color,
            borderwidth=1,
            borderpad=2
        )
        for name, y, color, yaxis, _ in traces
    ]

    fig.update_layout(
        plot_bgcolor="#f5f5f5",
        paper_bgcolor="#f5f5f5",
        font=dict(color="#333"),
        yaxis=dict(title="CMP / Support / Resistance / Strike Price / BB_HI / BB_LO"),
        yaxis2=dict(title="PCR", overlaying="y", side="right"),
        showlegend=False,
        margin=dict(l=40, r=100, t=40, b=60),
        annotations=annotations,
        hovermode="x unified",
        autosize=True
    )

    fig.update_xaxes(
        tickmode="array",
        tickvals=x_pos,
        ticktext=ticktext,
        tickangle=45
    )

    latest = data.iloc[-1]
    #summary = f"Showing {groupby} level trend: {selected_value}"
    if groupby == "Symbol":
        num_symbols = 1
        summary = ""
    else:
        # Count unique symbols in this group
        num_symbols = df[df[groupby] == selected_value]["Symbol"].nunique()
        summary = f"Showing avg data for {num_symbols} symbols" # in {groupby}: {selected_value}"


    return fig, summary

# --- Mobile optimization CSS ---
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Trend Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            @media (max-width: 600px) {
                .dash-graph {
                    height: 75vh !important;
                    width: 100vw !important;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

# --- Run App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
