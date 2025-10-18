import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# --- Initialize Dash ---
app = dash.Dash(__name__)
server = app.server

# --- Load CSV ---
df = pd.read_csv("AllFnOStocks_Opc_trend_analysis.csv")
df["Date"] = pd.to_datetime(df["Date"])

# --- App layout ---
app.layout = html.Div([
    # Top row: Holding checkbox + Stock selection dropdown + Stats
    html.Div(
        style={"display": "flex", "alignItems": "center", "justifyContent": "flex-start", "gap": "20px", "padding": "10px"},
        children=[
            # Checkbox for Holding filter
            dcc.Checklist(
                id="holding-filter",
                options=[{"label": "Hlds Only", "value": "holding"}],
                value=[],
                inputStyle={"margin-right": "5px"}
            ),
            # Stock dropdown
            dcc.Dropdown(
                id="symbol-dropdown",
                options=[{"label": s, "value": s} for s in sorted(df["Symbol"].unique())],
                value=sorted(df["Symbol"].unique())[0],
                clearable=False,
                style={"width": "300px", "backgroundColor": "#ffffff"}
            ),
            # Stats / summary
            html.Div(
                id="stats-output",
                style={"fontWeight": "bold", "marginLeft": "20px"}
            )
        ]
    ),
    # Graph
    dcc.Graph(id="trend-graph", style={"height": "90vh"})
])

# --- Callback to update stock dropdown if holding filter is applied ---
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

# --- Callback to update graph and stats ---
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
            xaxis_title="Date",
            yaxis_title="Values",
            plot_bgcolor="#f5f5f5",
            paper_bgcolor="#f5f5f5"
        )
        return fig, "No data to display"

    # Map dates to sequential positions
    x_pos = list(range(len(data)))
    tickvals = x_pos
    ticktext = [d.strftime("%d") if d.day != 1 else d.strftime("%d-%b") for d in data["Date"]]

    # Prepare customdata: one per date, all indicators
    customdata = list(zip(
        data["Date"], data["CMP"], data["Support"], data["Resistance"], data["strikePrice"], data["PCR"]
    ))

    # --- Plot traces ---
    fig = go.Figure()
    traces = [
        ("CMP", data["CMP"], "blue", "y", "solid"),
        ("Support", data["Support"], "green", "y", "dot"),
        ("Resistance", data["Resistance"], "red", "y", "dot"),
        ("Strike Price", data["strikePrice"], "olive", "y", "solid"),
        ("PCR", data["PCR"], "orange", "y2", "solid")
    ]

    for name, y, color, yaxis, dash_style in traces:
        fig.add_trace(go.Scatter(
            x=x_pos,
            y=y,
            name=name,
            line=dict(color=color, dash=dash_style),
            yaxis=yaxis,
            customdata=customdata,
#            hovertemplate=(
#                "%{name}<br>"
#            )
            hoverinfo="x+y+name"
        ))

    # --- Annotations for line labels ---
    annotations = []
    for name, y, color, yaxis, _ in traces:
        annotations.append(dict(
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
        ))

    # --- Layout ---
    fig.update_layout(
        plot_bgcolor="#f5f5f5",
        paper_bgcolor="#f5f5f5",
        font=dict(color="#333"),
        yaxis=dict(title="CMP / Support / Resistance / Strike Price"),
        yaxis2=dict(title="PCR", overlaying="y", side="right"),
        #legend=dict(orientation="v", yanchor="top", y=0.95, xanchor="left", x=1.02),
        showlegend=False,
        margin=dict(l=40, r=120, t=60, b=40),
        annotations=annotations,
        hovermode="x unified"
    )

    # --- X-axis settings ---
    fig.update_xaxes(
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=45
    )

    # --- Latest summary ---
    latest = data.iloc[-1]
    summary = (
        f"Exp: {latest['expiryDate']} | As of {latest['Date'].date()} | CMP: {latest['CMP']} | Sup: {latest['Support']} | "
        f"Res: {latest['Resistance']} | PCR: {latest['PCR']} | Strk Price: {latest['strikePrice']}"
    )

    return fig, summary

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
