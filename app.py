import os, re, sqlite3, csv, io, secrets, hmac, hashlib
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template, flash, Response

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', '')
if not app.secret_key:
    raise RuntimeError('請先設定 SECRET_KEY 環境變數')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','1')=='1', PERMANENT_SESSION_LIFETIME=timedelta(hours=4), MAX_CONTENT_LENGTH=8192)
DATABASE = os.environ.get('DATABASE_PATH', '/data/campaign.sqlite3')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
if len(ADMIN_PASSWORD) < 12:
    raise RuntimeError('請設定至少 12 字元的 ADMIN_PASSWORD')
TZ = timezone(timedelta(hours=8))

def db():
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE)), exist_ok=True)
    con=sqlite3.connect(DATABASE, timeout=15, isolation_level=None)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=15000')
    return con

def init_db():
    with db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS registrations (serial INTEGER PRIMARY KEY CHECK (serial BETWEEN 1 AND 60), name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, purpose TEXT NOT NULL CHECK(purpose IN ("自住", "置產")), created_at TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, created_at TEXT NOT NULL)')
init_db()

def now(): return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
def csrf():
    if 'csrf' not in session: session['csrf']=secrets.token_urlsafe(32)
    return session['csrf']
app.jinja_env.globals['csrf_token']=csrf

def csrf_check():
    return hmac.compare_digest(str(session.get('csrf','')),str(request.form.get('csrf_token',''))) and bool(session.get('csrf'))
def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('admin'): return redirect(url_for('admin_login'))
        return fn(*a,**kw)
    return wrapper

@app.get('/')
def home():
    with db() as con: count=con.execute('SELECT COUNT(*) FROM registrations').fetchone()[0]
    return render_template('index.html',count=count)

@app.post('/register')
def register():
    if not csrf_check(): return '表單已過期，請重新整理',400
    name=request.form.get('name','').strip()[:60]
    phone=re.sub(r'[\s\-]','',request.form.get('phone',''))
    purpose=request.form.get('purpose','')
    if not (2<=len(name)<=40) or not re.fullmatch(r'09\d{8}',phone) or purpose not in ('自住','置產'):
        flash('請填寫正確的姓名、台灣手機號碼，並選擇房產規劃。')
        return redirect(url_for('home'))
    if request.form.get('agree')!='yes':
        flash('請先閱讀並同意個人資料蒐集告知。')
        return redirect(url_for('home'))
    with db() as con:
        try:
            con.execute('BEGIN IMMEDIATE')
            prior=con.execute('SELECT serial FROM registrations WHERE phone=?',(phone,)).fetchone()
            if prior:
                con.execute('COMMIT')
                return render_template('success.html',serial=f'{prior[0]:03d}',duplicate=True)
            n=con.execute('SELECT COALESCE(MAX(serial),0)+1 FROM registrations').fetchone()[0]
            if n>60:
                con.execute('COMMIT')
                return render_template('full.html')
            con.execute('INSERT INTO registrations(serial,name,phone,purpose,created_at) VALUES(?,?,?,?,?)',(n,name,phone,purpose,now()))
            con.execute('COMMIT')
            return render_template('success.html',serial=f'{n:03d}',duplicate=False)
        except Exception:
            con.execute('ROLLBACK')
            raise

@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        if not csrf_check(): return '表單已過期',400
        if hmac.compare_digest(request.form.get('password',''),ADMIN_PASSWORD):
            session.clear(); session['admin']=True; session.permanent=True
            return redirect(url_for('admin'))
        flash('密碼不正確')
    return render_template('login.html')

@app.post('/admin/logout')
@login_required
def logout():
    if not csrf_check(): return '表單已過期',400
    session.clear()
    return redirect(url_for('home'))

@app.get('/admin')
@login_required
def admin():
    q=request.args.get('q','').strip()[:80]
    purpose=request.args.get('purpose','')
    sql='SELECT * FROM registrations WHERE 1=1';args=[]
    if q: sql+=' AND (name LIKE ? OR phone LIKE ? OR printf("%03d",serial) LIKE ?)';args += [f'%{q}%']*3
    if purpose in ('自住','置產'):sql+=' AND purpose=?';args.append(purpose)
    sql+=' ORDER BY serial ASC'
    with db() as con:
        rows=con.execute(sql,args).fetchall()
        count=con.execute('SELECT COUNT(*) FROM registrations').fetchone()[0]
        self_count=con.execute('SELECT COUNT(*) FROM registrations WHERE purpose="自住"').fetchone()[0]
    return render_template('admin.html',rows=rows,count=count,self_count=self_count,q=q,purpose=purpose)

@app.get('/admin/export')
@login_required
def export():
    out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['抽獎序號','姓名','電話','房產規劃','填寫時間'])
    with db() as con:
        for r in con.execute('SELECT * FROM registrations ORDER BY serial'):
            writer.writerow([f'{r["serial"]:03d}',r['name'], "'"+r['phone'],r['purpose'],r['created_at']])
        con.execute('INSERT INTO audit(action,created_at) VALUES (?,?)',('EXPORT_CSV',now()))
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename="campaign-registrations.csv"','Cache-Control':'no-store'})

@app.after_request
def headers(resp):
    resp.headers['X-Content-Type-Options']='nosniff'
    resp.headers['X-Frame-Options']='DENY'
    resp.headers['Referrer-Policy']='no-referrer'
    if request.path.startswith('/admin'):resp.headers['Cache-Control']='no-store'
    return resp

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','8000')))
