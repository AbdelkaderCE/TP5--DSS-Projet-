"""Initialize the veterinary clinic simulation with starter data."""
import pandas as pd
from datetime import datetime
import os

EXCEL_FILENAME = "animals.xlsx"

# Initial stock data
initial_stock = [
    {"Reference": "VAC001", "Name": "Rabies Vaccine", "Quantity": 50, "Price": 25.00, "Type": "Vaccine"},
    {"Reference": "VAC002", "Name": "Distemper Vaccine", "Quantity": 40, "Price": 30.00, "Type": "Vaccine"},
    {"Reference": "VAC003", "Name": "Parvovirus Vaccine", "Quantity": 35, "Price": 28.00, "Type": "Vaccine"},
    {"Reference": "MED001", "Name": "Antibiotic Pills", "Quantity": 100, "Price": 15.00, "Type": "Medicine"},
    {"Reference": "MED002", "Name": "Pain Relief", "Quantity": 80, "Price": 20.00, "Type": "Medicine"},
    {"Reference": "MED003", "Name": "Anti-Inflammatory", "Quantity": 60, "Price": 18.00, "Type": "Medicine"},
    {"Reference": "ACC001", "Name": "Syringe 5ml", "Quantity": 200, "Price": 0.50, "Type": "Accessory"},
    {"Reference": "ACC002", "Name": "Bandages", "Quantity": 150, "Price": 2.00, "Type": "Accessory"},
    {"Reference": "ACC003", "Name": "Surgical Gloves", "Quantity": 100, "Price": 1.50, "Type": "Accessory"},
]

stock_df = pd.DataFrame(initial_stock)
stock_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Create Excel with Stock sheet
with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl") as writer:
    stock_df.to_excel(writer, sheet_name="Stock", index=False)

print("✅ Initial stock data created successfully!")
print(f"📦 Created {len(initial_stock)} stock items")
print(f"💾 Saved to {EXCEL_FILENAME}")
