from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
from nsepython import nse_eq, fnolist, nsesymbolpurify
import time, os

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

lines = []
Headers = "Scrip,MCap,PE from Screener"
lines.append(Headers)

def mcap_pe(scrip):
    SCRIP = scrip
    link = f'https://www.screener.in/company/{SCRIP}'
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
            if 'Market Cap' in name_span.text: 
                num_span = li.find('span',{'class':'number'})
                num_span = num_span.text.replace(',', '')
                market_cap = float(num_span) if (num_span != '') else 0.0
            elif 'Stock P/E' in name_span.text: 
                num_span = li.find('span',{'class':'number'})
                num_span = num_span.text.replace(',', '')
                stock_pe = float(num_span) if (num_span != '') else 0.0
                break
        
        print(f'MARKET CAPITILIZATION - {SCRIP}: {market_cap} Cr. Stock P/E: {stock_pe}')
        lines.append(f"{SCRIP},{market_cap},{stock_pe}")

    except:
        print(f'EXCEPTION THROWN: UNABLE TO FETCH DATA FOR {SCRIP}')


for scrip in symbols:
    mcap_pe(scrip=scrip)
    time.sleep(5)

if os.name == 'nt':
    fp = os.getcwd() +"\\symValuations.csv"
elif os.name == 'posix':
    fp = os.getcwd() +"/symValuations.csv"
else:
    print("unknown OS. Change code to use this")
    exit(0)

print(f"Writing into the file {fp}")

with open(fp, "w") as f:
    for line in lines:
        f.write(line + "\n")

f.close()
print("Completed writing")