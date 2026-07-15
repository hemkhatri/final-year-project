import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Drop both related tables in the payment app
cursor.execute("DROP TABLE IF EXISTS payment_orderitem;")
cursor.execute("DROP TABLE IF EXISTS payment_order;")

# Wipe the migration logs for this app
cursor.execute("DELETE FROM django_migrations WHERE app='payment';")

conn.commit()
conn.close()
print("✨ Both payment tables dropped and migration history cleared successfully!")