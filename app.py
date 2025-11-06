from flask import Flask, render_template, request, redirect, session
import db_connect   # <-- this imports the file you just created
from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = 'A9f8Jk2!pL#xQ7zR4vM6sT1uW0yE3hB'

# ===================== Database Connection =====================
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",  # replace with your MySQL root password
        database="event_management"
    )

# ===================== Home =====================
@app.route('/')
def home():
    return redirect('/login')

# ===================== Register =====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users(name,email,password,user_type) VALUES(%s,%s,%s,%s)",
            (name, email, password, user_type)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/login')
    return render_template('register.html')

# ===================== Login =====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        account = cursor.fetchone()
        cursor.close()
        conn.close()

        if account:
            session['loggedin'] = True
            session['id'] = account['user_id']
            session['name'] = account['name']
            session['type'] = account['user_type']
            if account['user_type'] == 'customer':
                return redirect('/customer_dashboard')
            else:
                return redirect('/manager_dashboard')
        else:
            msg = 'Incorrect email/password!'
    return render_template('login.html', msg=msg)

# ===================== Logout =====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ===================== Customer Dashboard =====================
@app.route('/customer_dashboard')
def customer_dashboard():
    if 'loggedin' in session and session['type']=='customer':
        conn = db_connect.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('customer_dashboard.html', events=events)
    return redirect('/login')



@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        image_url = request.form['image_url']
        cursor.execute("UPDATE events SET event_name=%s, base_price=%s, image_url=%s WHERE event_id=%s",
                       (name, price, image_url, event_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/manager_dashboard')
    else:
        cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
        event = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template('edit_event.html', event=event)

@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE event_id=%s", (event_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/manager_dashboard')



# ===================== Book Event =====================
@app.route('/book_event/<int:event_id>', methods=['GET', 'POST'])
def book_event(event_id):
    if 'loggedin' not in session or session['type'] != 'customer':
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Event
    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    # Options
    cursor.execute("SELECT * FROM venues")
    venues = cursor.fetchall()
    cursor.execute("SELECT * FROM decoration_teams")
    teams = cursor.fetchall()
    cursor.execute("SELECT * FROM organizers")
    organizers = cursor.fetchall()

    if request.method == 'POST':
        venue_id = request.form.get('venue_id')
        team_id = request.form.get('team_id')
        organizer_id = request.form.get('organizer_id')
        date = request.form.get('date')
        time = request.form.get('time')

        if not all([venue_id, team_id, organizer_id, date, time]):
            return "Please fill all fields", 400

        # Prices
        cursor.execute("SELECT price, image_url FROM venues WHERE venue_id=%s", (venue_id,))
        venue = cursor.fetchone()
        venue_price = venue['price']
        venue_image = venue['image_url']

        cursor.execute("SELECT price FROM decoration_teams WHERE team_id=%s", (team_id,))
        team_price = cursor.fetchone()['price']

        final_price = float(event['base_price']) + float(venue_price) + float(team_price)

        # Insert booking
        cursor.execute("""
            INSERT INTO bookings(customer_id, event_id, venue_id, decoration_team_id, organizer_id, event_date, event_time, final_price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (session['id'], event_id, venue_id, team_id, organizer_id, date, time, final_price))
        conn.commit()

        booking_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return redirect(f'/booking_summary/{booking_id}')

    cursor.close()
    conn.close()
    return render_template('booking_form.html', event=event, venues=venues, teams=teams, organizers=organizers)


# ===================== Booking Summary =====================
@app.route('/booking_summary/<int:booking_id>', methods=['GET', 'POST'])
def booking_summary(booking_id):
    if 'loggedin' not in session or session['type'] != 'customer':
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT b.*, e.event_name, e.image_url as event_image, 
               v.venue_name, v.image_url as venue_image,
               d.team_name
        FROM bookings b
        JOIN events e ON b.event_id = e.event_id
        JOIN venues v ON b.venue_id = v.venue_id
        JOIN decoration_teams d ON b.decoration_team_id = d.team_id
        WHERE b.booking_id=%s
    """, (booking_id,))

    booking = cursor.fetchone()
    cursor.close()
    conn.close()

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET payment_method=%s WHERE booking_id=%s",
                       (payment_method, booking_id))
        conn.commit()
        cursor.close()
        conn.close()
        return "Payment Successful! Thank you for booking."

    return render_template('booking_summary.html', booking=booking)


# ===================== Manager Dashboard =====================
@app.route('/manager_dashboard')
def manager_dashboard():
    if 'loggedin' in session and session['type'] == 'manager':
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('manager_dashboard.html', events=events)
    return redirect('/login')

# ===================== Manager CRUD Routes =====================

@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if 'loggedin' in session and session['type'] == 'manager':
        conn = db_connect.get_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            name = request.form['name']
            price = request.form['price']
            image_url = request.form.get('image_url', '')

            cursor.execute(
                "INSERT INTO events (event_name, base_price, image_url) VALUES (%s, %s, %s)",
                (name, price, image_url)
            )
            conn.commit()

        # Fetch all events to display
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()

        cursor.close()
        conn.close()
        return render_template('add_event.html', events=events)

    return redirect('/login')


@app.route('/add_venue', methods=['GET', 'POST'])
def add_venue():
    if request.method == 'POST':
        venue_name = request.form.get('venue_name')
        price = request.form.get('price')
        image_url = request.form.get('image_url')  # New field

        cursor = get_connection().cursor()
        cursor.execute(
            "INSERT INTO venues (venue_name, price, image_url) VALUES (%s, %s, %s)",
            (venue_name, price, image_url)
        )
        get_connection().commit()
        cursor.close()
        return redirect('/manager_dashboard')

    return render_template('add_venue.html')



@app.route('/add_team', methods=['GET', 'POST'])
def add_team():
    if request.method == 'POST':
        try:
            team_name = request.form['team_name']
            price = request.form['price']

            # Ensure we always have exactly 6 image values
            image_urls = []
            for i in range(1, 7):
                img = request.form.get(f'image{i}', '')
                image_urls.append(img if img.strip() != '' else None)

            # Check the list length
            if len(image_urls) != 6:
                # Should never happen, but just in case
                image_urls += [None] * (6 - len(image_urls))

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decoration_teams
                (team_name, price, image1, image2, image3, image4, image5, image6)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (team_name, price, *image_urls))
            conn.commit()
            cursor.close()
            conn.close()

            return redirect('/manager_dashboard')
        except Exception as e:
            return f"Error: {str(e)}"

    return render_template('add_team.html')


@app.route('/view_teams')
def view_teams():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM decoration_teams")
    teams = cursor.fetchall()
    cursor.close()
    return render_template('view_teams.html', teams=teams)


@app.route('/add_organizer', methods=['GET', 'POST'])
def add_organizer():
    if 'loggedin' in session and session['type'] == 'manager':
        if request.method == 'POST':
            name = request.form['name']
            contact = request.form['contact_no']
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO organizers(name, contact_no) VALUES(%s,%s)", (name, contact))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect('/manager_dashboard')
        return render_template('add_organizer.html')
    return redirect('/login')

@app.route('/view_bookings')
def view_bookings():
    if 'loggedin' in session and session['type'] == 'manager':
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT b.booking_id, u.name as customer_name, e.event_name, v.venue_name, d.team_name, o.name as organizer_name, b.final_price
            FROM bookings b
            JOIN users u ON b.customer_id = u.user_id
            JOIN events e ON b.event_id = e.event_id
            JOIN venues v ON b.venue_id = v.venue_id
            JOIN decoration_teams d ON b.decoration_team_id = d.team_id
            JOIN organizers o ON b.organizer_id = o.organizer_id
            ORDER BY b.booking_id DESC
        """)
        bookings = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('view_bookings.html', bookings=bookings)
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
