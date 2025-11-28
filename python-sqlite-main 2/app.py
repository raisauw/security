from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import sqlite3

# TAMBAHAN BARIS 6-7: Import Flask-Limiter untuk rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# TAMBAHAN BARIS 14: Secret key untuk flash messages
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production-12345'

db = SQLAlchemy(app)

# TAMBAHAN BARIS 19-24: Inisialisasi Flask-Limiter dengan konfigurasi
limiter = Limiter(
    app=app,
    key_func=get_remote_address,  # Rate limit berdasarkan IP address
    default_limits=["200 per day", "50 per hour"],  # Global rate limits
    storage_uri="memory://"  # Storage untuk tracking limits
)

# TAMBAHAN BARIS 27-31: Konstanta untuk validasi input dan database limits
MAX_NAME_LENGTH = 100
MAX_GRADE_LENGTH = 10
MIN_AGE = 1
MAX_AGE = 150
MAX_RECORDS_SOFT_LIMIT = 1000  # Warning threshold
MAX_RECORDS_HARD_LIMIT = 5000  # Absolute blocking threshold

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(10), nullable=False)

    def __repr__(self):
        return f'<Student {self.name}>'

# TAMBAHAN BARIS 46-56: Helper function untuk cek database capacity
def check_record_limit():
    """
    Memeriksa apakah database sudah mencapai atau mendekati limit.
    Returns: (bool, str) - (can_add, error_message)
    """
    count = Student.query.count()
    
    if count >= MAX_RECORDS_HARD_LIMIT:
        return False, f"Database full! Maximum {MAX_RECORDS_HARD_LIMIT} records reached. Cannot add more students."
    elif count >= MAX_RECORDS_SOFT_LIMIT:
        flash(f'Warning: Database has {count} records (approaching limit: {MAX_RECORDS_SOFT_LIMIT})', 'warning')
    
    return True, None

# TAMBAHAN BARIS 58-82: Helper function untuk validasi input
def validate_student_input(name, age, grade):
    """
    Memvalidasi input data siswa sebelum disimpan ke database.
    Returns: list - daftar error messages (kosong jika valid)
    """
    errors = []
    
    # Validasi name: tidak boleh kosong dan tidak boleh terlalu panjang
    if not name or len(name.strip()) == 0:
        errors.append("Name cannot be empty")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Name too long (maximum {MAX_NAME_LENGTH} characters)")
    
    # Validasi age: harus angka dan dalam range yang wajar
    try:
        age_int = int(age)
        if age_int < MIN_AGE or age_int > MAX_AGE:
            errors.append(f"Age must be between {MIN_AGE} and {MAX_AGE}")
    except (ValueError, TypeError):
        errors.append("Age must be a valid number")
    
    # Validasi grade: tidak boleh kosong dan tidak boleh terlalu panjang
    if not grade or len(grade.strip()) == 0:
        errors.append("Grade cannot be empty")
    elif len(grade) > MAX_GRADE_LENGTH:
        errors.append(f"Grade too long (maximum {MAX_GRADE_LENGTH} characters)")
    
    return errors

@app.route('/')
def index():
    # KODE TIDAK BERUBAH - Endpoint read-only tidak perlu rate limiting
    students = db.session.execute(text('SELECT * FROM student')).fetchall()
    return render_template('index.html', students=students)

# MODIFIKASI BARIS 95-120: Tambahkan rate limiting dan validasi pada endpoint add
@app.route('/add', methods=['POST'])
@limiter.limit("10 per minute")  # TAMBAHAN: Rate limit 10 requests/menit
def add_student():
    name = request.form.get('name', '')
    age = request.form.get('age', '')
    grade = request.form.get('grade', '')
    
    # TAMBAHAN BARIS 103-108: Validasi input sebelum diproses
    validation_errors = validate_student_input(name, age, grade)
    if validation_errors:
        for error in validation_errors:
            flash(error, 'error')
        return redirect(url_for('index'))
    
    # TAMBAHAN BARIS 110-114: Cek apakah database sudah penuh
    can_add, error_msg = check_record_limit()
    if not can_add:
        flash(error_msg, 'error')
        return redirect(url_for('index'))
    
    # MODIFIKASI BARIS 116-127: Ganti raw query dengan parameterized query
    try:
        # KODE LAMA (DIHAPUS):
        # connection = sqlite3.connect('instance/students.db')
        # cursor = connection.cursor()
        # query = f"INSERT INTO student (name, age, grade) VALUES ('{name}', {age}, '{grade}')"
        # cursor.execute(query)
        # connection.commit()
        # connection.close()
        
        # KODE BARU: Gunakan parameterized query untuk keamanan
        db.session.execute(
            text("INSERT INTO student (name, age, grade) VALUES (:name, :age, :grade)"),
            {'name': name.strip(), 'age': int(age), 'grade': grade.strip()}
        )
        db.session.commit()
        flash('Student added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding student: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# MODIFIKASI BARIS 133-152: Tambahkan rate limiting dan validasi pada endpoint delete
@app.route('/delete/<string:id>')
@limiter.limit("20 per minute")  # TAMBAHAN: Rate limit 20 requests/menit
def delete_student(id):
    # TAMBAHAN BARIS 138-142: Validasi ID untuk mencegah SQL injection
    try:
        id_int = int(id)
    except (ValueError, TypeError):
        flash('Invalid student ID', 'error')
        return redirect(url_for('index'))
    
    # MODIFIKASI BARIS 144-155: Ganti raw query dengan parameterized query
    try:
        # KODE LAMA (DIHAPUS):
        # db.session.execute(text(f"DELETE FROM student WHERE id={id}"))
        
        # KODE BARU: Gunakan parameterized query
        result = db.session.execute(
            text("DELETE FROM student WHERE id=:id"), 
            {'id': id_int}
        )
        db.session.commit()
        
        if result.rowcount > 0:
            flash('Student deleted successfully!', 'success')
        else:
            flash('Student not found', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# MODIFIKASI BARIS 161-198: Tambahkan rate limiting dan validasi pada endpoint edit
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@limiter.limit("15 per minute")  # TAMBAHAN: Rate limit 15 requests/menit
def edit_student(id):
    if request.method == 'POST':
        name = request.form.get('name', '')
        age = request.form.get('age', '')
        grade = request.form.get('grade', '')
        
        # TAMBAHAN BARIS 169-174: Validasi input
        validation_errors = validate_student_input(name, age, grade)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'error')
            return redirect(url_for('edit_student', id=id))
        
        # MODIFIKASI BARIS 176-190: Ganti raw query dengan parameterized query
        try:
            # KODE LAMA (DIHAPUS):
            # db.session.execute(text(f"UPDATE student SET name='{name}', age={age}, grade='{grade}' WHERE id={id}"))
            
            # KODE BARU: Gunakan parameterized query
            db.session.execute(
                text("UPDATE student SET name=:name, age=:age, grade=:grade WHERE id=:id"),
                {'name': name.strip(), 'age': int(age), 'grade': grade.strip(), 'id': id}
            )
            db.session.commit()
            flash('Student updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'error')
        
        return redirect(url_for('index'))
    else:
        # MODIFIKASI BARIS 192-205: Ganti raw query dengan parameterized query
        try:
            # KODE LAMA (DIHAPUS):
            # student = db.session.execute(text(f"SELECT * FROM student WHERE id={id}")).fetchone()
            
            # KODE BARU: Gunakan parameterized query
            student = db.session.execute(
                text("SELECT * FROM student WHERE id=:id"),
                {'id': id}
            ).fetchone()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('index'))
            
            return render_template('edit.html', student=student)
        except Exception as e:
            flash(f'Error fetching student: {str(e)}', 'error')
            return redirect(url_for('index'))

# TAMBAHAN BARIS 208-215: Custom error handler untuk rate limit exceeded
@app.errorhandler(429)
def ratelimit_handler(e):
    """Handler untuk HTTP 429 Too Many Requests"""
    return jsonify(
        error="Rate limit exceeded",
        message="Too many requests. Please slow down and try again later.",
        retry_after=str(e.description)
    ), 429

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
