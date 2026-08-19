import pandas as pd
import numpy as np
from utils.db import get_connection
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


def calculate_fuel_per_100km():
    """Calculate actual fuel consumption per 100 km for each vehicle."""
    conn = get_connection()
    query = """
        SELECT v.PlateNumber, d.DepartmentName,
               SUM(u.FuelLiters) AS TotalFuel,
               SUM(u.DailyKM) AS TotalKM,
               (SUM(u.FuelLiters) / NULLIF(SUM(u.DailyKM), 0)) * 100 AS FuelPer100km
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        GROUP BY v.PlateNumber, d.DepartmentName
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def detect_anomalies(threshold=0.30):
    """Find vehicles exceeding standard consumption by more than threshold (default 30%)."""
    conn = get_connection()
    query = """
        SELECT v.PlateNumber, d.DepartmentName, v.StandardFuelPer100km,
               AVG(u.FuelLiters / NULLIF(u.DailyKM, 0)) * 100 AS ActualFuelPer100km
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        GROUP BY v.PlateNumber, d.DepartmentName, v.StandardFuelPer100km
    """
    df = pd.read_sql(query, conn)
    conn.close()

    df['DeviationPercent'] = (df['ActualFuelPer100km'] - df['StandardFuelPer100km']) / df['StandardFuelPer100km'] * 100
    anomalies = df[df['DeviationPercent'] > threshold * 100]
    return anomalies


def get_department_fuel_distribution():
    """Total fuel consumption by department."""
    conn = get_connection()
    query = """
        SELECT d.DepartmentName, SUM(u.FuelLiters) AS TotalFuel
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        GROUP BY d.DepartmentName
        ORDER BY TotalFuel DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def get_carbon_footprint():
    """Monthly CO2 emissions (1 liter fuel ≈ 2.31 kg CO2)."""
    conn = get_connection()
    query = """
        SELECT MONTH(u.UsageDate) AS Month, YEAR(u.UsageDate) AS Year,
               SUM(u.FuelLiters) AS TotalFuel
        FROM VehicleUsage u
        GROUP BY MONTH(u.UsageDate), YEAR(u.UsageDate)
        ORDER BY Year, Month
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df['CO2Emission'] = df['TotalFuel'] * 2.31
    return df


def get_budget_usage(fuel_price_per_liter=30.0):
    """Calculates how much of each department's budget is used for fuel."""
    conn = get_connection()
    query = """
        SELECT d.DepartmentName, d.Budget, SUM(u.FuelLiters) AS TotalFuel
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        GROUP BY d.DepartmentName, d.Budget
    """
    df = pd.read_sql(query, conn)
    conn.close()

    df['TotalCost'] = df['TotalFuel'] * fuel_price_per_liter
    df['BudgetUsedPercent'] = (df['TotalCost'] / df['Budget']) * 100
    return df


def get_budget_alerts(threshold=100.0):
    """Returns departments that have exceeded their fuel budget (default >100%)."""
    budget_df = get_budget_usage()
    alerts = budget_df[budget_df['BudgetUsedPercent'] > threshold]
    return alerts


def get_seasonal_avg_fuel():
    """Calculates average fuel consumption per 100 km for each month."""
    conn = get_connection()
    query = """
        SELECT MONTH(u.UsageDate) AS Month, YEAR(u.UsageDate) AS Year,
               AVG(u.FuelLiters / NULLIF(u.DailyKM, 0)) * 100 AS AvgFuelPer100km
        FROM VehicleUsage u
        GROUP BY MONTH(u.UsageDate), YEAR(u.UsageDate)
        ORDER BY Year, Month
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df['MonthLabel'] = df['Month'].astype(str) + '/' + df['Year'].astype(str)
    return df


def get_weekday_weekend_analysis():
    """Compares average fuel consumption between weekdays and weekends."""
    conn = get_connection()
    query = """
        SELECT 
            CASE WHEN DATEPART(weekday, u.UsageDate) IN (1, 7) THEN 'Weekend'
                 ELSE 'Weekday'
            END AS DayType,
            AVG(u.FuelLiters / NULLIF(u.DailyKM, 0)) * 100 AS AvgFuelPer100km
        FROM VehicleUsage u
        GROUP BY 
            CASE WHEN DATEPART(weekday, u.UsageDate) IN (1, 7) THEN 'Weekend'
                 ELSE 'Weekday'
            END
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def get_advanced_anomalies(monthly_change_threshold=0.20):
    conn = get_connection()
    query = """
        SELECT v.PlateNumber, d.DepartmentName,
               MONTH(u.UsageDate) AS Month, YEAR(u.UsageDate) AS Year,
               AVG(u.FuelLiters / NULLIF(u.DailyKM, 0)) * 100 AS AvgFuelPer100km
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        GROUP BY v.PlateNumber, d.DepartmentName, MONTH(u.UsageDate), YEAR(u.UsageDate)
        ORDER BY v.PlateNumber, Year, Month
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return []

    anomalies = []
    for plate, group in df.groupby('PlateNumber'):
        group = group.sort_values(['Year', 'Month'])
        if len(group) < 2:
            continue
        previous_avg = None
        previous_month = None
        for _, row in group.iterrows():
            if previous_avg is not None:
                change = (row['AvgFuelPer100km'] - previous_avg) / previous_avg
                if change > monthly_change_threshold:
                    anomalies.append({
                        'PlateNumber': row['PlateNumber'],
                        'DepartmentName': row['DepartmentName'],
                        'Month': f"{row['Month']}/{row['Year']}",
                        'PreviousMonth': previous_month,
                        'CurrentAvgFuel': round(row['AvgFuelPer100km'], 2),
                        'PreviousAvgFuel': round(previous_avg, 2),
                        'ChangePercent': round(change * 100, 2)
                    })
            previous_avg = row['AvgFuelPer100km']
            previous_month = f"{row['Month']}/{row['Year']}"
    return sorted(anomalies, key=lambda x: x['ChangePercent'], reverse=True)


def get_ml_anomalies(contamination=0.05):
    conn = get_connection()
    query = """
        SELECT v.PlateNumber, d.DepartmentName, u.DailyKM, u.FuelLiters,
               (u.FuelLiters / NULLIF(u.DailyKM, 0)) * 100 AS FuelPer100km
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if len(df) < 10:
        return []

    features = df[['DailyKM', 'FuelLiters', 'FuelPer100km']].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)
    model = IsolationForest(contamination=contamination, random_state=42)
    df['Anomaly'] = model.fit_predict(X_scaled)
    anomalies = df[df['Anomaly'] == -1]
    if anomalies.empty:
        return []
    summary = anomalies.groupby(['PlateNumber', 'DepartmentName']).size().reset_index(name='AnomalyCount')
    summary = summary.sort_values('AnomalyCount', ascending=False)
    return summary.to_dict('records')


def get_fuel_forecast(months_ahead=1):
    df = get_carbon_footprint()
    if len(df) < 2:
        return {}
    df['Date'] = pd.to_datetime(df.assign(day=1)[['Year', 'Month', 'day']])
    df = df.sort_values('Date')
    X = np.arange(len(df)).reshape(-1, 1)
    y = df['TotalFuel'].values
    model = LinearRegression()
    model.fit(X, y)
    next_index = np.array([[len(df) + months_ahead - 1]])
    predicted = model.predict(next_index)[0]
    last_date = df.iloc[-1]['Date']
    next_date = last_date + pd.DateOffset(months=months_ahead)
    return {
        'next_month': next_date.strftime('%m/%Y'),
        'predicted_fuel': round(predicted, 2),
        'trend': 'increasing' if model.coef_[0] > 0 else 'decreasing'
    }


def get_total_vehicles():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Vehicle")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_total_fuel():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(FuelLiters) FROM VehicleUsage")
    total = cursor.fetchone()[0] or 0
    conn.close()
    return round(float(total), 2)


def get_total_co2():
    total_fuel = float(get_total_fuel())
    return round(total_fuel * 2.31, 2)


def get_top_department():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP 1 d.DepartmentName, SUM(u.FuelLiters) AS TotalFuel
        FROM VehicleUsage u
        JOIN Vehicle v ON u.VehicleID = v.VehicleID
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        GROUP BY d.DepartmentName
        ORDER BY TotalFuel DESC
    """)
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'name': row[0], 'total_fuel': round(row[1], 2)}
    return None