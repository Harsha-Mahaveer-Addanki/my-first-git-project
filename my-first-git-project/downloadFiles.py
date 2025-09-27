import requests
import os

url = "https://raw.githubusercontent.com/Harsha-Mahaveer-Addanki/my-first-git-project/refs/heads/master/my-first-git-project/chkValuation.py"

if os.name == 'nt':
    save_as = os.getcwd() +"\\chkValuation_dwnld.py"
elif os.name == 'posix':
    save_as = os.getcwd() +"/chkValuation_dwnld.py"
else:
    print("unknown OS. Change code to use this")
    exit(0)

response = requests.get(url)
if response.status_code == 200:
    with open(save_as, "wb") as f:
        f.write(response.content)
    print(f"✅ Downloaded {save_as}")
else:
    print("❌ Failed to download:", response.status_code)
