import datetime as dt

import pandas as pd
import math,time,os
from nsepython import nse_optionchain_scrapper, fnolist, nsesymbolpurify
from tqdm import tqdm
import gc
pd.set_option('display.max_columns', None)
import concurrent.futures

def run_with_timeout(func, timeout=10, *args, **kwargs):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            print("Timeout! Skipping...")
            return -1

# Format as dd-MMM-yyyy
formatted_date = dt.datetime.now().strftime("%d-%b-%Y")

# Initialize an empty DataFrame
whole_df = pd.DataFrame()

# List of current Holdings
HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]

def print_msg(type="SUCCESS", msg=""):
     if type.lower() == "success":
          print(f"\033[32m{msg}\033[0m")
     elif type.lower() == "fail":
          print(f"\033[97;41m{msg}\033[0m")
     elif type.lower() == "warn":
          print(f"\033[93;44m{msg}\033[0m")

def collect_opc_data(symbol) :
     max_retries = 2
     attempt = 0
     while attempt < max_retries:
           try:
                 with tqdm(total=4, desc="Pipeline Progress", unit="step", leave=False) as pbar:
                       global whole_df
                       
                       opcdata = nse_optionchain_scrapper(symbol)
                       pbar.update(1)

                       df = pd.json_normalize(opcdata['filtered']['data'])[['PE.openInterest', 'CE.openInterest', 'strikePrice', 'PE.lastPrice', 'CE.lastPrice']]
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

                       df = pd.DataFrame(max_row, index=[0])
                       pbar.update(1)

                       whole_df = pd.concat([whole_df, df], ignore_index=True).round(2)
                       pbar.update(1)
                       del max_row
                       del df
                       gc.collect()
                       pbar.update(1)
                       return "Success"
		    
           except Exception as e:
                 attempt += 1
                 if attempt < max_retries:
                       print_msg(type="warn", msg=f"{attempt} Failed with symbol {symbol} {e}. Retrying")
                       time.sleep(5 * (2 ** attempt))
                 else:
                       print_msg(type="fail", msg=f"Max tries of {max_retries} reached. Seeing Error: {e}. Exiting")
                       return "Fail"

def Creat_fullReport_and_trendAnalysis(fp):
    global whole_df
    print(f"{printstr} Writing into the file {fp}")
    whole_df = whole_df[headers_list]
    whole_df.to_csv(fp, mode=md, header=header, index=False)
    print(f"{printstr} Completed Writing\n")

    df = pd.read_csv(fp, parse_dates=["Date"], date_format="%d-%b-%y")
    fpa = fp.replace(".csv", "_trend_analysis.csv")

    # Ensure data is sorted by Symbol and Date
    df.sort_values(by=["Symbol", "Date"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Define columns to analyze
    cols = ["CMP", "strikePrice", "Support", "Resistance", "PCR"]

    # Group by Symbol and compute difference
    for col in cols:
        df[col + "_change"] = df.groupby("Symbol")[col].diff(3)
    
        # Percentage difference over 3 rows
        df[col + "_pct_change"] = df.groupby("Symbol")[col].transform(lambda x: x.diff(3) / x.shift(3) * 100)
        
        # Convert diff to trend labels
        df[col + "_trend"] = df[col + "_change"].apply(lambda x: "up" if x > 0 else ("down" if x < 0 else "unchanged"))
    """
    trend_summary = df.groupby("Symbol").agg({
        "Support_trend":    lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
        "Resistance_trend": lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
        "PCR_trend":        lambda x: "up" if all(v=="up" for v in x[1:]) else ("down" if all(v=="down" for v in x[1:]) else "mixed"),
        
    })

    trend_summary.reset_index(inplace=True)
    #print(trend_summary)
    """
    print(f"{printstr} Writing into the file {fpa}")
    df.to_csv(fpa, mode='w', header=True, index=False)
    print(f"{printstr} Completed Writing\n")

    del whole_df
    del df
    gc.collect()



headers_list = ["Date", "expiryDate", "Symbol", "Type", "CMP", "strikePrice", 
                "Support", "Dist_from_Support", "Resistance", "Dist_from_Resist", "PCR"]
symbols, file_name, printstr = [], "", "\n--------------->>>>"

while True:
    ip = input(f"{printstr} Select: 1 - Holdings Symbols, 2 - All FnO Symbols, 3 - 300 Stocks (Nifty200, MidCap 100, SmallCap 100): ")
    if ip.strip() == "":
         print_msg(type="Warn", msg=f"{printstr} Wrong Selection.\n")
    elif 1 == int(ip):
        print(f"{printstr} Selected Holdings")
        symbols, file_name = HLDNGS.copy(), "MyHoldings_Opc.csv"
        break
    elif 2 == int(ip):
        print(f"{printstr} Selected All FnO Symbols")
        symbols, file_name = sorted(fnolist()), "AllFnOStocks_Opc.csv"
        symbols.remove('NIFTY')
        symbols.remove('NIFTYIT')
        symbols.remove('BANKNIFTY')        
        break
    elif 3 == int(ip):
        print(f"{printstr} 300 Stocks (Nifty200, MidCap 100, SmallCap 100)")
        from allIndices import AllList
        symbols, file_name = sorted(set(fnolist()) | set(AllList)) , "Nifty200_MidCap100_SmallCap100.csv"
        symbols.remove('NIFTY')
        symbols.remove('NIFTYIT')
        symbols.remove('BANKNIFTY')
        break
    else:
        print_msg(type="Warn", msg=f"{printstr} Wrong Selection.\n")

if os.name == 'nt':
    fp = os.getcwd() +"\\"+file_name
elif os.name == 'posix':
    fp = os.getcwd() +"/"+file_name
else:
    print("unknown OS. Change code to use this")
    exit(0)

fast, slow, sign = 12, 26, 9

while True:
    ip = input(f"{printstr} Select MACD: 1 - 12,29,9 ---- 2 - 50,200,25 : ")
    if ip.strip() == "":
         print_msg(type="Warn", msg=f"{printstr} Wrong Selection.\n")
    elif 1 == int(ip):
        print(f"{printstr} Selected MACD(12,26,9)")
        days = 365
        break
    elif 2 == int(ip):
        print(f"{printstr} Selected MACD(50,200,25)")
        fast, slow, sign, days = 50, 200, 25, 1000
        fp = fp.replace(".csv", "_MACD_50_200_25.csv")
        break
    else:
        print_msg(type="Warn", msg=f"{printstr} Wrong Selection.\n")

md, header = 'w', True

while True:
    if os.path.exists(fp):
        ip=input(f"{printstr} File {fp} exists.\n\nDefault is Overwrite. Select 1 - to just append , 2 - to create a new file with timestamp: ")

        if  os.access(fp, os.W_OK) != True:
             print_msg(type="fail", msg=f"File Permission Denied. Check if the file {fp} is open somwwhere")

        if ip.strip() == "":
             break
        elif int(ip) == 1:
            md, header = 'a', False
            break
        elif int(ip) == 2:
            fp = fp.replace(".csv", "_" + dt.datetime.now().strftime("%d-%b-%Y-%H-%M-%S") + ".csv")
            break
        else:
            print_msg(type="Warn", msg=f"{printstr} Wrong Selection.\n")
    else:
         print(f"{printstr} File {fp} doesnt exist. Will create it after processing the data\n")
         break

os.system('')
print(f"{printstr} Found total {len(symbols)} Symbols.\n")

# Current time with hours:minutes:seconds
print("\n\t\tTime Start: " + dt.datetime.now().strftime("%H:%M:%S") + "\n")

for symnum, symbol in enumerate(symbols, start=1):
    symbol=nsesymbolpurify(symbol)
    x = run_with_timeout(collect_opc_data, symbol=symbol)
    x == "Success" and print_msg(type="success", msg=f"Done with symbol {symnum:>4} {symbol}")
    time.sleep(2)

Creat_fullReport_and_trendAnalysis(fp)

print(dt.datetime.now().strftime("%H:%M:%S"))