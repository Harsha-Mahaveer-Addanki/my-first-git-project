from datetime import datetime,timedelta,date

# Current time with hours:minutes:seconds
print("\n\t\tTime Start: " + datetime.now().strftime("%H:%M:%S") + "\n")

import pandas as pd
import math,time,os
from nsepython import nse_eq, nse_optionchain_scrapper, fnolist, nsesymbolpurify
from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
from jugaad_data.nse import stock_df
from ta.momentum import RSIIndicator
from ta.trend import MACD
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
            return -1,0,0

# Format as dd-MMM-yyyy
formatted_date = datetime.now().strftime("%d-%b-%Y")

# Initialize an empty DataFrame
whole_df = pd.DataFrame()

# List of current Holdings
HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]

ed = datetime.now().date()
sd = ed - timedelta(days=365)

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
	rsi_msi_df = pd.DataFrame()
	gc.collect()
	hld='M&M' if hld== 'M%26M' else hld
	rsi_msi_df = stock_df(symbol=hld, from_date=date(sd.year, sd.month, sd.day), to_date=date(ed.year, ed.month, ed.day), series="EQ")
	rsi_msi_df.sort_values(by='DATE',inplace=True)
	
	# Calculate 14-day RSI
	rsi_indicator = RSIIndicator(close=rsi_msi_df[cls_prc_str], window=14)
	rsi_msi_df['RSI'] = rsi_indicator.rsi()
		
	# Calculate MACD
	macd_indicator = MACD(
	    close=rsi_msi_df[cls_prc_str],
	    window_slow=26,  # Default: 26-period Exponential Moving Average (EMA)
	    window_fast=12,  # Default: 12-period EMA
	    window_sign=9    # Default: 9-period EMA for the signal line
	)
	rsi_msi_df['MACD'] = macd_indicator.macd()
	rsi_msi_df['MACD_Signal'] = macd_indicator.macd_signal()
	
	#print(rsi_msi_df[[cls_prc_str, 'RSI', 'MACD', 'MACD_Signal']])
	#print(type(rsi_msi_df.iloc[-1].RSI))
	return rsi_msi_df.iloc[-1].RSI, rsi_msi_df.iloc[-1].MACD, rsi_msi_df.iloc[-1].MACD_Signal


def collect_opc_data(symbol) :
     max_retries = 3
     attempt = 0
     while attempt < max_retries:
           try:
                 with tqdm(total=7, desc="Pipeline Progress", unit="step", leave=False) as pbar:
                       global whole_df
                       data = nse_eq(symbol)
                       pbar.update(1)
                       ltp = data['priceInfo']['lastPrice']
                       macro = data['industryInfo']['macro']
                       sector = data['industryInfo']['sector']
                       industry = data['industryInfo']['industry']
                       basicIndustry = data['industryInfo']['basicIndustry']
                       RSI, MACD, MACD_Signal = run_with_timeout(cal_rsi_macd, hld=symbol)
                       if RSI == -1:
                              return
                       pbar.update(1)
                       stock_pe_ratio, stock_bv = mcap_pe(symbol)
                       pbar.update(1)
                       opcdata = nse_optionchain_scrapper(symbol)
                       pbar.update(1)
                       records = opcdata['records']['data']
                       hld_yrn = "Holding" if symbol in HLDNGS else "Non-Hld"

                       chain_data = []
                       for item in records:
                                    strike = item.get("strikePrice")
                                    expiry = item.get("expiryDate")

                                    ce = item.get("CE", {})
                                    pe = item.get("PE", {})

                                    ce_oi = 0 if ce.get("openInterest") == None else ce.get("openInterest")
                                    pe_oi = 0 if pe.get("openInterest") == None else pe.get("openInterest")
                                    CE_PE_Total = ce_oi + pe_oi

                                    ce_ltp_at_strk = 0 if ce.get("lastPrice") == None else ce.get("lastPrice")
                                    pe_ltp_at_strk = 0 if pe.get("lastPrice") == None else pe.get("lastPrice")
                                    Support = strike - (ce_ltp_at_strk + pe_ltp_at_strk)
                                    Resistance = strike + (ce_ltp_at_strk + pe_ltp_at_strk)
                                    Dist_from_Support = ((ltp - Support)/Support) * 100
                                    Dist_from_Resist = ((Resistance - ltp)/ltp) * 100	        

                                    chain_data.append({
                                         "Date" : formatted_date,
                                         "expiryDate": expiry,
                                         "Symbol" : symbol,
                                         "Type" : hld_yrn,
                                         "CMP" : ltp,
                                         "Stock PE" : stock_pe_ratio ,
                                         "BV-to-CMP" : ltp/stock_bv,
                                         "RSI" : RSI,
                                         "MACD" : MACD,
                                         "MACD_Signal" : MACD_Signal,
                                         "MACD_To_Signal" : MACD - MACD_Signal,
                                         "strikePrice": strike,
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
                                         "Macro": macro,
                                         "Sector": sector,
                                         "Industry": industry,
                                         "Basic Industry": basicIndustry,
                                    })

                       df = pd.DataFrame(chain_data)
                       pbar.update(1)

                       df_max_oi_tbl = df.loc[df.groupby("expiryDate")["CE_PE_Total"].idxmax()]

                       expdlst =[]
                       expdpcrlst =[]
                       for expd in df_max_oi_tbl["expiryDate"]:
                             Total_Puts = df[df.expiryDate == expd].PE_openInterest.sum()
                             Total_Calls = df[df.expiryDate == expd].CE_openInterest.sum()
                             if Total_Calls == 0:
                                   PCR = 0
                             else:
                                   PCR = Total_Puts/Total_Calls
                             expdlst.append(expd)
                             expdpcrlst.append(PCR)

                       pbar.update(1)	

                       expdpcrdf = pd.DataFrame({"expiryDate":expdlst, "PCR":expdpcrlst})
                       merged = pd.merge(df_max_oi_tbl, expdpcrdf, on="expiryDate", how="inner")
                       whole_df = pd.concat([whole_df, merged], ignore_index=True)
                       pbar.update(1)
                       return
		    
           except Exception as e:
                 attempt += 1
                 if attempt < max_retries:
                       print(f"{attempt} Failed with symbol {symbol} {e}. Retrying")
                 else:
                       print(f"Max tries of {max_retries} reached. Seeing Error: {e}. Exiting")
                       return
                        

symbols=[]
file_name = ""
printstr = "\n--------------->>>>"
while True:
    ip = input("Select: 1 - Holdings Symbols, 2 - All FnO Symbols : ")
    if 1 == int(ip):
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

md = 'w'
header = True
while True:
    if os.path.exists(fp):
        ip=input(f"File {file_name} exists.\n\nDefault is Overwrite. Select 1 - to just append , 2 - to create a new file with timestamp: ")
        if int(ip) == 1:
            md = 'a'
            header = False
            break
        elif int(ip) == 2:
            fp = fp.replace(".csv", "_" + datetime.now().strftime("%H_%M_%S") + ".csv")
            break
        else:
            print(f"{printstr} Wrong Selection.\n")
    else:
         print(f"File {file_name} doesnt exist. Will create it after processing the data\n")
         break

print(f"{printstr} Found total {len(symbols)} Symbols.\n")

for symbol in symbols:
    symbol=nsesymbolpurify(symbol)
    collect_opc_data(symbol=symbol)
    print(f"Done with symbol {symbol}")
    time.sleep(2)

print(f"Writing into the file {fp}")
whole_df.to_csv(fp, mode=md, header=header, index=False)
print("Completed writing")
print(datetime.now().strftime("%H:%M:%S"))