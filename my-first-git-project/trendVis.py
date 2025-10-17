import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# --- Initialize app ---
app = dash.Dash(__name__)
server = app.server

# --- Load CSV ---
df = pd.read_csv("AllFnOStocks_Opc_trend_analysis.csv")
df["Date"] = pd.to_datetime(df["Date"])

# --- App layout ---
app.layout = html.Div([
    html.Div(
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"},
        children=[
            # Stock selection dropdown
            dcc.Dropdown(
                id="symbol-dropdown",
                options=[{"label": s, "value": s} for s in df["Symbol"].unique()],
                value=df["Symbol"].unique()[0],
                clearable=False,
                style={"width": "300px"}
            ),
            # Stats / summary next to dropdown
            html.Div(
                id="stats-output",
                style={"fontWeight": "bold", "marginLeft": "20px"}
            )
        ]
    ),
    # Graph below
    dcc.Graph(id="trend-graph", style={"height": "90vh"})
])


@app.callback(
    [Output("trend-graph", "figure"),
     Output("stats-output", "children")],
    [Input("symbol-dropdown", "value")]
)
def update_graph(symbol):
    data = df[df["Symbol"] == symbol].sort_values("Date").reset_index(drop=True)
    
    # Sequential x-axis positions
    x_pos = list(range(len(data)))
    tickvals = x_pos
    ticktext = [d.strftime("%d") if d.day != 1 else d.strftime("%d-%b") for d in data["Date"]]

    fig = go.Figure()

    # Lines
    fig.add_trace(go.Scatter(x=x_pos, y=data["CMP"], name="CMP", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=x_pos, y=data["Support"], name="Support", line=dict(color="green", dash="dot")))
    fig.add_trace(go.Scatter(x=x_pos, y=data["Resistance"], name="Resistance", line=dict(color="red", dash="dot")))
    fig.add_trace(go.Scatter(x=x_pos, y=data["strikePrice"], name="Strike Price", line=dict(color="olive")))
    fig.add_trace(go.Scatter(x=x_pos, y=data["PCR"], name="PCR", line=dict(color="orange"), yaxis="y2"))

    # Hide default legend
    fig.update_layout(showlegend=False, yaxis2=dict(title="PCR", overlaying="y", side="right"),
                      margin=dict(l=40, r=40, t=60, b=40))

    # Inline labels beside last point of each line
    colors = ["blue", "green", "red", "olive", "orange"]
    names = ["CMP", "Support", "Resistance", "Strike Price", "PCR"]
    ys = [data["CMP"].iloc[-1], data["Support"].iloc[-1], data["Resistance"].iloc[-1],
          data["strikePrice"].iloc[-1], data["PCR"].iloc[-1]]

    annotations = []
    for i, y_val in enumerate(ys):
        annotations.append(dict(
            x=x_pos[-1] + 0.3,  # slightly right of last point
            y=y_val,
            xref="x",
            yref="y" if names[i] != "PCR" else "y2",
            text=names[i],
            font=dict(
                color=colors[i],
                size=12,
                family="Arial Black, Arial, sans-serif",  # bold-looking font
                weight="bold"  # correct property
            ),
            showarrow=False,
            align="left",
            bgcolor="rgba(255,255,255,0.8)",  # semi-transparent background
            bordercolor=colors[i],
            borderwidth=1,
            borderpad=2
        ))


    fig.update_layout(annotations=annotations)

    # X-axis settings
    fig.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext, tickangle=45)

    # Summary text
    latest = data.iloc[-1]
    summary = f"As of {latest['Date'].date()} | CMP: {latest['CMP']} | Sup: {latest['Support']} | Res: {latest['Resistance']} | PCR: {latest['PCR']} | Strk Price: {latest['strikePrice']}"

    return fig, summary


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
