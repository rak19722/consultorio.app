import sqlite3

conn = sqlite3.connect('base.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
''')

cursor.execute('''
INSERT OR IGNORE INTO users (email, password)
VALUES (?, ?)
''', ('doctor@example.com', 'doc123'))

conn.commit()
conn.close()

print("Base de datos inicializada con éxito.")
