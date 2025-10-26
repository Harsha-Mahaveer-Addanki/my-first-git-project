import pandas as pd
import os
import numpy as np

printstr = "\n===============>"

def is_file_locked(filepath):
    """Check if a file is open/locked by another process (e.g., Excel)."""
    if not os.path.exists(filepath):
        return False  # File doesn't exist, so it's not locked

    try:
        # Try opening for append (no truncation)
        with open(filepath, "a"):
            return False  # If success, not locked
    except PermissionError:
        return True  # Locked by another process

def Creat_fullReport_and_trendAnalysis(fp, past_days=3):

    df = pd.read_csv(fp, parse_dates=["Date"], date_format="%d-%b-%y")
    fpa = fp.replace(".csv", "_trend_analysis_All.csv")

    # Ensure data is sorted by Symbol and Date
    df.sort_values(by=["Symbol", "Date"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Define columns to analyze
    #cols = ["CMP", "strikePrice", "Support", "Resistance", "PCR", "RSI",	"MACD",	"MACD_Signal",	"MACD_Hist", 	"BB_HI", 
    #        	"BB_MID", 	"BB_LO"]
    cols = df.columns.to_list()
    new_cols = []
    # Group by Symbol and compute difference
    for col in cols[4:]:
#        if col in ["CMP", "Support", "Resistance", "BB_HI", "BB_MID", "BB_LO" ]:
        df[col + "_chg"] = df.groupby("Symbol")[col].diff(past_days)
        new_cols.append(col + "_chg")
        # Percentage difference over 3 rows
        df[col + "_pct_chg"] = df.groupby("Symbol")[col].transform(lambda x: x.diff(past_days) / x.shift(past_days) * 100)
        new_cols.append(col + "_pct_chg")
    # Convert diff to trend labels
        df[col + "_trend"] = df[col + "_chg"].apply(lambda x: "up" if x > 0 else ("down" if x < 0 else "unchanged"))
        new_cols.append(col + "_trend")

    # --- Define conditions ---
    conditions = [
        (df["Resistance"] > df["BB_HI"]) & (df["Support"] > df["BB_HI"]),
        (df["Resistance"] < df["BB_LO"]) & (df["Support"] < df["BB_LO"]),
        (df["Resistance"] > df["BB_HI"]) & (df["Support"] < df["BB_LO"]),
        (df["Resistance"] < df["BB_HI"]) & (df["Support"] > df["BB_LO"]),
        (df["Resistance"] > df["BB_HI"]) & (df["Support"].between(df["BB_MID"], df["BB_HI"])),
        (df["Resistance"] < df["BB_MID"]) & (df["Support"].between(df["BB_LO"], df["BB_MID"])),
        (df["Resistance"] > df["BB_MID"]) & (df["Support"] < df["BB_MID"]),
    ]

    choices = [
        "Strong Uptrend (Both Above BB_HI)",
        "Strong Downtrend (Both Below BB_LO)",
        "Volatile Wide Range (BB within Res-Support)",
        "Consolidation (Res-Sup Inside BB Range)",
        "Moderate Uptrend (Sup Near BB_MID to BB_HI)",
        "Moderate Downtrend (Sup Near BB_LO to BB_MID)",
        "Neutral (BB_MID Between Res-Sup)",
    ]

    df["BB-FnO"] = np.select(conditions, choices, default="Mixed / Undefined")
    """
    trend_map = {
        "Strong Uptrend (Both Above BB_HI)": 3,
        "Moderate Uptrend (Sup Near BB_MID to BB_HI)": 2,
        "Neutral (BB_MID Between Res-Sup)": 1,
        "Consolidation (Res-Sup Inside BB Range)": 0,
        "Moderate Downtrend (Sup Near BB_LO to BB_MID)": -2,
        "Strong Downtrend (Both Below BB_LO)": -3,
        "Volatile Wide Range (BB within Res-Support)": 99
    }

    df["Trend_Code"] = df["BB-FnO"].map(trend_map)
    """
    cols.append("BB-FnO")
    print(cols)
 
    final_order = []
    for c in cols:
        final_order.append(c)
        if f"{c}_trend" in df.columns:
            if c in ["CMP", "Support", "Resistance", "BB_HI", "BB_MID", "BB_LO" ]:
                final_order.append(f"{c}_chg")
                final_order.append(f"{c}_pct_chg")
            final_order.append(f"{c}_trend")
    
    print(final_order)

    df = df[final_order].round(2)

    while True:
        if is_file_locked(fpa):
            input(f"\033[97;41mFile '{fp}' is open in another program! \nClose it before running the script & press enter\033[0m")
        else:
            print("✅ File is free to write.")
            break

    print(f"{printstr} Writing into the file {fpa}")
    df.to_csv(fpa, mode='w', header=True, index=False)
    print(f"{printstr} Completed Writing\n")

    del df, cols, final_order, fpa, fp

if __name__ == "__main__":
    past_days = 2
    Creat_fullReport_and_trendAnalysis("AllFnOStocks_Opc.csv", past_days=past_days)