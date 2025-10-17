import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# --- Initialize app ---
app = dash.Dash(__name__)
server = app.server

# --- Load CSV ---
# You can replace this with your CSV path
# Or allow file upload (shown below)
df = pd.read_csv("AllFnOStocks_Opc_trend_analysis.csv")  # change path as needed

# Ensure date type
df["Date"] = pd.to_datetime(df["Date"])

# --- App layout ---
app.layout = html.Div([
    html.H2("📈 Stock Trend Visualizer (Dash)", style={"textAlign": "center"}),

    html.Label("Select Stock Symbol:"),
    dcc.Dropdown(
        id="symbol-dropdown",
        options=[{"label": s, "value": s} for s in df["Symbol"].unique()],
        value=df["Symbol"].unique()[0],
        clearable=False,
    ),

    dcc.Graph(id="trend-graph", style={"height": "75vh"}),

    html.Br(),
    html.Div(id="stats-output", style={"textAlign": "center", "fontWeight": "bold"})
])

# --- Callback to update chart ---
@app.callback(
    [Output("trend-graph", "figure"),
     Output("stats-output", "children")],
    [Input("symbol-dropdown", "value")]
)
def update_graph(symbol):
    data = df[df["Symbol"] == symbol].sort_values("Date")

    # --- Plot ---
    fig = go.Figure()

    # CMP, Support, Resistance
    fig.add_trace(go.Scatter(x=data["Date"], y=data["CMP"], name="CMP", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=data["Date"], y=data["Support"], name="Support", line=dict(color="green", dash="dot")))
    fig.add_trace(go.Scatter(x=data["Date"], y=data["Resistance"], name="Resistance", line=dict(color="red", dash="dot")))

    # PCR on secondary axis
    fig.add_trace(go.Scatter(x=data["Date"], y=data["PCR"], name="PCR", line=dict(color="orange"), yaxis="y2"))

    fig.update_layout(
       # title=f"{symbol} — CMP, Support, Resistance, and PCR Trends",
        xaxis=dict(title="Date"),
        yaxis=dict(title="CMP / Support / Resistance"),
        yaxis2=dict(title="PCR", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40)
    )

    # --- Summary text ---
    latest = data.iloc[-1]
    summary = f"📅 Latest Date: {latest['Date'].date()} | 💰 CMP: {latest['CMP']} | 🧭 Support: {latest['Support']} | 🧱 Resistance: {latest['Resistance']} | 📊 PCR: {latest['PCR']}"

    return fig, summary

# --- Run server ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)