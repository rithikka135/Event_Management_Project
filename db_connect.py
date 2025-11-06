import mysql.connector

def get_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",        # your MySQL username
        password="root",  # your MySQL password
        database="event_management"     # your database name
    )
    return conn
