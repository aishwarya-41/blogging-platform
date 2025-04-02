from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blog"
    )

@app.route('/')
def home():
    if 'user' in session:
        return redirect('/dashboard')
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT posts.p_id, posts.title, posts.content, user.name,
               comments.c_id, comments.content as comment_content, 
               comment_user.name as comment_author
        FROM posts 
        JOIN user ON posts.u_id = user.u_id
        LEFT JOIN comments ON posts.p_id = comments.p_id
        LEFT JOIN user as comment_user ON comments.u_id = comment_user.u_id
        ORDER BY posts.p_id DESC, comments.c_id ASC
    """)
    posts_data = cursor.fetchall()
    conn.close()
    
    # Organize posts and comments
    posts = {}
    for row in posts_data:
        if row['p_id'] not in posts:
            posts[row['p_id']] = {
                'p_id': row['p_id'],
                'title': row['title'],
                'content': row['content'],
                'author': row['name'],
                'comments': []
            }
        if row['c_id']:  # If there's a comment
            posts[row['p_id']]['comments'].append({
                'c_id': row['c_id'],
                'content': row['comment_content'],
                'author': row['comment_author']
            })
    
    return render_template('index.html', user=session['user'], posts=posts.values())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Get role from login form
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user WHERE email=%s AND role=%s", (email, role))
        user = cursor.fetchone()
        conn.close()
        if user and password == user["password"]:
            session['user'] = user
            return redirect('/dashboard')
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Get role from signup form
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user WHERE email=%s OR name=%s", (email, name))
        if cursor.fetchone():
            conn.close()
            return render_template('signup.html', error="Name or Email already exists!")
        cursor.execute("INSERT INTO user (name, email, password, role) VALUES (%s, %s, %s, %s)", 
                       (name, email, password, role))
        conn.commit()
        conn.close()
        return redirect('/login')
    return render_template('signup.html')

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'user' not in session:
        return redirect('/login')
    title = request.form['title']
    content = request.form['content']
    user_id = session['user']['u_id']
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO posts (title, content, u_id) VALUES (%s, %s, %s)", 
                   (title, content, user_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session:
        return redirect('/login')
    content = request.form['content']
    user_id = session['user']['u_id']
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comments (p_id, u_id, content) VALUES (%s, %s, %s)", 
                   (post_id, user_id, content))
    cursor.execute("SELECT u_id FROM posts WHERE p_id = %s", (post_id,))
    post_owner = cursor.fetchone()
    if post_owner:
        cursor.execute("INSERT INTO notifications (u_id, type, p_id) VALUES (%s, %s, %s)", 
                       (post_owner[0], "New comment on your post", post_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect('/login')
    conn = get_connection()
    cursor = conn.cursor()
    # Get post owner before deletion
    cursor.execute("SELECT u_id FROM posts WHERE p_id = %s", (post_id,))
    post_owner = cursor.fetchone()
    if post_owner:
        cursor.execute("INSERT INTO notifications (u_id, type, p_id) VALUES (%s, %s, %s)", 
                       (post_owner[0], "Your post has been deleted by admin", post_id))
    cursor.execute("DELETE FROM comments WHERE p_id = %s", (post_id,))
    cursor.execute("DELETE FROM posts WHERE p_id = %s", (post_id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect('/login')
    conn = get_connection()
    cursor = conn.cursor()
    # Get comment owner before deletion
    cursor.execute("SELECT u_id FROM comments WHERE c_id = %s", (comment_id,))
    comment_owner = cursor.fetchone()
    if comment_owner:
        cursor.execute("INSERT INTO notifications (u_id, type) VALUES (%s, %s)", 
                       (comment_owner[0], "Your comment has been deleted by admin"))
    cursor.execute("DELETE FROM comments WHERE c_id = %s", (comment_id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/notifications')
def notifications():
    if 'user' not in session:
        return redirect('/login')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT type FROM notifications WHERE u_id = %s", (session['user']['u_id'],))
    notifications = cursor.fetchall()
    cursor.execute("DELETE FROM notifications WHERE u_id = %s", (session['user']['u_id'],))
    conn.commit()
    conn.close()
    return render_template('notifications.html', notifications=notifications)

if __name__ == '__main__':
     app.run(debug=True, port=8080)
