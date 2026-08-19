import pandas as pd
from utils.db import get_connection

def load_csv_to_db(file_path):
    df = pd.read_csv(file_path, encoding='utf-8')
    # Normalize column names
    df.columns = [col.strip().lower() for col in df.columns]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        # Check if vehicle exists
        cursor.execute("SELECT VehicleID FROM Vehicle WHERE PlateNumber = ?", row['plate_number'])
        vehicle = cursor.fetchone()
        if not vehicle:
            cursor.execute("""
                INSERT INTO Vehicle (PlateNumber, Brand, Model, DepartmentID, StandardFuelPer100km)
                VALUES (?, ?, ?, ?, ?)
            """, row['plate_number'], row.get('brand', ''), row.get('model', ''),
                 row.get('department_id'), row.get('standard_fuel_per_100km'))
            cursor.execute("SELECT SCOPE_IDENTITY()")
            vehicle_id = cursor.fetchone()[0]
        else:
            vehicle_id = vehicle[0]
        
        # Insert usage record
        cursor.execute("""
            INSERT INTO VehicleUsage (VehicleID, UsageDate, DailyKM, FuelLiters)
            VALUES (?, ?, ?, ?)
        """, vehicle_id, row['usage_date'], row['daily_km'], row['fuel_liters'])
    
    conn.commit()
    conn.close()