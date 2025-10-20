import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import logging
import sys

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

# --- Update dropdown options ---
@app.callback(
    Output("symbol-dropdown", "options"),
    Input("holding-filter", "value")
)
def update_dropdown(holding_values):
    if "holding" in holding_values:
        symbols = sorted(df[df["Type"] == "Holding"]["Symbol"].unique())
    else:
        symbols = sorted(df["Symbol"].unique())
    return [{"label": s, "value": s} for s in symbols]


# --- Update graph and stats ---
@app.callback(
    [Output("trend-graph", "figure"),
     Output("stats-output", "children")],
    [Input("symbol-dropdown", "value")]
)
def update_graph(symbol):
    data = df[df["Symbol"] == symbol].sort_values("Date").reset_index(drop=True)

    if data.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No data available for this selection",
            plot_bgcolor="#f5f5f5",
            paper_bgcolor="#f5f5f5"
        )
        return fig, "No data to display"

    # Sequential x positions
    x_pos = list(range(len(data)))
    ticktext = [d.strftime("%d") if d.day != 1 else d.strftime("%d-%b") for d in data["Date"]]

    # Plot lines
    traces = [
        ("CMP", data["CMP"], "blue", "y", "solid"),
        ("Support", data["Support"], "green", "y", "dot"),
        ("Resistance", data["Resistance"], "red", "y", "dot"),
        ("Strike Price", data["strikePrice"], "olive", "y", "solid"),
        ("PCR", data["PCR"], "orange", "y2", "solid")
    ]

    fig = go.Figure()
    for name, y, color, yaxis, dash_style in traces:
        fig.add_trace(go.Scatter(
            x=x_pos,
            y=y,
            name=name,
            line=dict(color=color, dash=dash_style),
            yaxis=yaxis,
            hoverinfo="x+y+name"
        ))

    # Label annotations
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
        yaxis=dict(title="CMP / Support / Resistance / Strike Price"),
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
    summary = ()

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
