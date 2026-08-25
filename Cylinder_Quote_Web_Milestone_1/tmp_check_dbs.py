import sqlite3
for db in ['instance/Employee_Contacts.db','instance/Quote.db']:
    print('\n'+db)
    conn=sqlite3.connect(db)
    tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print('tables:', tables)
    for t in tables:
        print(t+':', conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0])
