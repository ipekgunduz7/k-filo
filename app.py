from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from werkzeug.utils import secure_filename
import utils.analytics as analytics
import utils.data_loader as data_loader
import pandas as pd
from io import BytesIO
from flask import jsonify
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import random
from datetime import date
from functools import wraps
import time

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['SECRET_KEY'] = 'your-secret-key'
# Bildirim kontrol zamanı için config değişkeni
app.config['last_notif_check'] = 0

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- BİLDİRİM OLUŞTURMA FONKSİYONU ---
def create_notification(user_id, message):
    try:
        conn = data_loader.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Notification (UserID, Message, IsRead) VALUES (?, ?, 0)", (user_id, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error while sending notification: {e}")
# ------------------------------------------------------------

@app.route('/')
@login_required
def index():
    department_df = pd.DataFrame()
    anomalies = pd.DataFrame()
    active_anomalies = 0
    carbon_df = pd.DataFrame()
    budget_df = pd.DataFrame()
    budget_alerts = pd.DataFrame()
    seasonal_df = pd.DataFrame()
    weekday_df = pd.DataFrame()
    advanced_anomalies = []
    ml_anomalies = []
    forecast = {}
    total_vehicles = 0
    total_fuel = 0
    total_co2 = 0
    top_department = None

    try:
        department_df = analytics.get_department_fuel_distribution()
    except Exception as e:
        print(f"Dashboard Error - get_department_fuel_distribution: {e}")

    try:
        anomalies = analytics.detect_anomalies()
        active_anomalies = len(anomalies)
    except Exception as e:
        print(f"Dashboard Error - detect_anomalies: {e}")

    try:
        carbon_df = analytics.get_carbon_footprint()
    except Exception as e:
        print(f"Dashboard Error - get_carbon_footprint: {e}")

    try:
        budget_df = analytics.get_budget_usage()
    except Exception as e:
        print(f"Dashboard Error - get_budget_usage: {e}")

    try:
        budget_alerts = analytics.get_budget_alerts()
    except Exception as e:
        print(f"Dashboard Error - get_budget_alerts: {e}")

    try:
        seasonal_df = analytics.get_seasonal_avg_fuel()
    except Exception as e:
        print(f"Dashboard Error - get_seasonal_avg_fuel: {e}")

    try:
        weekday_df = analytics.get_weekday_weekend_analysis()
    except Exception as e:
        print(f"Dashboard Error - get_weekday_weekend_analysis: {e}")

    try:
        advanced_anomalies = analytics.get_advanced_anomalies() or []
    except Exception as e:
        print(f"Dashboard Error - get_advanced_anomalies: {e}")

    try:
        ml_anomalies = analytics.get_ml_anomalies() or []
    except Exception as e:
        print(f"Dashboard Error - get_ml_anomalies: {e}")

    try:
        forecast = analytics.get_fuel_forecast() or {}
    except Exception as e:
        print(f"Dashboard Error - get_fuel_forecast: {e}")

    try:
        total_vehicles = analytics.get_total_vehicles() or 0
        total_fuel = analytics.get_total_fuel() or 0
        total_co2 = analytics.get_total_co2() or 0
        top_department = analytics.get_top_department()
    except Exception as e:
        print(f"Dashboard Error - get_total_...: {e}")

    insights = {}
    if not department_df.empty:
        total_fuel_sum = department_df['TotalFuel'].sum()
        top_dept = department_df.iloc[0]
        insights['pie'] = f"The highest fuel consumer is {top_dept['DepartmentName']} with {top_dept['TotalFuel']:.0f} liters, representing {top_dept['TotalFuel'] / total_fuel_sum * 100:.1f}% of total fuel consumption."
        insights['bar'] = f"Total fuel consumption across all departments is {total_fuel_sum:.0f} liters. {top_dept['DepartmentName']} has the highest consumption."
    else:
        insights['pie'] = "No data available for department fuel distribution."
        insights['bar'] = "No data available for total fuel consumption."

    if not carbon_df.empty:
        latest_carbon = carbon_df.iloc[-1]
        insights['line'] = f"Total CO2 emission in {int(latest_carbon['Month'])}/{int(latest_carbon['Year'])} is {latest_carbon['CO2Emission']:.2f} kg."
    else:
        insights['line'] = "No carbon footprint data available."

    if not budget_df.empty:
        max_budget = budget_df.loc[budget_df['BudgetUsedPercent'].idxmax()]
        insights['budget'] = f"{max_budget['DepartmentName']} has the highest budget utilization at {max_budget['BudgetUsedPercent']:.1f}%."
    else:
        insights['budget'] = "No budget data available."

    if not seasonal_df.empty:
        seasonal_max = seasonal_df.loc[seasonal_df['AvgFuelPer100km'].idxmax()]
        seasonal_min = seasonal_df.loc[seasonal_df['AvgFuelPer100km'].idxmin()]
        insights['seasonal'] = f"The highest monthly average fuel consumption is {seasonal_max['AvgFuelPer100km']:.2f} L/100km in {seasonal_max['MonthLabel']}. The lowest is {seasonal_min['AvgFuelPer100km']:.2f} L/100km in {seasonal_min['MonthLabel']}."
    else:
        insights['seasonal'] = "No seasonal data available."

    if not weekday_df.empty:
        weekday_row = weekday_df[weekday_df['DayType'] == 'Weekday']
        weekend_row = weekday_df[weekday_df['DayType'] == 'Weekend']
        if not weekday_row.empty and not weekend_row.empty:
            insights['weekday'] = f"Weekday average fuel consumption is {weekday_row.iloc[0]['AvgFuelPer100km']:.2f} L/100km. Weekend average is {weekend_row.iloc[0]['AvgFuelPer100km']:.2f} L/100km."
        else:
            insights['weekday'] = "Insufficient weekday/weekend data."
    else:
        insights['weekday'] = "No weekday/weekend data available."

    # Chart verileri
    department_labels = department_df['DepartmentName'].tolist() if not department_df.empty else []
    department_values = department_df['TotalFuel'].tolist() if not department_df.empty else []

    carbon_labels = [f"{int(row['Month'])}/{int(row['Year'])}" for _, row in carbon_df.iterrows()] if not carbon_df.empty else []
    carbon_values = carbon_df['CO2Emission'].tolist() if not carbon_df.empty else []

    budget_labels = budget_df['DepartmentName'].tolist() if not budget_df.empty else []
    budget_values = budget_df['BudgetUsedPercent'].tolist() if not budget_df.empty else []

    seasonal_labels = seasonal_df['MonthLabel'].tolist() if not seasonal_df.empty else []
    seasonal_values = seasonal_df['AvgFuelPer100km'].tolist() if not seasonal_df.empty else []

    weekday_labels = weekday_df['DayType'].tolist() if not weekday_df.empty else []
    weekday_values = weekday_df['AvgFuelPer100km'].tolist() if not weekday_df.empty else []

    return render_template(
        'index.html',
        department_labels=department_labels,
        department_values=department_values,
        anomalies=anomalies.to_dict('records') if not anomalies.empty else [],
        carbon_labels=carbon_labels,
        carbon_values=carbon_values,
        budget_labels=budget_labels,
        budget_values=budget_values,
        budget_alerts=budget_alerts.to_dict('records') if not budget_alerts.empty else [],
        seasonal_labels=seasonal_labels,
        seasonal_values=seasonal_values,
        weekday_labels=weekday_labels,
        weekday_values=weekday_values,
        advanced_anomalies=advanced_anomalies,
        insights=insights,
        ml_anomalies=ml_anomalies,
        forecast=forecast,
        total_vehicles=total_vehicles,
        total_fuel=total_fuel,
        total_co2=total_co2,
        top_department=top_department,
        active_anomalies=active_anomalies
    )


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            if filename.endswith('.xlsx'):
                df = pd.read_excel(filepath)
                csv_path = filepath.replace('.xlsx', '.csv')
                df.to_csv(csv_path, index=False)
                filepath = csv_path
            data_loader.load_csv_to_db(filepath)
            return redirect(url_for('index'))
    return render_template('upload.html')


@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


@app.route('/export')
def export_excel():
    department_df = analytics.get_department_fuel_distribution()
    budget_df = analytics.get_budget_usage()
    carbon_df = analytics.get_carbon_footprint()
    seasonal_df = analytics.get_seasonal_avg_fuel()
    weekday_df = analytics.get_weekday_weekend_analysis()
    anomalies_df = analytics.detect_anomalies()
    advanced_anomalies = analytics.get_advanced_anomalies()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        department_df.to_excel(writer, sheet_name='Fuel by Department', index=False)
        budget_df.to_excel(writer, sheet_name='Budget Usage', index=False)
        carbon_df.to_excel(writer, sheet_name='Carbon Footprint', index=False)
        seasonal_df.to_excel(writer, sheet_name='Seasonal Trend', index=False)
        weekday_df.to_excel(writer, sheet_name='Weekday vs Weekend', index=False)
        anomalies_df.to_excel(writer, sheet_name='Anomalies', index=False)
        if advanced_anomalies:
            pd.DataFrame(advanced_anomalies).to_excel(writer, sheet_name='Advanced Anomalies', index=False)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name='K-FILO_Report.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/api/simulate', methods=['POST'])
@login_required
def simulate_data():
    conn = None
    try:
        conn = data_loader.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 VehicleID FROM Vehicle ORDER BY NEWID()")
        vehicle = cursor.fetchone()
        if not vehicle:
            return jsonify({'success': False, 'error': 'No vehicles found'}), 400

        vehicle_id = vehicle[0]
        usage_date = date.today()
        daily_km = round(random.uniform(40, 300), 2)
        fuel_liters = round((daily_km / 100) * random.uniform(8, 15), 2)

        cursor.execute("""
            INSERT INTO VehicleUsage (VehicleID, UsageDate, DailyKM, FuelLiters)
            VALUES (?, ?, ?, ?)
        """, vehicle_id, usage_date, daily_km, fuel_liters)

        conn.commit()
        return jsonify({'success': True, 'daily_km': daily_km, 'fuel_liters': fuel_liters})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Simulation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/dashboard-data')
@login_required
def api_dashboard_data():
    try:
        dept_df = analytics.get_department_fuel_distribution()
        budget_df = analytics.get_budget_usage()
        carbon_df = analytics.get_carbon_footprint()
        seasonal_df = analytics.get_seasonal_avg_fuel()
        total_fuel = analytics.get_total_fuel()
        total_co2 = analytics.get_total_co2()
        top_department = analytics.get_top_department()
        
        active_anomalies = 0
        try:
            anomalies = analytics.detect_anomalies()
            active_anomalies = len(anomalies)
        except Exception as e:
            print(f"Dashboard Error - active_anomalies: {e}")

    except Exception as e:
        print(f"Dashboard Data Error: {e}")
        dept_df, budget_df, carbon_df, seasonal_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        total_fuel, total_co2 = 0, 0
        top_department = None
        active_anomalies = 0

    return jsonify({
        'department_labels': dept_df['DepartmentName'].tolist() if not dept_df.empty else [],
        'department_values': dept_df['TotalFuel'].tolist() if not dept_df.empty else [],
        'budget_labels': budget_df['DepartmentName'].tolist() if not budget_df.empty else [],
        'budget_values': budget_df['BudgetUsedPercent'].tolist() if not budget_df.empty else [],
        'carbon_labels': [f"{int(row['Month'])}/{int(row['Year'])}" for _, row in carbon_df.iterrows()] if not carbon_df.empty else [],
        'carbon_values': carbon_df['CO2Emission'].tolist() if not carbon_df.empty else [],
        'seasonal_labels': seasonal_df['MonthLabel'].tolist() if not seasonal_df.empty else [],
        'seasonal_values': seasonal_df['AvgFuelPer100km'].tolist() if not seasonal_df.empty else [],
        'total_fuel': total_fuel,
        'total_co2': total_co2,
        'active_anomalies': active_anomalies,  
        'top_department_name': top_department['name'] if top_department else 'N/A'
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = data_loader.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, Username, PasswordHash, Role, DepartmentID FROM [User] WHERE Username = ?", username)
        row = cursor.fetchone()
        conn.close()
        if row and check_password_hash(row[2], password):
            user = User(row[0], row[1], row[3], row[4])
            login_user(user)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/vehicles')
@login_required
def vehicles():
    conn = data_loader.get_connection()
    query = """
        SELECT v.VehicleID, v.PlateNumber, v.Brand, v.Model, d.DepartmentName
        FROM Vehicle v
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        ORDER BY v.PlateNumber
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return render_template('vehicles.html', vehicles=df.to_dict('records'))


@app.route('/vehicle/<int:vehicle_id>')
@login_required
def vehicle_detail(vehicle_id):
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.PlateNumber, v.Brand, v.Model, d.DepartmentName
        FROM Vehicle v 
        JOIN Department d ON v.DepartmentID = d.DepartmentID
        WHERE v.VehicleID = ?
    """, vehicle_id)
    info = cursor.fetchone()
    if not info:
        return "Vehicle not found", 404
    cursor.execute("""
        SELECT UsageDate, DailyKM, FuelLiters, 
               (FuelLiters / NULLIF(DailyKM, 0)) * 100 AS L100
        FROM VehicleUsage 
        WHERE VehicleID = ? 
        ORDER BY UsageDate DESC
    """, vehicle_id)
    rows = cursor.fetchall()
    conn.close()
    vehicle_info = {
        'PlateNumber': info[0], 
        'Brand': info[1], 
        'Model': info[2], 
        'DepartmentName': info[3]
    }
    usage_data = [{
        'UsageDate': r[0], 
        'DailyKM': r[1], 
        'FuelLiters': r[2], 
        'L100': round(float(r[3]), 2) if r[3] else 0
    } for r in rows]
    return render_template('vehicle_detail.html', vehicle=vehicle_info, usage_data=usage_data)


class User(UserMixin):
    def __init__(self, user_id, username, role, department_id=None):
        self.id = user_id
        self.username = username
        self.role = role
        self.department_id = department_id

    def is_admin(self):
        return self.role == 'admin'


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return "You don't have permission to access this page.", 403
        return f(*args, **kwargs)
    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserID, Username, Role, DepartmentID FROM [User] WHERE UserID = ?", user_id)
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None


@app.route('/api/departments')
@login_required
def api_departments():
    df = analytics.get_department_fuel_distribution()
    return jsonify(df.to_dict('records'))


@app.route('/api/anomalies')
@login_required
def api_anomalies():
    df = analytics.detect_anomalies()
    return jsonify(df.to_dict('records'))


@app.route('/api/forecast')
@login_required
def api_forecast():
    forecast = analytics.get_fuel_forecast()
    return jsonify(forecast)


@app.route('/download-pdf')
@login_required
def download_pdf():
    dept_df = analytics.get_department_fuel_distribution()
    anomalies = analytics.detect_anomalies()
    forecast = analytics.get_fuel_forecast()

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("K-FILO Fleet Analysis Report", styles['Heading1']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Fuel Consumption by Department", styles['Heading2']))
    if not dept_df.empty:
        table_data = [dept_df.columns.tolist()] + dept_df.values.tolist()
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))
    story.append(Paragraph("Anomalies Detected", styles['Heading2']))
    if not anomalies.empty:
        for _, row in anomalies.iterrows():
            story.append(Paragraph(f"Vehicle {row['PlateNumber']} ({row['DepartmentName']}): {row['DeviationPercent']:.2f}% over standard", styles['Normal']))
    else:
        story.append(Paragraph("No anomalies found.", styles['Normal']))
    story.append(Spacer(1, 12))
    if forecast:
        story.append(Paragraph("Fuel Forecast", styles['Heading2']))
        story.append(Paragraph(f"Predicted consumption for {forecast['next_month']}: {forecast['predicted_fuel']:.2f} liters ({forecast['trend']} trend).", styles['Normal']))
    doc.build(story)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='K_FILO_Report.pdf', mimetype='application/pdf')


@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    conn = None
    try:
        conn = data_loader.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, Username, Role, DepartmentID FROM [User]")
        users = [{'UserID': r[0], 'Username': r[1], 'Role': r[2], 'DepartmentID': r[3]} for r in cursor.fetchall()]
        cursor.execute("SELECT DepartmentID, DepartmentName, Budget FROM Department")
        departments = [{'DepartmentID': r[0], 'DepartmentName': r[1], 'Budget': r[2]} for r in cursor.fetchall()]
        cursor.execute("""
            SELECT v.VehicleID, v.PlateNumber, v.Brand, v.Model, d.DepartmentName
            FROM Vehicle v
            LEFT JOIN Department d ON v.DepartmentID = d.DepartmentID
            ORDER BY v.PlateNumber
        """)
        vehicles = [{'VehicleID': r[0], 'PlateNumber': r[1], 'Brand': r[2], 'Model': r[3], 'DepartmentName': r[4] or 'N/A'} for r in cursor.fetchall()]
        total_vehicles = len(vehicles)
        total_departments = len(departments)
        total_users = len(users)
        
        try:
            active_anomalies = len(analytics.detect_anomalies())
        except:
            active_anomalies = 0
            
        top_department = analytics.get_top_department()
        
        return render_template('admin.html',
                               users=users,
                               departments=departments,
                               vehicles=vehicles,
                               total_vehicles=total_vehicles,
                               total_departments=total_departments,
                               total_users=total_users,
                               top_department=top_department,
                               active_anomalies=active_anomalies)
    except Exception as e:
        print(f"Critical error while loading admin panel: {e}")
        return "An error occurred while retrieving admin panel data, check the terminal.", 500
    finally:
        if conn:
            conn.close()

@app.route('/admin/add-department', methods=['POST'])
@login_required
@admin_required
def admin_add_department():
    name = request.form['name']
    budget = request.form.get('budget', 0)
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Department (DepartmentName, Budget) VALUES (?, ?)", name, budget)
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete-department/<int:dept_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_department(dept_id):
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Department WHERE DepartmentID = ?", dept_id)
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/add-vehicle', methods=['POST'])
@login_required
@admin_required
def admin_add_vehicle():
    plate = request.form['plate']
    brand = request.form['brand']
    model = request.form['model']
    dept_id = request.form.get('department_id') or None
    standard_fuel = request.form.get('standard_fuel', 10)
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Vehicle (PlateNumber, Brand, Model, DepartmentID, StandardFuelPer100km)
        VALUES (?, ?, ?, ?, ?)
    """, plate, brand, model, dept_id, standard_fuel)
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete-vehicle/<int:vehicle_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_vehicle(vehicle_id):
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Vehicle WHERE VehicleID = ?", vehicle_id)
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/add', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    dept_id = request.form.get('department_id')
    if dept_id == '':
        dept_id = None
    hashed_pw = generate_password_hash(password)
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO [User] (Username, PasswordHash, Role, DepartmentID) VALUES (?, ?, ?, ?)",
                   username, hashed_pw, role, dept_id)
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    if user_id == int(current_user.id):
        return "You cannot delete yourself.", 400
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Notification WHERE UserID = ?", user_id)
        cursor.execute("DELETE FROM Message WHERE SenderID = ? OR ReceiverID = ?", user_id, user_id)
        cursor.execute("DELETE FROM [User] WHERE UserID = ?", user_id)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Hata: {e}")
        return "An error occurred while deleting the user.", 500
    finally:
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/analytics')
@login_required
def analytics_page():
    return redirect(url_for('reports'))


@app.route('/messages')
@login_required
def messages():
    return render_template('messages.html')


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        return redirect(url_for('settings'))
    return render_template('settings.html')


# --- BİLDİRİM SİSTEMİ API ---
@app.route('/api/notifications')
@login_required
def get_notifications():
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT NotificationID, Message, IsRead, CreatedAt 
        FROM Notification 
        WHERE UserID = ? 
        ORDER BY CreatedAt DESC
    """, (current_user.id,))
    rows = cursor.fetchall()
    unread_count = sum(1 for r in rows if not r[2])
    notif_list = [{
        'id': r[0], 
        'message': r[1], 
        'is_read': r[2], 
        'created_at': r[3].strftime('%H:%M') if r[3] else ''
    } for r in rows]
    conn.close()
    return jsonify({'notifications': notif_list, 'unread_count': unread_count})


@app.route('/api/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Notification SET IsRead = 1 WHERE UserID = ?", (current_user.id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# --- MESAJLAŞMA SİSTEMİ API ---
@app.route('/api/users')
@login_required
def api_users():
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserID, Username, Role FROM [User] WHERE UserID != ?", (current_user.id,))
    users = [{'id': r[0], 'username': r[1], 'role': r[2]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)


@app.route('/api/messages/<int:user_id>')
@login_required
def get_messages(user_id):
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SenderID, Content, CreatedAt 
        FROM Message 
        WHERE (SenderID = ? AND ReceiverID = ?) OR (SenderID = ? AND ReceiverID = ?)
        ORDER BY CreatedAt ASC
    """, (current_user.id, user_id, user_id, current_user.id))
    rows = cursor.fetchall()
    messages = [{
        'sender_id': r[0],
        'content': r[1],
        'created_at': r[2].strftime('%H:%M')
    } for r in rows]
    cursor.execute("UPDATE Message SET IsRead = 1 WHERE SenderID = ? AND ReceiverID = ?", (user_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify(messages)


@app.route('/api/messages/send', methods=['POST'])
@login_required
def send_message():
    data = request.json
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    if not receiver_id or not content:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Message (SenderID, ReceiverID, Content) VALUES (?, ?, ?)", 
                   (current_user.id, receiver_id, content))
    conn.commit()
    conn.close()
    create_notification(receiver_id, f"💬 New message from {current_user.username}")
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=8080)