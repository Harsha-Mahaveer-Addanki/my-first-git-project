import pandas as pd
from multiprocessing import Pool
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import threading, time, gc, os, sys, random
import datetime as dt
from nsepython import fnolist
from urllib.error import HTTPError, URLError
from tqdm import tqdm

try:
    from Backup.allIndices import AllList
except ImportError as e:
    from allIndices import AllList

if os.name == 'nt':
    #print("This seems to be Windows. Using YFinance")
    import yfinance as yf
    def eq_func(sym):
        df = yf.download(sym + ".NS", start=start_date, end=end_date, auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        df = df.reset_index()
        df['Close'] = df['Close'].round(2)
        return df[['Date', 'Close']]
elif "pydroid" in sys.executable.lower():
    #print("This seems to be pydroid on Android. Using nsepython")
    from nsepython import equity_history
    def eq_func(sym):
        df = equity_history(symbol=sym, series="EQ",
                            start_date=start_date.strftime("%d-%m-%Y"),
                            end_date=end_date.strftime("%d-%m-%Y"))
        df.rename(columns={"CH_TIMESTAMP": "Date", "CH_CLOSING_PRICE": "Close"}, inplace=True)
        df.sort_values(by='Date', inplace=True)
        return df[['Date', 'Close']]

# --- Screener.in header ---
screener_hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# --- CMP/PE/BV function ---
def get_cmp_pe_bv(sym, retries=5, delay=5):
    link = f'https://www.screener.in/company/{sym}/#top'
    req = Request(link, headers=screener_hdr)

    for attempt in range(retries):
        try:
            page = urlopen(req, timeout=15)
            soup = BeautifulSoup(page, "html.parser")

            div_html = soup.find('div', {'class': 'company-ratios'})
            ul_html = div_html.find('ul', {'id': 'top-ratios'})
            market_cap = cmp = stock_pe = book_value = 0.0

            for li in ul_html.find_all("li"):
                name_span = li.find('span', {'class': 'name'})
                num_span = li.find('span', {'class': 'number'}).text.replace(',', '')
                num_val = float(num_span) if num_span != '' else 0.0

                if 'Market Cap' in name_span.text:
                    market_cap = num_val
                elif 'Current Price' in name_span.text:
                    cmp = num_val
                elif 'Stock P/E' in name_span.text:
                    stock_pe = num_val
                elif 'Book Value' in name_span.text:
                    book_value = num_val
                    break

            return market_cap, cmp, stock_pe, book_value

        except HTTPError as e:
            if e.code == 503:
                print(f"\033[93m[WARN]\033[0m {sym}: HTTP 503 — retrying ({attempt+1}/{retries}) in {delay}s...")
                time.sleep(delay * (2 ** attempt))
            else:
                print(f"\033[91m[ERROR]\033[0m {sym}: HTTP Error {e.code}")
                break
        except (URLError, Exception) as e:
            print(f"\033[91m[ERROR]\033[0m {sym}: {e}")
            time.sleep(delay)

    print(f"\033[91m[FAILED]\033[0m {sym}: could not fetch after {retries} attempts")
    return 0.0, 0.0, 0.0, 0.0


# --- Top-level indicator functions ---
def calc_rsi(df):
    rsi_df = RSIIndicator(df["Close"], window=14).rsi()
    rsi_df_trend = rsi_df.diff(3).apply(lambda x: 'increasing' if x > 0 else 'decreasing').iloc[-1]
    return rsi_df.iloc[-1], rsi_df_trend

def calc_macd(df, slow, fast, sign):
    macd = MACD(df["Close"], window_slow=slow, window_fast=fast, window_sign=sign)
    macd_trend = macd.macd_diff().diff(3).apply(lambda x: 'increasing' if x > 0 else 'decreasing').iloc[-1]
    return macd.macd().iloc[-1], macd.macd_signal().iloc[-1], macd.macd_diff().iloc[-1], macd_trend

def calc_dir(df):
    return df['Close'].diff(3).apply(lambda x: 'increasing' if x > 0 else 'decreasing').iloc[-1]

def calc_bb_hi(df):
    return BollingerBands(df["Close"], window=20, window_dev=2).bollinger_hband().iloc[-1]

def calc_bb_mid(df):
    return BollingerBands(df["Close"], window=20, window_dev=2).bollinger_mavg().iloc[-1]

def calc_bb_lo(df):
    return BollingerBands(df["Close"], window=20, window_dev=2).bollinger_lband().iloc[-1]

"""
Trend_Dict = {
    "Below BBLo":  {"decreasing" : "Strong downside / weakness", "increasing" : "Recovering from lower range"},
    "Close to BBLo": {"decreasing" : "Strong downside / weakness", "increasing" : "Recovering from lower range"},
    "Close but BELOW Mid": {"decreasing" : "Strong downside / weakness", "increasing" : "Recovering from lower range"},
    "Mid":         {"decreasing" : "Strong downside / weakness", "increasing" : "Recovering from lower range"},
    "Close but ABOVE Mid": {"decreasing" : "Pullback in uptrend",        "increasing" : "Upside / Bullish"},
    "Close to BBHi": {"decreasing" : "Pullback in uptrend",        "increasing" : "Upside / Bullish"},
    "Above BBHi":  {"decreasing" : "Pullback in uptrend",        "increasing" : "Strong upside / Strong bullish"},}
"""

Trend_Dict = {
    "Below BBLo": {
        "decreasing": "Broke BBLo (strong dwnside momentum/oversold)",
        "increasing": "Possible rebound from oversold zone",
    },
    "Close to BBLo": {
        "decreasing": "Approaching BBLo. Weakness persisting near support",
        "increasing": "weak, possibly rebounding (early reversal possible)",
    },
    "Close but BELOW Mid": {
        "decreasing": "Below SMA - Bearish to neutral — still under pressure",
        "increasing": "Gradual recovery toward mean",
    },
    "Mid": {
        "decreasing": "Losing momentum / neutralizing after prior uptrend",
        "increasing": "Stabilizing / preparing for uptrend continuation",
    },
    "Close but ABOVE Mid": {
        "decreasing": "Pullback in ongoing uptrend",
        "increasing": "Above SMA, Mild bullishness, possible continuation",
    },
    "Close to BBHi": {
        "decreasing": "Pullback near resistance or profit booking",
        "increasing": "Aproaching BBHi/nearing overbought zone",
    },
    "Above BBHi": {
        "decreasing": "Reversal from overbought zone or exhaustion",
        "increasing": "Broke BBHi (Strong upside momentum/breakout/overbought",
    },
}

def bb_position(pos_val):
    if pos_val <= 0:
        return "Below BBLo"
    elif pos_val <= 0.25:
        return "Close to BBLo"
    elif pos_val < 0.5:
        return "Close but BELOW Mid"
    elif pos_val == 0.5:
        return "Mid"
    elif pos_val <= 0.75:
        return "Close but ABOVE Mid"
    elif pos_val < 1.0:
        return "Close to BBHi"
    else:
        return "Above BBHi"


# --- Main function per symbol ---
def analyze_symbol(symbol, slow=26, fast=12, sign=9):
    gc.collect()
    symbol = 'M&M' if symbol == 'M%26M' else symbol

    pbar = tqdm(total=4, desc="Pipeline Progress", unit="step", leave=False)
    df = eq_func(sym=symbol)
    pbar.update(1)
    indicators = {}

    # --- Thread for CMP/PE/BV ---
    def fetch_cmp_pe_bv():
        indicators['Market_Cap'], indicators['CMP'], indicators['Stock_PE'], indicators['Book_Value'] = get_cmp_pe_bv(symbol)

    cmp_thread = threading.Thread(target=fetch_cmp_pe_bv)
    cmp_thread.start()

    # --- Multiprocessing for indicators ---
    tasks = [
        (calc_rsi, df),
        (calc_macd, df, slow, fast, sign),
        (calc_dir, df),
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
    
    # Combine results
    indicators["RSI"], indicators["RSI_Trend"] = results[0]
    indicators["MACD"], indicators["MACD_Signal"], indicators["MACD_Hist"], indicators["MACD_Trend"] = results[1]
    indicators['CMP Dir'] = results[2]
    indicators["BB_HI"] = results[3]
    indicators["BB_MID"] = results[4]
    indicators["BB_LO"] = results[5]

    indicators["Symbol"] = symbol
    pos_val = round(((df['Close'].iloc[-1] - indicators['BB_LO']) / (indicators['BB_HI'] - indicators['BB_LO'])), 2)
    indicators['BB Pos'] = bb_position(pos_val=pos_val) #"Below BBLo" if pos_val <= 0 else "Close to BBLo" if (pos_val > 0) and (pos_val <= 0.25) else "Close but BELOW Mid" if (pos_val > 0.25) and (pos_val < 0.5) else "Mid" if round(pos_val, 1) == 0.5 else "Close but ABOVE Mid" if (round(pos_val, 1) > 0.5) and (pos_val <= 0.75) else "Close to BBHi" if (round(pos_val, 1) > 0.5) and (pos_val <= 0.75) else "Above BBHi"
    indicators['Interpretation'] = Trend_Dict[indicators['BB Pos']][indicators['CMP Dir']]
    indicators['Holding'] = "Yes" if symbol in HLDNGS else "No"
    indicators['FnO'] = "Yes" if symbol in fno else "No"
    pbar.update(1)
    
    cmp_thread.join()
    pbar.update(1)
    
    return indicators

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

# --- Report and Trend Analysis ---
def Creat_fullReport_and_trendAnalysis(fp):
    global all_results

    df_final = pd.DataFrame(all_results)
    df_final['Date'] = date_clm
    df_final = df_final[['Date', 'FnO', 'Holding', 'Symbol', 'CMP', 'RSI_Trend', 'BB Pos', 'CMP Dir', 'Interpretation', 'MACD_Trend', 'RSI', 'BB_HI', 'BB_MID', 'BB_LO', 'MACD', 'MACD_Signal',
                           'MACD_Hist', 'Market_Cap',  'Stock_PE', 'Book_Value']]

    fp = os.path.join(os.getcwd(), file_name)

    while True:
        if is_file_locked(fp):
            input(f"\033[97;41mFile '{fp}' is open in another program! \nClose it before running the script & press enter\033[0m")
        else:
            print("✅ File is free to write.")
            break

    #write_header = not os.path.isfile(fp)

    print(f"{printstr} Writing into the file {fp}")
    df_final.to_csv(fp, mode='w', header=True, index=True)
    print(f"{printstr} Completed Writing\n")

    del df_final
    gc.collect()
    return fp

# --- Main Execution ---
if __name__ == "__main__":
    fno = fnolist()
    HLDNGS = ["ABB", "BEL", "BSE", "CAMS", "CDSL", "CGPOWER", "COALINDIA", "IEX", "INDIGO", "IRCTC", "KFINTECH", "MCX","MOTHERSON", "PFC", "POWERGRID", "SIEMENS"]
    symbols = sorted(set(fno) | set(AllList))
    symbols.remove('NIFTY')
    symbols.remove('NIFTYIT')
    symbols.remove('BANKNIFTY')
    if (len(sys.argv) > 1) and sys.argv[1].lower() == "test":
        import random
        symbols = random.sample(symbols, 5)

    end_date = dt.date.today() + dt.timedelta(days=1)
    start_date = end_date - dt.timedelta(days=365)
    date_clm = dt.date.today().strftime("%d-%b-%Y")
    all_results = []
    file_name = "Nifty200_MidCap100_SmallCap100.csv"
    printstr = "\n--------------->>>>"
    slow, fast, sign = 29, 12, 9
    os.system('')
    print(f"{printstr} Totally {len(symbols)} Symbols found")
    print("\n\t\tTime Start: " + dt.datetime.now().strftime("%H:%M:%S") + "\n")
    #pbar = tqdm(total=4, desc="Pipeline Progress", unit="step", leave=False)
    for symnum, sym in enumerate(symbols, start=1):
        try:
            res = analyze_symbol(sym, slow, fast, sign)
            all_results.append(res)
            print(f"\033[32mDone with symbol {symnum:>4} {sym}\033[0m")
        except Exception as e:
            print(f"\033[97;41mERROR with symbol {symnum:>4} {sym} : {e}\033[0m")
        time.sleep(2)

    # Write report and trend analysis
    fp = Creat_fullReport_and_trendAnalysis(file_name)
    del symbols
    del all_results
    gc.collect()
    print(dt.datetime.now().strftime("%H:%M:%S"))
    exit(0)
    import subprocess
    subprocess.run(["git", "add", fp], check=True)
    subprocess.run(["git", "commit", "-m", "Auto commit from Home Laptop"], check=True)
    subprocess.run(["git", "push"], check=True)
