# 🚛 K-FILO Fleet Management Dashboard

A modern, responsive fleet management dashboard built with Flask, Bootstrap 5, and SQL Server. Features real-time data simulation, AI fuel forecasts, ML-based anomaly detection, and a built-in messaging system.

## ✨ Features

- **Live Dashboard:** Real-time KPI cards (Total Fuel, CO₂, Anomalies) and charts that update every 10 seconds.
- **Anomaly Detection:** Identifies vehicles consuming fuel above standard limits and department budget overruns.
- **AI & ML Insights:** Fuel consumption forecast for the next month and Isolation Forest based anomaly detection.
- **Vehicle Management:** Comprehensive list view with live search, detailed vehicle usage history, and L/100km charts.
- **Admin Panel:** Complete CRUD operations for managing Users, Departments, and Vehicles.
- **Messaging System:** Real-time direct messaging between users with contact search and notification alerts.
- **Dark Mode:** Global dark/light theme toggle that persists across all pages.

## 🛠️ Tech Stack

- **Backend:** Flask, Flask-Login
- **Database:** Microsoft SQL Server (pyodbc)
- **Frontend:** Bootstrap 5, Chart.js, Jinja2
- **Data Processing:** Pandas, Scikit-learn (Isolation Forest, Linear Regression)

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ipekgunduz7/k-filo.git
   cd k-filo
