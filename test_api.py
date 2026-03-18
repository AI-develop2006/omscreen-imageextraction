import requests
import os

url = "http://127.0.0.1:8000/api/convert"

# Test 1: Tabular data
try:
    with open("table_test.png", "rb") as f:
        files = {"file": ("table_test.png", f, "image/png")}
        response = requests.post(url, files=files)
        
    print(f"Tabular test Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Tabular data successfully converted to Excel.")
        with open("result.xlsx", "wb") as out_f:
            out_f.write(response.content)
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Test 1 failed to run: {e}")

# Test 2: Non-tabular data
try:
    with open("non_table_test.png", "rb") as f:
        files = {"file": ("non_table_test.png", f, "image/png")}
        response = requests.post(url, files=files)
        
    print(f"Non-tabular test Status Code: {response.status_code}")
    if response.status_code == 400:
        print("Non-tabular data correctly rejected.")
    else:
        print(f"Unexpected response: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Test 2 failed to run: {e}")
