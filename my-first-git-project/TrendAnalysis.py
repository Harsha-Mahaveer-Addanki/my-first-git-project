import pandas as pd
import sys


# Sample data — you can read from CSV instead
df = pd.read_csv(sys.argv[1], parse_dates=["Date"], date_format="%d-%b-%y")
fp = sys.argv[1].replace(".csv", "_trend_analysis.csv")

# Ensure data is sorted by Symbol and Date
df.sort_values(by=["Symbol", "Date"], inplace=True)
df.reset_index(drop=True, inplace=True)

# Define columns to analyze
cols = ["RSI", "Support", "Resistance", "PCR"]

# Group by Symbol and compute difference
for col in cols:
    df[col + "_change"] = df.groupby("Symbol")[col].diff()
    # Convert diff to trend labels
    df[col + "_trend"] = df[col + "_change"].apply(lambda x: "up" if x > 0 else ("down" if x < 0 else "unchanged"))

trend_summary = df.groupby("Symbol").agg({
    "RSI_trend":        lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
    "Support_trend":    lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
    "Resistance_trend": lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
    "PCR_trend":        lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
    
})

trend_summary.reset_index(inplace=True)
print(trend_summary)

trend_summary.to_csv(fp, mode='w', header=True, index=False)