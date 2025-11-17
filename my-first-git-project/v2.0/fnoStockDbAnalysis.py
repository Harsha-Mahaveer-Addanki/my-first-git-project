import sqlite3, datetime, random, os
import pandas as pd
from util_lib import print_msg

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

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

def Create_report(df):
    fp = os.path.join(os.getcwd(), "AllFnOStocks_Opc_above_Below_analysis.csv")
    mode, header = "w", True
    
    while True:
        if is_file_locked(fp):
            input(f"\033[97;41mFile '{fp}' is open in another program! \nClose it before running the script & press enter\033[0m")
        else:
            print("✅ File is free to write.")
            break

    df.to_csv(fp, mode=mode, index=False, header=header)
    del fp, df
    return

def condCheck(below_cmp, above_cmp, combined):
    ss = 0
    conditions = [
        below_cmp['Puts_W'] > above_cmp['Call_L'],
        below_cmp['Call_W'] < above_cmp['Call_W'],
        below_cmp['Puts_W'] > above_cmp['Puts_W'],
        above_cmp["Call_B"] > below_cmp['Call_B'],
        (combined["Call_B"] + combined["Call_S"] + combined["Puts_W"] + combined["Puts_L"]) > (combined["Call_W"] + combined["Call_L"] + combined["Puts_B"] + combined["Puts_S"]),
        (combined["Call_B"] + combined["Puts_W"]) > (combined["Call_S"] + combined["Puts_L"]),
        combined["Puts_W"] > combined["Call_B"],
        combined["Puts_W"] > combined["Puts_B"],
        combined["Call_B"] > combined["Call_W"]
    ]

    ss += sum(conditions)
    return ss

def getPct(val, ts):
    return round(100* val/ts) #, 2)

def stats_pct(below_cmp, above_cmp, combined):
    stats = {}

    stats["pB_CB"] = getPct(below_cmp["Call_B"], below_cmp["Tot_Strikes"])
    stats["pB_CS"] = getPct(below_cmp["Call_S"], below_cmp["Tot_Strikes"])
    stats["pB_PW"] = getPct(below_cmp["Puts_W"], below_cmp["Tot_Strikes"])
    stats["pB_PL"] = getPct(below_cmp["Puts_L"], below_cmp["Tot_Strikes"])
    
    stats["pB_CW"] = getPct(below_cmp["Call_W"], below_cmp["Tot_Strikes"])
    stats["pB_CL"] = getPct(below_cmp["Call_L"], below_cmp["Tot_Strikes"])
    stats["pB_PB"] = getPct(below_cmp["Puts_B"], below_cmp["Tot_Strikes"])
    stats["pB_PS"] = getPct(below_cmp["Puts_S"], below_cmp["Tot_Strikes"])
    stats["B_Ts"]  = below_cmp["Tot_Strikes"]

    stats["pA_CB"] = getPct(above_cmp["Call_B"], above_cmp["Tot_Strikes"])
    stats["pA_CS"] = getPct(above_cmp["Call_S"], above_cmp["Tot_Strikes"])
    stats["pA_PW"] = getPct(above_cmp["Puts_W"], above_cmp["Tot_Strikes"])
    stats["pA_PL"] = getPct(above_cmp["Puts_L"], above_cmp["Tot_Strikes"])
    
    stats["pA_CW"] = getPct(above_cmp["Call_W"], above_cmp["Tot_Strikes"])
    stats["pA_CL"] = getPct(above_cmp["Call_L"], above_cmp["Tot_Strikes"])
    stats["pA_PB"] = getPct(above_cmp["Puts_B"], above_cmp["Tot_Strikes"])
    stats["pA_PS"] = getPct(above_cmp["Puts_S"], above_cmp["Tot_Strikes"])
    stats["A_Ts"]  = above_cmp["Tot_Strikes"]

    stats["p_CB"] = getPct(combined["Call_B"], combined["Tot_Strikes"])
    stats["p_CS"] = getPct(combined["Call_S"], combined["Tot_Strikes"])
    stats["p_PW"] = getPct(combined["Puts_W"], combined["Tot_Strikes"])
    stats["p_PL"] = getPct(combined["Puts_L"], combined["Tot_Strikes"])
    
    stats["p_CW"] = getPct(combined["Call_W"], combined["Tot_Strikes"])
    stats["p_CL"] = getPct(combined["Call_L"], combined["Tot_Strikes"])
    stats["p_PB"] = getPct(combined["Puts_B"], combined["Tot_Strikes"])
    stats["p_PS"] = getPct(combined["Puts_S"], combined["Tot_Strikes"])
    stats["Ts"]  = combined["Tot_Strikes"]

    return stats

def statsCheck(stats):
    ss = 0
    conditions = [
        stats["pA_CB"] > stats["pA_CW"],
        stats["pB_CB"] > stats["pB_CW"],   
        stats["pA_CS"] > stats["pA_CL"],
        stats["pB_CS"] > stats["pB_CL"],
        stats["pA_PB"] < stats["pA_PW"],
        stats["pB_PB"] < stats["pB_PW"],
        stats["pA_PS"] > stats["pA_PL"],
        stats["pB_PS"] > stats["pB_PL"],
        stats["p_CB"] > stats["p_CW"],
        stats["p_CS"] > stats["p_CL"],
        stats["p_PB"] < stats["p_PW"],
        stats["p_PS"] > stats["p_PL"],
    ]
    ss += sum(conditions)
    return ss

def safe_agg(df, col_change, col_oi, cond):
    """Return (count, sum) safely even if df is empty."""
    sub = df.loc[cond]
    count = len(sub)
    oi_sum = sub[col_oi].sum()

    if pd.isna(oi_sum):
        oi_sum = 0

    return count, oi_sum


def getStats(df):

    Call_B = safe_agg(df, 'CE.change', 'CE.openInterest',
                      (df['CE.changeinOpenInterest'] > 0) & (df['CE.change'] > 0))

    Call_S = safe_agg(df, 'CE.change', 'CE.openInterest',
                      (df['CE.changeinOpenInterest'] < 0) & (df['CE.change'] > 0))

    Puts_W = safe_agg(df, 'PE.change', 'PE.openInterest',
                      (df['PE.changeinOpenInterest'] > 0) & (df['PE.change'] < 0))

    Puts_L = safe_agg(df, 'PE.change', 'PE.openInterest',
                      (df['PE.changeinOpenInterest'] < 0) & (df['PE.change'] < 0))


    Call_W = safe_agg(df, 'CE.change', 'CE.openInterest',
                      (df['CE.changeinOpenInterest'] > 0) & (df['CE.change'] < 0))

    Call_L = safe_agg(df, 'CE.change', 'CE.openInterest',
                      (df['CE.changeinOpenInterest'] < 0) & (df['CE.change'] < 0))

    Puts_B = safe_agg(df, 'PE.change', 'PE.openInterest',
                      (df['PE.changeinOpenInterest'] > 0) & (df['PE.change'] > 0))

    Puts_S = safe_agg(df, 'PE.change', 'PE.openInterest',
                      (df['PE.changeinOpenInterest'] < 0) & (df['PE.change'] > 0))


    return {
        "Call_B": Call_B[0],
        "Call_S": Call_S[0],
        "Puts_W": Puts_W[0],
        "Puts_L": Puts_L[0],

        "Call_W": Call_W[0],
        "Call_L": Call_L[0],
        "Puts_B": Puts_B[0],
        "Puts_S": Puts_S[0],

        "Call_B_OI": Call_B[1],
        "Call_S_OI": Call_S[1],
        "Puts_W_OI": Puts_W[1],
        "Puts_L_OI": Puts_L[1],

        "Call_W_OI": Call_W[1],
        "Call_L_OI": Call_L[1],
        "Puts_B_OI": Puts_B[1],
        "Puts_S_OI": Puts_S[1],

        "Tot_Strikes": len(df['strikePrice']),
    }

def oiStatsCheck(stats):
    ss = 0
    conditions = [
        stats["A_Call_B_OI"] > stats["A_Call_W_OI"],
        stats["B_Call_B_OI"] > stats["B_Call_W_OI"],   
        stats["A_Call_S_OI"] > stats["A_Call_L_OI"],
        stats["B_Call_S_OI"] > stats["B_Call_L_OI"],
        stats["A_Puts_B_OI"] < stats["A_Puts_W_OI"],
        stats["B_Puts_B_OI"] < stats["B_Puts_W_OI"],
        stats["A_Puts_S_OI"] > stats["A_Puts_L_OI"],
        stats["B_Puts_S_OI"] > stats["B_Puts_L_OI"],
    ]
    ss += sum(conditions)
    return ss    

def analyzeSymbolOpc(symbol, df):
    cmp = 0
    below_cmp = above_cmp = combined = stats = allDict = {}

    cmp = df['CE.underlyingValue'].dropna().iloc[0]
    
    below_cmp = getStats(df[df.strikePrice < cmp].tail(5))
    above_cmp = getStats(df[df.strikePrice > cmp].head(5))
    combined = getStats(df)

    ss = condCheck(below_cmp, above_cmp, combined)
    stats = stats_pct(below_cmp, above_cmp, combined)
    ss_pct = statsCheck(stats)

    below_cmp = {f"B_{k}": v for k, v in below_cmp.items()}
    above_cmp = {f"A_{k}": v for k, v in above_cmp.items()}

    allDict =  {
            **{k: below_cmp[k] for k in list(below_cmp)[-9:]},
            **{k: above_cmp[k] for k in list(above_cmp)[-9:]},
            } 

    ss_oi = oiStatsCheck(allDict)

    td = {"Date" : df.Date.iloc[0],
            "Symbol" : symbol,
            "Type" : "Holding" if symbol in HLDNGS else "Non-Hld", 
            "Sentiment" : ss,
            "Senti_pct" : ss_pct,
            "Senti_oi" : ss_oi,
            } 
    
    return td #| allDict


if __name__ == "__main__":

    displayHdrs = ['Date', 'Symbol', 'CE.openInterest', 
                'CE.changeinOpenInterest', 'CE.totalTradedVolume', 
                'CE.lastPrice', 'CE.change', 'strikePrice', 'PE.openInterest', 'PE.changeinOpenInterest', 
                'PE.totalTradedVolume', 'PE.lastPrice', 'PE.change', 'CE.underlyingValue']
    HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]

    DB, TABLE = "NSE_FnO_Stocks_OPC.db", "FnO_Option_Chain"

    TODAY = datetime.datetime.now().strftime("%d-%b-%Y")
    # 1) Read full table (or restricted date-range for performance)
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE};", conn)[displayHdrs]
    conn.close()

    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.sort_values(['Date', 'Symbol','strikePrice'])
    AllList = df.Symbol.unique().tolist()
    AllDates = df.Date.unique().tolist()

    fullList = []
    for symnum, symbol in enumerate(AllList, start=1):
        for date in AllDates:
            sdf = df[(df.Symbol == symbol) & (df.Date == date)]
            fullList.append(analyzeSymbolOpc(symbol, sdf)) 
        print_msg("info", f"Done with Symbol {symnum:>5} {symbol:<15}")

    Create_report(pd.DataFrame(fullList).sort_values(['Date', 'Symbol']))
