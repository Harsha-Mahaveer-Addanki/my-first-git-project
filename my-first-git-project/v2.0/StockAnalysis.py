import pandas as pd
from util_lib import eq_func, print_msg
from nsepython import nsesymbolpurify
from datetime import datetime
from time import sleep
from tqdm import tqdm
from multiprocessing import Pool
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
import sys, os, sqlite3
from jugaad_data.nse import NSELive

past_days = 2

def calc_rsi(df):
    return RSIIndicator(df["Close"], window=14).rsi().tail(past_days)

def calc_macd(df, slow, fast, sign):
    macd = MACD(df["Close"], window_slow=slow, window_fast=fast, window_sign=sign)
    macd_df = pd.concat([macd.macd().tail(past_days), macd.macd_signal().tail(past_days), macd.macd_diff().tail(past_days)], axis=1)
    return macd_df

def calc_bb_hi(df):
    return BollingerBands(df["Close"], window=20, window_dev=2).bollinger_hband().tail(past_days)

def calc_bb_mid(df):
    return BollingerBands(df["Close"], window=20, window_dev=2).bollinger_mavg().tail(past_days)

def calc_bb_lo(df):
    return BollingerBands(df["Close"], window=20, window_dev=2).bollinger_lband().tail(past_days)

def getMarketData(symbol):
    symbol = 'M&M' if symbol == 'M%26M' else symbol
    max_retries = 2
    attempt = 0
    while attempt < max_retries:
         try:     
            pbar = tqdm(total=4, desc="Pipeline Progress", unit="step", leave=False)
            df = eq_func(symbol)
            pbar.update(1)

            # --- Multiprocessing for indicators ---
            tasks = [
                    (calc_rsi, df),
                    (calc_macd, df, slow, fast, sign),
                    (calc_bb_hi, df),
                    (calc_bb_mid, df),
                    (calc_bb_lo, df),
            ]

            results = []
            with Pool(processes=len(tasks)) as pool:
                    for t in tasks:
                            func = t[0]
                            args = t[1:]
                            results.append(pool.apply(func, args=args))
            pbar.update(1)

            dfc = pd.concat(results, axis=1).round(2)
            #dfc["Dist_from_BB_HI"] = dfc.apply(lambda x: round(((x["BB_HI"] - df["Close"].iloc[-1])/df["Close"].iloc[-1])*100, 2))
            #dfc["Dist_from_BB_LO"] = dfc.apply(lambda x: round(((df["Close"].iloc[-1] - x["BB_LO"])/x["BB_LO"])*100, 2))

            last_close = df["Close"].iloc[-1]

            dfc["Dist_from_BB_HI"] = ((dfc["hband"] - last_close) / last_close * 100).round(2)
            dfc["Dist_from_BB_LO"] = ((last_close - dfc["lband"]) / dfc["lband"] * 100).round(2)

            pbar.update(1)
            del symbol, df, tasks, pbar, results, 
            return dfc.iloc[-1].to_dict()
         except Exception as e:
            attempt += 1
            if attempt < max_retries:
                print_msg(type="warn", msg=f"{attempt} in function getMarketData() Failed with symbol {symbol} {e}. Retrying")
                sleep(5 * (2 ** attempt))
            else:
                print_msg(type="fail", msg=f"Max tries of {max_retries} reached in function getMarketData(). Seeing Error: {e}. Exiting")
                return {}        


def analyze_row(row):

    # 1️⃣ Overall activity comparison
    if (row["Call_B"] + row["Call_S"] + row["Puts_W"] + row["Puts_L"]) > (row["Call_W"] + row["Call_L"] + row["Puts_B"] + row["Puts_S"]):
        # 2️⃣ Buying/Writing balance
        if (row["Call_B"] + row["Puts_W"]) > (row["Call_S"] + row["Puts_L"]):
            # 3️⃣ Put writing vs Call buying
            if row["Puts_W"] > row["Call_B"]:
                sentiment_score = "6 - Very Bullish"
            else:
                sentiment_score = "5 - Bullish"
        else:
            sentiment_score = "4 - Mild Bullish"
    else:
        if (row["Call_B"] + row["Puts_W"]) > (row["Call_S"] + row["Puts_L"]):
            # 3️⃣ Put writing vs Call buying
            if row["Puts_W"] > row["Call_B"]:
                sentiment_score = "3 - Mild Bearish"
            else:
                sentiment_score = "2 - Bearish"
        else:
            sentiment_score = "1 - Very Bearish"

    return sentiment_score


def getOptionChainData(symbol, conn, cursor):
    max_retries = 2
    attempt = 0
    while attempt < max_retries:
         try:
            with tqdm(total=3, desc="Pipeline Progress", unit="step", leave=False) as pbar:
                #symbol = nsesymbolpurify(symbol=symbol)
                opcdata = NL.equities_option_chain(symbol)
                pbar.update(1)

                df = pd.json_normalize(opcdata['filtered']['data'])

                dbdf = df.copy()
                dbdf['Symbol'] = symbol
                dbdf['Date'] = formatted_date

                # Write to temporary table
                dbdf[hd_list].to_sql("temp_table", conn, if_exists='replace', index=False)

                # Insert only new rows into main table
                cursor.execute(f'''
                    INSERT OR IGNORE INTO {table_name}
                    SELECT * FROM temp_table
                ''')
                conn.commit()
                pbar.update(1)

                Call_B = ((df['CE.changeinOpenInterest'] > 0) & (df['CE.change'] > 0)).sum()
                Call_S = ((df['CE.changeinOpenInterest'] < 0) & (df['CE.change'] > 0)).sum()
                Puts_W = ((df['PE.changeinOpenInterest'] > 0) & (df['PE.change'] < 0)).sum()
                Puts_L = ((df['PE.changeinOpenInterest'] < 0) & (df['PE.change'] < 0)).sum()
                
                Call_W = ((df['CE.changeinOpenInterest'] > 0) & (df['CE.change'] < 0)).sum()
                Call_L = ((df['CE.changeinOpenInterest'] < 0) & (df['CE.change'] < 0)).sum()
                Puts_B = ((df['PE.changeinOpenInterest'] > 0) & (df['PE.change'] > 0)).sum()
                Puts_S = ((df['PE.changeinOpenInterest'] < 0) & (df['PE.change'] > 0)).sum()

                row = {
                    "Call_B":   Call_B,
                    "Call_S":   Call_S,
                    "Puts_W":   Puts_W,
                    "Puts_L":   Puts_L,
                    
                    "Call_W":   Call_W,
                    "Call_L":   Call_L,
                    "Puts_B":   Puts_B,
                    "Puts_S":   Puts_S,
                }

                sentDict = {
                    "Sentiment" : analyze_row(row),
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
                del row

                df = df[hdl]
                df.dropna(subset=["PE.openInterest", "CE.openInterest"], inplace=True)
                df = df[(df["PE.openInterest"] != 0) & (df["PE.lastPrice"] != 0) & (df["CE.openInterest"] != 0) & (df["CE.lastPrice"] != 0)]
                df.loc[:, "TotalOI"] = df.loc[:, "PE.openInterest"] + df.loc[:, "CE.openInterest"]
                max_row = df.loc[df['TotalOI'].idxmax()].copy().to_dict()
                max_row["Date"] = formatted_date
                max_row["expiryDate"] = opcdata['records']['expiryDates'][0]
                max_row["Symbol"] = symbol
                max_row["Type"] = "Holding" if symbol in HLDNGS else "Non-Hld"
                max_row["CMP"] = opcdata['records']['underlyingValue']
                max_row["Support"] = max_row['strikePrice'] - max_row["PE.lastPrice"] - max_row["CE.lastPrice"]
                max_row["Dist_from_Support"] = round(((max_row["CMP"] - max_row["Support"])/max_row["Support"])*100, 2)
                max_row["Resistance"] = max_row['strikePrice'] + max_row["PE.lastPrice"] + max_row["CE.lastPrice"]
                max_row["Dist_from_Resist"] = round(((max_row["Resistance"] - max_row["CMP"])/max_row["CMP"])*100, 2)
                max_row["PCR"] = opcdata['filtered']['PE']['totOI']/opcdata['filtered']['CE']['totOI']
                for key in ['PE.openInterest', 'CE.openInterest', 'PE.lastPrice', 'CE.lastPrice', 'TotalOI']:
                    max_row.pop(key, None)
                pbar.update(1)
                #print(max_row)
                del df, dbdf
                return max_row, sentDict
         
         except Exception as e:
            attempt += 1
            if attempt < max_retries:
                print_msg(type="warn", msg=f"{attempt} in function getOptionChainData() Failed with symbol {symbol} {e}. Retrying")
                sleep(5 * (2 ** attempt))
            else:
                print_msg(type="fail", msg=f"Max tries of {max_retries} reached in function getOptionChainData(). Seeing Error: {e}. Exiting")
                return {} , {}            

def print_delay(delay=5):
    print("Waiting", end="", flush=True)
    for i in range(delay):
        print(".", end="", flush=True)
        sleep(1)
    sys.stdout.write("\r" + " " * (len("Waiting") + delay) + "\r")
    sys.stdout.flush()    

def getFnOStkList():
    AllList = NL.live_fno()
    AllList = sorted([y['meta']['symbol'] for y in AllList['data'] ])
    return AllList

def Stock_All_Data_Analysis():


    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print_msg("info", f"\n✅ Connected to SQLite DB: {os.path.abspath(db_path)}")

    # ---------- Create table if not exists ----------
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        Date TEXT,
        Symbol TEXT,
        expiryDate TEXT,
        "CE.underlying" TEXT,
        "CE.openInterest" REAL,
        "CE.changeinOpenInterest" REAL,
        "CE.pchangeinOpenInterest" REAL,
        "CE.totalTradedVolume" REAL,
        "CE.impliedVolatility" REAL,
        "CE.lastPrice" REAL,
        "CE.change" REAL,
        "CE.pChange" REAL,
        "CE.underlyingValue" REAL,
        strikePrice REAL,
        "PE.openInterest" REAL,
        "PE.changeinOpenInterest" REAL,
        "PE.pchangeinOpenInterest" REAL,
        "PE.totalTradedVolume" REAL,
        "PE.impliedVolatility" REAL,
        "PE.lastPrice" REAL,
        "PE.change" REAL,
        "PE.pChange" REAL,
        "PE.underlyingValue" REAL,
        UNIQUE(Symbol, Date, strikePrice)
    )
    ''')
    conn.commit()

    # Add an index for faster lookups
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_symbol_date ON {table_name}(Symbol, Date)")
    conn.commit()


    AllList = getFnOStkList()
    FullDictList = []
    global headers_list
    print_msg(msg="\t\tTime Start: " + datetime.now().strftime("%H:%M:%S"))
    for symnum, symbol in enumerate(AllList, start=1):
        opcDict = mktDict = {}
        mktDict = getMarketData(symbol)
        opcDict, mySentDict = getOptionChainData(symbol=symbol, conn=conn, cursor=cursor)
        if not opcDict or not mktDict : continue
        FullDictList.append(opcDict | mktDict | mySentDict)
        print_msg(type="success", msg=f"Done with {symnum:>5} {symbol:<15}")
        if symnum != len(AllList) : print_delay(3)
    print_msg(msg="\t\tTime End: " + datetime.now().strftime("%H:%M:%S"))
    for k in mySentDict.keys():
        headers_list.append(k)
    del AllList, opcDict, mktDict
    conn.close()

    return FullDictList

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

def Create_report(FullDictList):
    Final_Df = pd.DataFrame(FullDictList).round(2)
    Final_Df.rename(columns=indicator_map, inplace=True)
    fp = os.path.join(os.getcwd(), "AllFnOStocks_Opc.csv")
    if os.path.exists(fp):
        mode, header = "a", False
    else:
        mode, header = "w", True
    
    while True:
        if is_file_locked(fp):
            input(f"\033[97;41mFile '{fp}' is open in another program! \nClose it before running the script & press enter\033[0m")
        else:
            print("✅ File is free to write.")
            break

    Final_Df[headers_list].to_csv(fp, mode=mode, index=False, header=header)
    del FullDictList, Final_Df
    return

if __name__ == "__main__":
    NL = NSELive()
    formatted_date = datetime.now().strftime("%d-%b-%Y")

    db_path = "NSE_FnO_Stocks_OPC.db"
    table_name = "FnO_Option_Chain"

    hdl = ['PE.openInterest', 'CE.openInterest', 'strikePrice', 'PE.lastPrice', 'CE.lastPrice']
    HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]
    headers_list = ["Date", "expiryDate", "Symbol", "Type", "CMP", "strikePrice", 
                    "Support", "Dist_from_Support", "Resistance", "Dist_from_Resist", "PCR",
                    "RSI", "MACD", "MACD_Signal", "MACD_Hist", "BB_HI", "BB_MID", "BB_LO"]    

    hd_list = ['Date', 'Symbol', 'expiryDate', 'CE.underlying', 'CE.openInterest', 'CE.changeinOpenInterest',
           'CE.pchangeinOpenInterest', 'CE.totalTradedVolume', 'CE.impliedVolatility', 'CE.lastPrice',
           'CE.change', 'CE.pChange', 'CE.underlyingValue', 'strikePrice', 'PE.openInterest',
           'PE.changeinOpenInterest', 'PE.pchangeinOpenInterest', 'PE.totalTradedVolume', 'PE.impliedVolatility',
           'PE.lastPrice', 'PE.change', 'PE.pChange', 'PE.underlyingValue']

    indicator_map = {
    "rsi": "RSI",
    "hband": "BB_HI",
    "mavg": "BB_MID",
    "lband": "BB_LO",
    "MACD_12_26": "MACD",
    "MACD_sign_12_26": "MACD_Signal",
    "MACD_diff_12_26": "MACD_Hist"
    }
    slow, fast, sign = 26, 12, 9

    finaldict = Stock_All_Data_Analysis()
    Create_report(finaldict)
