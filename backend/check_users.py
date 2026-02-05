from database import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT id, username, email, created_at FROM users ORDER BY id')
    users = cur.fetchall()

    print("Users in database:")
    print("-" * 80)
    for user in users:
        print(f"ID: {user['id']}, Username: {user['username']}, Email: {user['email']}, Created: {user['created_at']}")
    print("-" * 80)
    print(f"Total users: {len(users)}")
