from datetime import datetime,timedelta,date

import pandas as pd
import math,time,os
from nsepython import nse_eq, nse_optionchain_scrapper, fnolist, nsesymbolpurify
from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
from jugaad_data.nse import stock_df
from ta.momentum import RSIIndicator
from ta.trend import MACD,EMAIndicator
from ta.volatility import BollingerBands
from datetime import date
from tqdm import tqdm
import gc

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
formatted_date = datetime.now().strftime("%d-%b-%Y")

# Initialize an empty DataFrame
whole_df = pd.DataFrame()

# List of current Holdings
HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]



# Define function for getting the symbol's PE and Book Value from Screener.in
# input arg : Symbol
# returns: pe and bv

def mcap_pe(scrip):
    SCRIP = scrip
    link = f'https://www.screener.in/company/{SCRIP}/#top'
    hdr = {'User-Agent':'Mozilla/5.0'}
    req = Request(link,headers=hdr)

    try:
        page=urlopen(req)
        soup = BeautifulSoup(page, "html.parser")

        div_html = soup.find('div',{'class': 'company-ratios'})
        ul_html = div_html.find('ul',{'id': 'top-ratios'})
        market_cap = 0.0

        for li in ul_html.find_all("li"):
            name_span = li.find('span',{'class':'name'})
            if 'Stock P/E' in name_span.text: 
                num_span = li.find('span',{'class':'number'})
                num_span = num_span.text.replace(',', '')
                stock_pe = float(num_span) if (num_span != '') else 0.0
            elif 'Book Value' in name_span.text: 
                num_span = li.find('span',{'class':'number'})
                num_span = num_span.text.replace(',', '')
                book_value = float(num_span) if (num_span != '') else 0.0
                break

        return stock_pe, book_value

    except Exception as e:
        print(f'EXCEPTION THROWN: UNABLE TO FETCH DATA FOR {SCRIP}: {e}')
        return 0

def cal_rsi_macd(hld, cls_prc_str='CLOSE'):
    global fast, slow, sign
    rmdf = pd.DataFrame()
    gc.collect()
    hld='M&M' if hld== 'M%26M' else hld
    rmdf = stock_df(symbol=hld, from_date=date(sd.year, sd.month, sd.day), to_date=date(ed.year, ed.month, ed.day), series="EQ")
    rmdf.sort_values(by='DATE',inplace=True)
	
	# Calculate 14-day RSI
    rsi_indicator = RSIIndicator(close=rmdf[cls_prc_str], window=14)
    rmdf['RSI'] = rsi_indicator.rsi()
		
	# Calculate MACD
    macd_indicator = MACD(
	    close=rmdf[cls_prc_str],
	    window_slow=slow,  # Default: 26-period Exponential Moving Average (EMA)
	    window_fast=fast,  # Default: 12-period EMA
	    window_sign=sign    # Default: 9-period EMA for the signal line
	)
    rmdf['MACD'] = macd_indicator.macd()
    rmdf['MACD_Signal'] = macd_indicator.macd_signal()
    rmdf['ema_20'] = EMAIndicator(rmdf[cls_prc_str], window=20).ema_indicator()
    rmdf['bbhi'] = BollingerBands(close=rmdf[cls_prc_str],window=20,window_dev=2).bollinger_hband()
    rmdf['bbli'] = BollingerBands(close=rmdf[cls_prc_str],window=20,window_dev=2).bollinger_lband()	
	#print(rmdf[[cls_prc_str, 'RSI', 'MACD', 'MACD_Signal']])
	#print(type(rmdf.iloc[-1].RSI))
    return rmdf.iloc[-1].RSI, rmdf.iloc[-1].MACD, rmdf.iloc[-1].MACD_Signal, rmdf.iloc[-1].bbhi, rmdf.iloc[-1].bbli, rmdf.iloc[-1].ema_20


def collect_opc_data(symbol) :
     max_retries = 1
     attempt = 0
     while attempt < max_retries:
           try:
                 with tqdm(total=6, desc="Pipeline Progress", unit="step", leave=False) as pbar:
                       global whole_df
                       
                       """
                       data = nse_eq(symbol)
                       pbar.update(1)
                       macro = data['industryInfo']['macro']
                       sector = data['industryInfo']['sector']
                       industry = data['industryInfo']['industry']
                       basicIndustry = data['industryInfo']['basicIndustry']
                       """
                       RSI, MACD, MACD_Signal, BBHi, BBLi, ema_20 = cal_rsi_macd(hld=symbol)
                       pbar.update(1)
                       
                       stock_pe_ratio, stock_bv = mcap_pe(symbol)
                       pbar.update(1)
                       
                       opcdata = nse_optionchain_scrapper(symbol)
                       pbar.update(1)
                       
                       records = opcdata['records']['data']
                       ltp = opcdata['records']['underlyingValue']
                       
                       if ltp < BBLi:
                            bb_analysis = "Below BBLi"
                       elif (ltp > BBLi) & (ltp < ema_20):
                            bb_analysis = "Close to BBLi"
                       elif (ltp > ema_20) & (ltp < BBHi):
                            bb_analysis = "Close to BBHi"
                       else:
                            bb_analysis = "Above BBHi"                       

                       chain_data = []
                       for item in records:
                                    expiry = item.get("expiryDate")
                                    if expiry != opcdata['records']['expiryDates'][0]:
                                         continue
                                    strike = item.get("strikePrice")
                                    

                                    ce = item.get("CE", {})
                                    pe = item.get("PE", {})

                                    ce_oi = 0 if ce.get("openInterest") == None else ce.get("openInterest")
                                    pe_oi = 0 if pe.get("openInterest") == None else pe.get("openInterest")
                                    CE_PE_Total = ce_oi + pe_oi

                                    clas = 0 if ce.get("lastPrice") == None else ce.get("lastPrice")
                                    plas = 0 if pe.get("lastPrice") == None else pe.get("lastPrice")
                                    Support = strike - (clas + plas)
                                    Resistance = strike + (clas + plas)
                                    Dist_from_Support = ((ltp - Support)/Support) * 100
                                    Dist_from_Resist = ((Resistance - ltp)/ltp) * 100
                                    comments = "OI or Premium is 0" if any(v==0 for v in [ce_oi, pe_oi, clas, plas]) else "Proper"	        

                                    chain_data.append({
                                         "Date" : formatted_date,
                                         "expiryDate": expiry,
                                         "Symbol" : symbol,
                                         "Type" : "Holding" if symbol in HLDNGS else "Non-Hld",
                                         "CMP" : ltp,
                                         "Stock PE" : stock_pe_ratio ,
                                         "BV-to-CMP" : ltp/stock_bv,
                                         "RSI" : RSI,
                                         "MACD" : MACD,
                                         "MACD_Signal" : MACD_Signal,
                                         "MACD_To_Signal" : MACD - MACD_Signal,
                                         "strikePrice": strike,
                                         "Comments" : comments,
                                         "CE_openInterest": ce_oi,
                                         #"CE_changeOI": ce.get("changeinOpenInterest"),
                                         #"CE_lastPrice": ce_ltp_at_strk,
                                         "PE_openInterest": pe_oi,
                                         #"PE_changeOI": pe.get("changeinOpenInterest"),
                                         #"PE_lastPrice": pe_ltp_at_strk,
                                         "CE_PE_Total": CE_PE_Total,
                                         "Support" : Support,
                                         "Dist_from_Support" : math.ceil(Dist_from_Support * 100)/100,
                                         "Resistance" : Resistance,
                                         "Dist_from_Resist" : math.ceil(Dist_from_Resist * 100)/100,
                                         #"PCR" : PCR,
                                         #"Macro": macro,
                                         #"Sector": sector,
                                         #"Industry": industry,
                                         #"Basic Industry": basicIndustry,
                                         #"BBHi" : BBHi,
                                         #"BBLi" : BBLi,
                                         "BB Analysis" : bb_analysis, 
                                    })

                       df = pd.DataFrame(chain_data)
                       pbar.update(1)
                       Total_Puts = df.PE_openInterest.sum()
                       Total_Calls = df.CE_openInterest.sum()

                       df.loc[df["CE_PE_Total"].idxmax(), "PCR"] = 0 if Total_Calls == 0 else Total_Puts/Total_Calls
                       df.dropna(inplace=True)
                       pbar.update(1)
                       whole_df = pd.concat([whole_df, df], ignore_index=True)
                       del chain_data
                       del df
                       gc.collect()
                       pbar.update(1)
                       return "Success"
		    
           except Exception as e:
                 attempt += 1
                 if attempt < max_retries:
                       print(f"{attempt} Failed with symbol {symbol} {e}. Retrying")
                 else:
                       print(f"Max tries of {max_retries} reached. Seeing Error: {e}. Exiting")
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
    #print(trend_summary)
    print(f"{printstr} Writing into the file {fpa}")
    trend_summary.to_csv(fpa, mode='w', header=True, index=False)
    print(f"{printstr} Completed Writing\n")

    del whole_df
    del df
    gc.collect()



headers_list = ["Date", "expiryDate", "Symbol", "Type", "CMP", "Stock PE", "BV-to-CMP", "RSI", 
                     "MACD", "MACD_Signal", "MACD_To_Signal", "BB Analysis", "strikePrice", "Comments",
                     "Support", "Dist_from_Support", "Resistance", "Dist_from_Resist", "PCR"]
symbols=[]
file_name = ""
printstr = "\n--------------->>>>"
while True:
    ip = input(f"{printstr} Select: 1 - Holdings Symbols, 2 - All FnO Symbols : ")
    if ip.strip() == "":
         print(f"{printstr} Wrong Selection.\n")
    elif 1 == int(ip):
        print(f"{printstr} Selected Holdings")
        file_name = "MyHoldings_Opc.csv"
        symbols=HLDNGS.copy()
        break
    elif 2 == int(ip):
        print(f"{printstr} Selected All FnO Symbols")
        file_name = "AllFnOStocks_Opc.csv"
        symbols=sorted(fnolist())
        symbols.remove('NIFTY')
        symbols.remove('NIFTYIT')
        symbols.remove('BANKNIFTY')
        break
    else:
        print(f"{printstr} Wrong Selection.\n")

if os.name == 'nt':
    fp = os.getcwd() +"\\"+file_name
elif os.name == 'posix':
    fp = os.getcwd() +"/"+file_name
else:
    print("unknown OS. Change code to use this")
    exit(0)

fast=12
slow=26
sign=9

while True:
    ip = input(f"{printstr} Select MACD: 1 - 12,29,9 ---- 2 - 50,200,25 : ")
    if ip.strip() == "":
         print(f"{printstr} Wrong Selection.\n")
    elif 1 == int(ip):
        print(f"{printstr} Selected MACD(12,26,9)")
        days = 365
        break
    elif 2 == int(ip):
        print(f"{printstr} Selected MACD(50,200,25)")
        fast = 50
        slow = 200
        sign = 25
        days = 1000
        fp = fp.replace(".csv", "_MACD_50_200_25.csv")
        break
    else:
        print(f"{printstr} Wrong Selection.\n")

ed = datetime.now().date()
sd = ed - timedelta(days=days)

md = 'w'
header = True
while True:
    if os.path.exists(fp):
        ip=input(f"{printstr} File {fp} exists.\n\nDefault is Overwrite. Select 1 - to just append , 2 - to create a new file with timestamp: ")
        if ip.strip() == "":
             break
        elif int(ip) == 1:
            md = 'a'
            header = False
            break
        elif int(ip) == 2:
            fp = fp.replace(".csv", "_" + datetime.now().strftime("%d-%b-%Y-%H-%M-%S") + ".csv")
            break
        else:
            print(f"{printstr} Wrong Selection.\n")
    else:
         print(f"{printstr} File {fp} doesnt exist. Will create it after processing the data\n")
         break

print(f"{printstr} Found total {len(symbols)} Symbols.\n")

# Current time with hours:minutes:seconds
print("\n\t\tTime Start: " + datetime.now().strftime("%H:%M:%S") + "\n")

for symnum, symbol in enumerate(symbols, start=1):
    symbol=nsesymbolpurify(symbol)
    x = run_with_timeout(collect_opc_data, symbol=symbol)
    x == "Success" and print(f"Done with symbol {symnum:>4} {symbol}")
    time.sleep(2)


Creat_fullReport_and_trendAnalysis(fp)

print(datetime.now().strftime("%H:%M:%S"))