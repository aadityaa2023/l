import sqlite3

def main():
    db = 'db.sqlite3'
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('platformadmin_teammember')")
        rows = cur.fetchall()
        if not rows:
            print('NO_TABLE')
        else:
            for r in rows:
                print(r)
    except Exception as e:
        print('ERROR', e)
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == '__main__':
    main()
