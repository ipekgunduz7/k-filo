import pyodbc
import config

def get_connection():
    conn_str = (
        f"DRIVER={{{config.DB_DRIVER}}};"
        f"SERVER={config.DB_SERVER};"
        f"DATABASE={config.DB_NAME};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)