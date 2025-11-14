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

def getStats(df):
    Call_B = ((df['CE.changeinOpenInterest'] > 0) & (df['CE.change'] > 0)).sum()
    Call_S = ((df['CE.changeinOpenInterest'] < 0) & (df['CE.change'] > 0)).sum()
    Puts_W = ((df['PE.changeinOpenInterest'] > 0) & (df['PE.change'] < 0)).sum()
    Puts_L = ((df['PE.changeinOpenInterest'] < 0) & (df['PE.change'] < 0)).sum()
    
    Call_W = ((df['CE.changeinOpenInterest'] > 0) & (df['CE.change'] < 0)).sum()
    Call_L = ((df['CE.changeinOpenInterest'] < 0) & (df['CE.change'] < 0)).sum()
    Puts_B = ((df['PE.changeinOpenInterest'] > 0) & (df['PE.change'] > 0)).sum()
    Puts_S = ((df['PE.changeinOpenInterest'] < 0) & (df['PE.change'] > 0)).sum()

    return {
        "Call_B":   Call_B,
        "Call_S":   Call_S,
        "Puts_W":   Puts_W,
        "Puts_L":   Puts_L,
        
        "Call_W":   Call_W,
        "Call_L":   Call_L,
        "Puts_B":   Puts_B,
        "Puts_S":   Puts_S,

        "Tot_Strikes": len(df['strikePrice']),
    }

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

def analyzeSymbolOpc(symbol, df):
    cmp = df['CE.underlyingValue'].dropna().iloc[0]
    
    below_cmp = getStats(df[df.strikePrice < cmp])
    above_cmp = getStats(df[df.strikePrice > cmp])
    combined = {k: below_cmp[k] + above_cmp[k] for k in below_cmp}

    ss = condCheck(below_cmp, above_cmp, combined)

    return {"Symbol" : symbol,
            "Type" : "Holding" if symbol in HLDNGS else "Non-Hld", 
            "Sentiment" : ss
            }

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
    df = pd.read_sql_query(f"SELECT * FROM {TABLE} WHERE Date = \'{TODAY}\';", conn)[displayHdrs]
    conn.close()

    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.sort_values(['Date', 'Symbol','strikePrice'])
    AllList = df.Symbol.unique().tolist()

    fullList = []
    for symnum, symbol in enumerate(AllList, start=1):
        
        fullList.append(analyzeSymbolOpc(symbol, df[df.Symbol == symbol]))
        #print_msg("info", f"Done with Symbol {symnum:>5} {symbol:<15}")  

    Create_report(pd.DataFrame(fullList).sort_values(['Sentiment'], ascending=False))
