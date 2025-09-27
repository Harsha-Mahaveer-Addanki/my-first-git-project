import pandas as pd
import math

from nsepython import nse_eq, nse_optionchain_scrapper, fnolist, nsesymbolpurify
import time, os

lines = []
Headers = "Expiry,Symbol,PCR,CMP,Support,Dist_From_Support,Resistance,Dist_From_Resistance,Max_OI_Strike,Prev Close,Close"
print(Headers)
lines.append(Headers)

def collect_opc_data(symbol, exp) :
    # call the nse_eq function to get basic equity info
    data = nse_eq(symbol)

    # create some variables to print based on the data from the nse_eq
    ltp = data['priceInfo']['lastPrice']
    prev_close = data['priceInfo']['previousClose']
    close = data['priceInfo']['close']

    opcdata = nse_optionchain_scrapper(symbol)

    records = opcdata['records']['data']

    chain_data = []
    for item in records:
        strike = item.get("strikePrice")
        expiry = item.get("expiryDate")
        
        if exp != expiry:
            continue

        ce = item.get("CE", {})
        pe = item.get("PE", {})

        chain_data.append({
            "expiryDate": expiry,
            "strikePrice": strike,
            "CE_openInterest": ce.get("openInterest"),
            #"CE_changeOI": ce.get("changeinOpenInterest"),
            "CE_lastPrice": ce.get("lastPrice"),
            "PE_openInterest": pe.get("openInterest"),
            #"PE_changeOI": pe.get("changeinOpenInterest"),
            "PE_lastPrice": pe.get("lastPrice"),
        })

    df = pd.DataFrame(chain_data).sort_values(["CE_openInterest", "PE_openInterest"])

    df["CE_PE_Total"] = df["CE_openInterest"] + df["PE_openInterest"]
    df_Specific_Exp = df[df.expiryDate == exp]
    Total_Puts = df_Specific_Exp.PE_openInterest.sum()
    Total_Calls = df_Specific_Exp.CE_openInterest.sum()
    PCR = Total_Puts/Total_Calls
    max_oi_row = df_Specific_Exp.loc[df_Specific_Exp['CE_PE_Total'].idxmax()]

    Support = max_oi_row["strikePrice"] - max_oi_row["CE_lastPrice"] - max_oi_row["PE_lastPrice"]
    Resistance = max_oi_row["strikePrice"] + max_oi_row["CE_lastPrice"] + max_oi_row["PE_lastPrice"]
    Dist_from_Support = ((ltp - Support)/Support) * 100
    Dist_from_Resist = ((Resistance - ltp)/ltp) * 100

    rfh = f"{exp},{symbol},{round(PCR, 2)},{ltp},{Support},{math.ceil(Dist_from_Support * 100)/100},"
    rsh = f"{Resistance},{math.ceil(Dist_from_Resist * 100)/100},{max_oi_row.strikePrice},{prev_close},{close}"
    print(rfh+rsh)
    
    row = rfh + rsh
    lines.append(row)


exp = "30-Sep-2025"
symbols=[]

ip = input("Select 1 - Holdings Symbols, 2 - All FnO Symbols: ")
if 1 == int(ip):
    print("selected Hlds")
    symbols = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX", 
           "MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]
elif 2 == int(ip):
    print("selected All FnO")
    symbols=sorted(fnolist())
    symbols.remove('NIFTY')
    symbols.remove('NIFTYIT')
    symbols.remove('BANKNIFTY')
else:
    print("Error: Select either 1 or 2")
    exit(0)
   
for symbol in symbols:
    symbol=nsesymbolpurify(symbol)
    collect_opc_data(symbol=symbol, exp=exp)
    time.sleep(3)

if os.name == 'nt':
    fp = os.getcwd() +"\\allSym_Opc"+"_"+exp+".csv"
elif os.name == 'posix':
    fp = os.getcwd() +"/allSym_Opc"+"_"+exp+".csv"
else:
    print("unknown OS. Change code to use this")
    exit(0)

print(f"Writing into the file {fp}")

with open(fp, "w") as f:
    for line in lines:
        f.write(line + "\n")

f.close()
print("Completed writing")