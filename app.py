from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import os
from datetime import datetime
from datetime import timedelta
import pandas as pd
from threading import Lock
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import json


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

_excel_lock = Lock()
EXCEL_FILENAME = "animals.xlsx"
SHEET_NAME = "Animals"


def get_stock_items():
    """Return list of stock items from Excel."""
    items = []
    if not os.path.exists(EXCEL_FILENAME):
        return items
    with _excel_lock:
        try:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
        except Exception:
            return items
    for _, row in stock_df.iterrows():
        qty = int(row.get("Quantity", 0)) if not pd.isna(row.get("Quantity")) else 0
        if qty == 0:
            urgency = "CRITICAL"
        elif qty < 5:
            urgency = "HIGH"
        elif qty < 10:
            urgency = "MEDIUM"
        else:
            urgency = "OK"
        items.append({
            "timestamp": row.get("Timestamp", ""),
            "reference": row.get("Reference", ""),
            "name": row.get("Name", ""),
            "quantity": qty,
            "price": float(row.get("Price", 0)) if not pd.isna(row.get("Price")) else 0.0,
            "type": row.get("Type", ""),
            "urgency": urgency,
        })
    return items


def upsert_stock_to_excel(row_dict: dict):
    """Insert or update a stock item (add or overwrite entire row)."""
    stock_sheet = "Stock"
    columns = [
        "Timestamp",
        "Reference",
        "Name",
        "Quantity",
        "Price",
        "Type",
    ]

    row_with_ts = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **row_dict,
    }

    with _excel_lock:
        if os.path.exists(EXCEL_FILENAME):
            try:
                # Try to read existing Stock sheet
                existing_df = pd.read_excel(EXCEL_FILENAME, sheet_name=stock_sheet)
            except Exception:
                # Stock sheet doesn't exist or is unreadable
                existing_df = pd.DataFrame(columns=columns)
        else:
            existing_df = pd.DataFrame(columns=columns)

        ref = row_dict.get("Reference", "").strip()
        if ref and not existing_df.empty and "Reference" in existing_df.columns:
            match_idx = existing_df[existing_df["Reference"] == ref].index
            if not match_idx.empty:
                for col in columns:
                    if col in row_with_ts:
                        existing_df.loc[match_idx[0], col] = row_with_ts[col]
                combined = existing_df
            else:
                new_df = pd.DataFrame([row_with_ts], columns=columns)
                combined = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            new_df = pd.DataFrame([row_with_ts], columns=columns)
            combined = pd.concat([existing_df, new_df], ignore_index=True)

        # Write back to Excel with multiple sheets
        with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl", mode="a" if os.path.exists(EXCEL_FILENAME) else "w") as writer:
            # Preserve existing Animals sheet if it exists
            if os.path.exists(EXCEL_FILENAME):
                try:
                    animals_df = pd.read_excel(EXCEL_FILENAME, sheet_name=SHEET_NAME)
                    animals_df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
                except Exception:
                    pass
            combined.to_excel(writer, sheet_name=stock_sheet, index=False)


def save_invoice_to_excel(invoice_data: dict):
    """Save invoice to the Invoices sheet in Excel."""
    invoice_sheet = "Invoices"
    columns = [
        "Timestamp",
        "Invoice Number",
        "Owner Name",
        "Items",
        "Total Amount",
        "Payment Method",
        "PDF Path",
    ]

    row = {
        "Timestamp": invoice_data["timestamp"],
        "Invoice Number": invoice_data["invoice_number"],
        "Owner Name": invoice_data["owner_name"],
        "Items": invoice_data["items_summary"],
        "Total Amount": invoice_data["total"],
        "Payment Method": invoice_data["payment_method"],
        "PDF Path": invoice_data["pdf_path"],
    }

    new_df = pd.DataFrame([row], columns=columns)

    with _excel_lock:
        if os.path.exists(EXCEL_FILENAME):
            try:
                existing_df = pd.read_excel(EXCEL_FILENAME, sheet_name=invoice_sheet)
                combined = pd.concat([existing_df, new_df], ignore_index=True)
            except Exception:
                combined = new_df
        else:
            combined = new_df

        # Write to Excel preserving other sheets
        with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl", mode="a" if os.path.exists(EXCEL_FILENAME) else "w") as writer:
            if os.path.exists(EXCEL_FILENAME):
                # Preserve Animals sheet if present (simulation may write to it)
                try:
                    animals_df = pd.read_excel(EXCEL_FILENAME, sheet_name=SHEET_NAME)
                    animals_df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
                except Exception:
                    pass
                try:
                    stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
                    stock_df.to_excel(writer, sheet_name="Stock", index=False)
                except Exception:
                    pass
            combined.to_excel(writer, sheet_name=invoice_sheet, index=False)


def generate_invoice_pdf(invoice_data: dict) -> str:
    """Generate a PDF invoice and return the file path."""
    # Create invoices directory if it doesn't exist
    invoices_dir = "invoices"
    os.makedirs(invoices_dir, exist_ok=True)

    # Generate filename
    invoice_num = invoice_data["invoice_number"]
    pdf_filename = f"invoice_{invoice_num}.pdf"
    pdf_path = os.path.join(invoices_dir, pdf_filename)

    # Create PDF
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1a237e"),
        spaceAfter=30,
        alignment=TA_CENTER,
    )

    # Title
    title = Paragraph("VETERINARY CLINIC INVOICE", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    # Invoice details
    info_data = [
        ["Invoice Number:", invoice_num],
        ["Date:", invoice_data["timestamp"]],
        ["Owner Name:", invoice_data["owner_name"]],
        ["Payment Method:", invoice_data["payment_method"]],
    ]
    info_table = Table(info_data, colWidths=[2 * inch, 4 * inch])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#424242")),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 0.4 * inch))

    # Items table
    items_data = [["Item/Service", "Quantity", "Unit Price", "Total"]]
    for item in invoice_data["items"]:
        items_data.append(
            [
                item["name"],
                str(item["quantity"]),
                f"${float(item['unit_price']):.2f}",
                f"${float(item['total']):.2f}",
            ]
        )

    items_table = Table(items_data, colWidths=[3 * inch, 1 * inch, 1.5 * inch, 1.5 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e0e0e0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Total
    total_data = [["TOTAL:", f"${float(invoice_data['total']):.2f}"]]
    total_table = Table(total_data, colWidths=[5.5 * inch, 1.5 * inch])
    total_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("ALIGN", (0, 0), (0, 0), "RIGHT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1a237e")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e3f2fd")),
                ("BOX", (1, 0), (1, 0), 2, colors.HexColor("#1a237e")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(total_table)

    # Build PDF
    doc.build(elements)
    return pdf_path


def get_dashboard_data():
    """Read Excel data and compute dashboard statistics."""
    data = {
        "total_animals": 0,
        "animal_types": {},
        "stock_items": [],
        "low_stock_items": [],
        "total_invoices": 0,
        "total_revenue": 0.0,
        "daily_revenue": {},
    }

    if not os.path.exists(EXCEL_FILENAME):
        return data

    with _excel_lock:
        # Animals data
        try:
            animals_df = pd.read_excel(EXCEL_FILENAME, sheet_name=SHEET_NAME)
            if not animals_df.empty:
                data["total_animals"] = len(animals_df)
                
                # Count by animal type
                if "Animal Type" in animals_df.columns:
                    type_counts = animals_df["Animal Type"].value_counts().to_dict()
                    data["animal_types"] = type_counts
        except Exception:
            # Animals sheet doesn't exist or is empty - that's OK
            data["animal_types"] = {"No Data": 1}
            pass

        # Stock data
        try:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
            for _, row in stock_df.iterrows():
                item = {
                    "name": row.get("Name", ""),
                    "reference": row.get("Reference", ""),
                    "quantity": int(row.get("Quantity", 0)),
                    "type": row.get("Type", ""),
                }
                data["stock_items"].append(item)
                
                # Low stock alert (quantity < 10)
                if item["quantity"] < 10:
                    data["low_stock_items"].append(item)
        except Exception:
            pass

        # Invoices data
        try:
            invoices_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Invoices")
            data["total_invoices"] = len(invoices_df)
            
            if "Total Amount" in invoices_df.columns:
                data["total_revenue"] = float(invoices_df["Total Amount"].sum())
            
            # Daily revenue (last 30 days)
            if "Timestamp" in invoices_df.columns and "Total Amount" in invoices_df.columns:
                invoices_df["Timestamp"] = pd.to_datetime(invoices_df["Timestamp"], errors="coerce")
                invoices_df["Date"] = invoices_df["Timestamp"].dt.strftime("%Y-%m-%d")
                daily = invoices_df.groupby("Date")["Total Amount"].sum().to_dict()
                # Get last 30 days sorted
                sorted_days = sorted(daily.keys())[-30:]
                data["daily_revenue"] = {day: daily[day] for day in sorted_days}
        except Exception:
            pass

    return data


def get_simulation_state():
    """Get current simulation state (day number, budget, etc.)."""
    state_file = "simulation_state.json"
    default_state = {
        "current_day": 1,
        "budget": 5000.0,
        "daily_events": [],
        "total_animals_treated": 0,
        "start_date": datetime.now().date().isoformat()
    }
    
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                # Backfill start_date if missing from older state files
                if "start_date" not in state:
                    state["start_date"] = datetime.now().date().isoformat()
                return state
        except Exception:
            return default_state
    return default_state


def save_simulation_state(state):
    """Save simulation state to file."""
    state_file = "simulation_state.json"
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def get_dss_recommendations():
    """Decision Support System: analyze stock and provide purchase recommendations."""
    recommendations = []
    
    if not os.path.exists(EXCEL_FILENAME):
        return recommendations
    
    with _excel_lock:
        try:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
            
            for _, row in stock_df.iterrows():
                qty = int(row.get("Quantity", 0))
                name = row.get("Name", "")
                ref = row.get("Reference", "")
                price = float(row.get("Price", 0))
                item_type = row.get("Type", "")
                
                # DSS logic: recommend purchase based on stock level
                if qty == 0:
                    recommended_qty = 50
                    urgency = "CRITICAL"
                elif qty < 5:
                    recommended_qty = 30
                    urgency = "HIGH"
                elif qty < 10:
                    recommended_qty = 20
                    urgency = "MEDIUM"
                else:
                    continue
                
                total_cost = recommended_qty * price
                recommendations.append({
                    "reference": ref,
                    "name": name,
                    "current_qty": qty,
                    "recommended_qty": recommended_qty,
                    "unit_price": price,
                    "total_cost": total_cost,
                    "urgency": urgency,
                    "type": item_type
                })
        except Exception:
            pass
    
    # Sort by urgency and return
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    recommendations.sort(key=lambda x: urgency_order.get(x["urgency"], 3))
    return recommendations


def simulate_day():
    """Simulate one day: random events, stock consumption, animal visits, auto invoice generation with line items, and daily overhead costs."""
    import random

    state = get_simulation_state()
    events = []
    daily_revenue = 0.0
    day_number = state["current_day"]
    try:
        base_date = datetime.fromisoformat(state["start_date"]).date()
    except Exception:
        base_date = datetime.now().date()
    sim_date = base_date + timedelta(days=day_number - 1)

    num_visits = random.randint(3, 8)
    animal_types = ["Dog", "Cat", "Rabbit", "Bird", "Hamster"]
    owner_names = ["John Smith", "Mary Johnson", "David Lee", "Sarah Wilson", "Mike Brown", "Emma Davis"]

    with _excel_lock:
        try:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
        except Exception:
            stock_df = pd.DataFrame(columns=["Timestamp", "Reference", "Name", "Quantity", "Price", "Type"])
        try:
            animals_df = pd.read_excel(EXCEL_FILENAME, sheet_name=SHEET_NAME)
        except Exception:
            animals_df = pd.DataFrame(columns=["Timestamp", "Animal Name", "Animal Type", "Medical History", "Age", "Sex", "Owner Name", "Owner Email", "Owner Phone", "Comments"])
        try:
            invoices_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Invoices")
        except Exception:
            invoices_df = pd.DataFrame(columns=["Timestamp", "Invoice Number", "Owner Name", "Items", "Total Amount", "Payment Method", "PDF Path"])

        for i in range(num_visits):
            animal_type = random.choice(animal_types)
            animal_name = f"{animal_type} #{random.randint(100, 999)}"
            owner_name = random.choice(owner_names)
            age = random.randint(1, 15)
            sex = random.choice(["Male", "Female"])

            new_animal = pd.DataFrame([{
                "Timestamp": datetime.combine(sim_date, datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S"),
                "Animal Name": animal_name,
                "Animal Type": animal_type,
                "Medical History": "Simulation visit",
                "Age": age,
                "Sex": sex,
                "Owner Name": owner_name,
                "Owner Email": f"{owner_name.lower().replace(' ', '.')}@email.com",
                "Owner Phone": f"+1-555-{random.randint(1000, 9999)}",
                "Comments": f"Day {day_number} visit"
            }])
            animals_df = pd.concat([animals_df, new_animal], ignore_index=True)

            line_items = []

            # Consultation fee
            consult_fee = round(random.uniform(30, 80), 2)
            line_items.append({
                "name": "Consultation Fee",
                "quantity": 1,
                "unit_price": consult_fee,
                "total": consult_fee,
            })

            # Vaccines (50% chance)
            if random.random() < 0.5:
                vaccine_rows = stock_df[stock_df["Type"] == "Vaccine"]
                if not vaccine_rows.empty:
                    idx = vaccine_rows.sample(1).index[0]
                    if stock_df.loc[idx, "Quantity"] > 0:
                        stock_df.loc[idx, "Quantity"] -= 1
                        item_name = stock_df.loc[idx, "Name"]
                        item_price = float(stock_df.loc[idx, "Price"])
                        sell_unit = round(item_price * 2.0, 2)
                        line_items.append({
                            "name": item_name,
                            "quantity": 1,
                            "unit_price": sell_unit,
                            "total": sell_unit,
                        })

            # Medicine (40% chance)
            if random.random() < 0.4:
                medicine_rows = stock_df[stock_df["Type"] == "Medicine"]
                if not medicine_rows.empty:
                    idx = medicine_rows.sample(1).index[0]
                    consume_qty = random.randint(1, 3)
                    current = stock_df.loc[idx, "Quantity"]
                    actual_consume = min(consume_qty, current)
                    if actual_consume > 0:
                        stock_df.loc[idx, "Quantity"] -= actual_consume
                        item_name = stock_df.loc[idx, "Name"]
                        item_price = float(stock_df.loc[idx, "Price"])
                        sell_unit = round(item_price * 1.8, 2)
                        line_items.append({
                            "name": item_name,
                            "quantity": int(actual_consume),
                            "unit_price": sell_unit,
                            "total": round(sell_unit * int(actual_consume), 2),
                        })

            # Accessories (30% chance)
            if random.random() < 0.3:
                acc_rows = stock_df[stock_df["Type"] == "Accessory"]
                if not acc_rows.empty:
                    idx = acc_rows.sample(1).index[0]
                    consume_qty = random.randint(1, 2)
                    current = stock_df.loc[idx, "Quantity"]
                    actual_consume = min(consume_qty, current)
                    if actual_consume > 0:
                        stock_df.loc[idx, "Quantity"] -= actual_consume
                        item_name = stock_df.loc[idx, "Name"]
                        item_price = float(stock_df.loc[idx, "Price"])
                        sell_unit = round(item_price * 3.0, 2)
                        line_items.append({
                            "name": item_name,
                            "quantity": int(actual_consume),
                            "unit_price": sell_unit,
                            "total": round(sell_unit * int(actual_consume), 2),
                        })

            visit_total = round(sum(li["total"] for li in line_items), 2)
            daily_revenue += visit_total

            invoice_num = f"{state['current_day']}{i+1:02d}{random.randint(100, 999)}"
            items_summary = "; ".join([f"{li['name']} (x{li['quantity']})" for li in line_items])
            invoice_data = {
                "timestamp": datetime.combine(sim_date, datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S"),
                "invoice_number": invoice_num,
                "owner_name": owner_name,
                "payment_method": random.choice(["Cash", "Card", "Insurance"]),
                "items": line_items,
                "total": visit_total,
                "items_summary": items_summary,
                "pdf_path": ""
            }
            pdf_path = generate_invoice_pdf(invoice_data)
            invoice_data["pdf_path"] = pdf_path

            invoices_df = pd.concat([invoices_df, pd.DataFrame([{
                "Timestamp": invoice_data["timestamp"],
                "Invoice Number": invoice_num,
                "Owner Name": owner_name,
                "Items": items_summary,
                "Total Amount": visit_total,
                "Payment Method": invoice_data["payment_method"],
                "PDF Path": pdf_path
            }])], ignore_index=True)

            events.append({
                "type": "visit",
                "animal": f"{animal_name} ({animal_type})",
                "items_used": [f"{li['name']} x{li['quantity']}" for li in line_items],
                "revenue": visit_total
            })

        with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl") as writer:
            animals_df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
            stock_df.to_excel(writer, sheet_name="Stock", index=False)
            invoices_df.to_excel(writer, sheet_name="Invoices", index=False)

    # Operational costs (rent and storage)
    RENT_PER_DAY = 100.0
    try:
        with _excel_lock:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
            total_units = int(stock_df["Quantity"].fillna(0).sum())
    except Exception:
        total_units = 0
    STORAGE_COST_PER_UNIT = 0.01
    storage_cost = round(STORAGE_COST_PER_UNIT * total_units, 2)
    overhead_total = round(RENT_PER_DAY + storage_cost, 2)

    state["current_day"] += 1
    state["budget"] += daily_revenue
    state["budget"] -= overhead_total
    if overhead_total > 0:
        events.append({"type": "cost", "name": "Clinic Rent", "cost": RENT_PER_DAY})
        if storage_cost > 0:
            events.append({"type": "cost", "name": "Storage Cost", "cost": storage_cost, "units": total_units})
    state["daily_events"] = events
    state["total_animals_treated"] += num_visits
    save_simulation_state(state)

    return {
        "day": day_number,
        "events": events,
        "animals_treated": num_visits,
        "revenue": round(daily_revenue, 2),
        "new_budget": state["budget"]
    }


def reset_simulation(full: bool = True):
    """Reset simulation. If full=True, wipe all data (Excel, invoices, state) to a fresh start."""
    # Remove existing files for a truly fresh state
    if full:
        if os.path.exists(EXCEL_FILENAME):
            try:
                os.remove(EXCEL_FILENAME)
            except Exception:
                pass
        # Delete all generated invoice PDFs
        invoices_dir = "invoices"
        if os.path.isdir(invoices_dir):
            for fname in os.listdir(invoices_dir):
                if fname.lower().endswith(".pdf"):
                    try:
                        os.remove(os.path.join(invoices_dir, fname))
                    except Exception:
                        pass
        # Reset state file
        if os.path.exists("simulation_state.json"):
            try:
                os.remove("simulation_state.json")
            except Exception:
                pass

    # Recreate initial state
    initial_state = {
        "current_day": 1,
        "budget": 5000.0,
        "daily_events": [],
        "total_animals_treated": 0,
        "start_date": datetime.now().date().isoformat()
    }
    save_simulation_state(initial_state)

    # Initial stock baseline
    initial_stock = [
        {"Reference": "VAC001", "Name": "Rabies Vaccine", "Quantity": 15, "Price": 25.00, "Type": "Vaccine"},
        {"Reference": "VAC002", "Name": "Distemper Vaccine", "Quantity": 12, "Price": 30.00, "Type": "Vaccine"},
        {"Reference": "VAC003", "Name": "Parvovirus Vaccine", "Quantity": 10, "Price": 28.00, "Type": "Vaccine"},
        {"Reference": "MED001", "Name": "Antibiotic Pills", "Quantity": 30, "Price": 15.00, "Type": "Medicine"},
        {"Reference": "MED002", "Name": "Pain Relief", "Quantity": 24, "Price": 20.00, "Type": "Medicine"},
        {"Reference": "MED003", "Name": "Anti-Inflammatory", "Quantity": 20, "Price": 18.00, "Type": "Medicine"},
        {"Reference": "ACC001", "Name": "Syringe 5ml", "Quantity": 60, "Price": 0.50, "Type": "Accessory"},
        {"Reference": "ACC002", "Name": "Bandages", "Quantity": 45, "Price": 2.00, "Type": "Accessory"},
        {"Reference": "ACC003", "Name": "Surgical Gloves", "Quantity": 30, "Price": 1.50, "Type": "Accessory"},
    ]
    stock_df = pd.DataFrame(initial_stock)
    stock_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create fresh Excel file with empty Animals & Invoices sheets
    with _excel_lock:
        with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl") as writer:
            # Empty Animals sheet
            animals_cols = ["Timestamp", "Animal Name", "Animal Type", "Medical History", "Age", "Sex", "Owner Name", "Owner Email", "Owner Phone", "Comments"]
            pd.DataFrame(columns=animals_cols).to_excel(writer, sheet_name=SHEET_NAME, index=False)
            # Stock
            stock_df.to_excel(writer, sheet_name="Stock", index=False)
            # Empty Invoices sheet
            invoice_cols = ["Timestamp", "Invoice Number", "Owner Name", "Items", "Total Amount", "Payment Method", "PDF Path"]
            pd.DataFrame(columns=invoice_cols).to_excel(writer, sheet_name="Invoices", index=False)

    return initial_state


@app.route("/", methods=["GET"])
def root_redirect():
    return redirect(url_for("dashboard"))


@app.route("/stock", methods=["GET"])
def stock():
    items = get_stock_items()
    return render_template("stock.html", stock_items=items)


@app.route("/stock/submit", methods=["POST"])
def stock_submit():
    form = request.form
    required_fields = ["name", "quantity", "reference", "price", "type"]
    missing = [f for f in required_fields if not form.get(f)]
    if missing:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("stock"))
    try:
        row = {
            "Reference": form.get("reference", "").strip(),
            "Name": form.get("name", "").strip(),
            "Quantity": form.get("quantity", "").strip(),
            "Price": form.get("price", "").strip(),
            "Type": form.get("type", "").strip(),
        }
        upsert_stock_to_excel(row)
        flash("Stock item saved successfully.", "success")
    except Exception as e:
        flash(f"Failed to save stock item: {e}", "error")
    return redirect(url_for("stock"))

@app.route("/stock/refill", methods=["POST"])
def stock_refill():
    reference = request.form.get("reference", "").strip()
    quantity_add = int(request.form.get("quantity", 0))
    if not reference or quantity_add <= 0:
        flash("Invalid refill parameters.", "error")
        return redirect(url_for("stock"))
    with _excel_lock:
        try:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
        except Exception:
            flash("Stock sheet not found.", "error")
            return redirect(url_for("stock"))
        idx = stock_df[stock_df["Reference"] == reference].index
        if idx.empty:
            flash("Reference not found.", "error")
            return redirect(url_for("stock"))
        stock_df.loc[idx[0], "Quantity"] = int(stock_df.loc[idx[0], "Quantity"] or 0) + quantity_add
        stock_df.loc[idx[0], "Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Preserve other sheets
        try:
            animals_df = pd.read_excel(EXCEL_FILENAME, sheet_name=SHEET_NAME)
        except Exception:
            animals_df = pd.DataFrame()
        try:
            invoices_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Invoices")
        except Exception:
            invoices_df = pd.DataFrame()
        with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl") as writer:
            if not animals_df.empty:
                animals_df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
            stock_df.to_excel(writer, sheet_name="Stock", index=False)
            if not invoices_df.empty:
                invoices_df.to_excel(writer, sheet_name="Invoices", index=False)
    flash(f"Refilled {reference} by {quantity_add} units.", "success")
    return redirect(url_for("stock"))


@app.route("/invoices", methods=["GET"])
def invoices_list():
    invoices = []
    if os.path.exists(EXCEL_FILENAME):
        with _excel_lock:
            try:
                invoices_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Invoices")
                for _, row in invoices_df.iterrows():
                    invoices.append({
                        "timestamp": row.get("Timestamp", ""),
                        "number": row.get("Invoice Number", ""),
                        "owner": row.get("Owner Name", ""),
                        "total": float(row.get("Total Amount", 0)),
                        "pdf_exists": os.path.exists(os.path.join("invoices", f"invoice_{row.get('Invoice Number', '')}.pdf"))
                    })
            except Exception:
                pass
    return render_template("invoices.html", invoices=invoices)

@app.route("/invoices/download/<invoice_num>")
def invoices_download(invoice_num):
    pdf_path = os.path.join("invoices", f"invoice_{invoice_num}.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=f"invoice_{invoice_num}.pdf")
    flash("Invoice not found.", "error")
    return redirect(url_for("invoices_list"))


@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Display the dashboard with commercial statistics and charts."""
    state = get_simulation_state()
    return render_template("dashboard.html", state=state)


@app.route("/api/dashboard-data", methods=["GET"])
def dashboard_data():
    """Return dashboard data as JSON for Chart.js."""
    data = get_dashboard_data()
    state = get_simulation_state()
    data["simulation_state"] = state
    return data


@app.route("/simulation", methods=["GET"])
def simulation():
    """Simulation game interface."""
    state = get_simulation_state()
    recommendations = get_dss_recommendations()
    return render_template("simulation.html", state=state, recommendations=recommendations)


@app.route("/simulation/next-day", methods=["POST"])
def simulation_next_day():
    """Advance to next day in simulation."""
    result = simulate_day()
    flash(f"Day {result['day']}: Treated {result['animals_treated']} animals. Revenue: ${result['revenue']:.2f}", "success")
    return redirect(url_for("simulation"))


@app.route("/simulation/reset", methods=["POST"])
def simulation_reset():
    """Full reset: wipe all data and reinitialize."""
    reset_simulation(full=True)
    flash("Application fully reset: state, stock, animals, invoices cleared.", "success")
    return redirect(url_for("simulation"))


@app.route("/simulation/buy", methods=["POST"])
def simulation_buy():
    """Purchase items per DSS with adjustable quantity; server calculates cost."""
    reference = request.form.get("reference", "").strip()
    quantity = int(request.form.get("quantity", 0))
    if not reference or quantity <= 0:
        flash("Invalid purchase parameters.", "error")
        return redirect(url_for("simulation"))

    state = get_simulation_state()

    with _excel_lock:
        try:
            stock_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Stock")
        except Exception:
            flash("Stock sheet not found.", "error")
            return redirect(url_for("simulation"))

        idx = stock_df[stock_df["Reference"] == reference].index
        if idx.empty:
            flash("Item not found in stock.", "error")
            return redirect(url_for("simulation"))

        unit_price = float(stock_df.loc[idx[0], "Price"] or 0.0)
        total_cost = unit_price * quantity
        if state["budget"] < total_cost:
            flash(f"Insufficient budget! Need ${total_cost:.2f}, have ${state['budget']:.2f}", "error")
            return redirect(url_for("simulation"))

        # Deduct budget
        state["budget"] -= total_cost
        save_simulation_state(state)

        # Update quantity
        current_qty = int(stock_df.loc[idx[0], "Quantity"] or 0)
        stock_df.loc[idx[0], "Quantity"] = current_qty + quantity
        stock_df.loc[idx[0], "Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Preserve other sheets
        try:
            animals_df = pd.read_excel(EXCEL_FILENAME, sheet_name=SHEET_NAME)
        except Exception:
            animals_df = pd.DataFrame()
        try:
            invoices_df = pd.read_excel(EXCEL_FILENAME, sheet_name="Invoices")
        except Exception:
            invoices_df = pd.DataFrame()
        with pd.ExcelWriter(EXCEL_FILENAME, engine="openpyxl") as writer:
            if not animals_df.empty:
                animals_df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
            stock_df.to_excel(writer, sheet_name="Stock", index=False)
            if not invoices_df.empty:
                invoices_df.to_excel(writer, sheet_name="Invoices", index=False)

    flash(f"Purchased {quantity} units of {reference} for ${total_cost:.2f} (unit ${unit_price:.2f}).", "success")
    return redirect(url_for("simulation"))


if __name__ == "__main__":
    # Run the app directly for local development
    app.run(host="127.0.0.1", port=5000, debug=True)
