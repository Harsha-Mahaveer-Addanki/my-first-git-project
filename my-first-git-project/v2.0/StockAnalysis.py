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
import sys, os
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
     
def getOptionChainData(symbol):
    max_retries = 2
    attempt = 0
    while attempt < max_retries:
         try:
            with tqdm(total=2, desc="Pipeline Progress", unit="step", leave=False) as pbar:
                #symbol = nsesymbolpurify(symbol=symbol)
                opcdata = NL.equities_option_chain(symbol)
                pbar.update(1)

                df = pd.json_normalize(opcdata['filtered']['data'])[hdl]
                df.dropna(subset=["PE.openInterest", "CE.openInterest"], inplace=True)
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
                return max_row
         
         except Exception as e:
            attempt += 1
            if attempt < max_retries:
                print_msg(type="warn", msg=f"{attempt} in function getOptionChainData() Failed with symbol {symbol} {e}. Retrying")
                sleep(5 * (2 ** attempt))
            else:
                print_msg(type="fail", msg=f"Max tries of {max_retries} reached in function getOptionChainData(). Seeing Error: {e}. Exiting")
                return {}             

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
    AllList = getFnOStkList()
    FullDictList = []
    print_msg(msg="\t\tTime Start: " + datetime.now().strftime("%H:%M:%S"))
    for symnum, symbol in enumerate(AllList, start=1):
        opcDict = mktDict = {}
        opcDict = getOptionChainData(symbol=symbol)
        mktDict = getMarketData(symbol)
        if not opcDict or not mktDict : continue
        FullDictList.append(opcDict | mktDict)
        print_msg(type="success", msg=f"Done with {symnum:>5} {symbol:<15}")
        if symnum != len(AllList) : print_delay()
    print_msg(msg="\t\tTime End: " + datetime.now().strftime("%H:%M:%S"))
    del AllList, opcDict, mktDict
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
    hdl = ['PE.openInterest', 'CE.openInterest', 'strikePrice', 'PE.lastPrice', 'CE.lastPrice']
    HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]
    headers_list = ["Date", "expiryDate", "Symbol", "Type", "CMP", "strikePrice", 
                    "Support", "Dist_from_Support", "Resistance", "Dist_from_Resist", "PCR",
                    "RSI", "MACD", "MACD_Signal", "MACD_Hist", "BB_HI", "BB_MID", "BB_LO"]    
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
    ip = input()
    Create_report(finaldict)
