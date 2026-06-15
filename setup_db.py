import pymysql

# Connect to MySQL Server (adjust user/password if needed)
try:
    connection = pymysql.connect(host='localhost', user='root', password='')
    cursor = connection.cursor()
    
    # Create the database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS smart_parking")
    print("✅ Database 'smart_parking' created successfully or already exists.")
    
    connection.commit()
    cursor.close()
    connection.close()
except Exception as e:
    print(f"❌ Error connecting to MySQL: {e}")
    print("Please make sure your MySQL server (like XAMPP) is running.")
