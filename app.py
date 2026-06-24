"""
Derna Facilities Management — Inventory Web App
Flask backend with SQLite, role-based access (viewer / storekeeper).

Deploy on Render.com (free tier) — see README.md for instructions.
"""

import os, json, base64, uuid
from datetime import datetime, date
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'derna-inv-secret-2025-change-me')

# SQLite DB — stored in /data on Render (persistent disk) or locally
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'inventory.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Storekeeper password — set via environment variable on Render
SK_PASSWORD = os.environ.get('SK_PASSWORD', 'derna2025')
SK_USERNAME = os.environ.get('SK_USERNAME', 'storekeeper')

db = SQLAlchemy(app)

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────────────────────────────────────
class Item(db.Model):
    __tablename__ = 'items'
    id       = db.Column(db.String(32), primary_key=True, default=lambda: 'u'+str(uuid.uuid4())[:8])
    cat      = db.Column(db.String(32), nullable=False)
    name     = db.Column(db.String(200), nullable=False)
    unit     = db.Column(db.String(32), nullable=False)
    opening  = db.Column(db.Float, default=0)
    safety   = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, cat=self.cat, name=self.name,
                    unit=self.unit, opening=self.opening, safety=self.safety)


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id       = db.Column(db.String(32), primary_key=True, default=lambda: 'x'+str(uuid.uuid4())[:10])
    type     = db.Column(db.String(3), nullable=False)   # IN / OUT
    date     = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    item_id  = db.Column(db.String(32), db.ForeignKey('items.id'), nullable=False)
    qty      = db.Column(db.Float, nullable=False)
    ref      = db.Column(db.String(200))
    person   = db.Column(db.String(100))
    building = db.Column(db.String(100))
    remarks  = db.Column(db.Text)
    delivery_note_data = db.Column(db.Text)   # base64 data-URI
    delivery_note_name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(
            id=self.id, type=self.type, date=self.date, itemId=self.item_id,
            qty=self.qty, ref=self.ref or '', person=self.person or '',
            building=self.building or '', remarks=self.remarks or '',
            deliveryNote=(dict(dataUri=self.delivery_note_data,
                               name=self.delivery_note_name)
                          if self.delivery_note_data else None),
            at=self.created_at.isoformat() if self.created_at else ''
        )


# ─────────────────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def is_storekeeper():
    return session.get('role') == 'storekeeper'

def sk_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_storekeeper():
            return jsonify({'error': 'Unauthorised — storekeeper login required'}), 403
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT SEED DATA
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_ITEMS = [
  # Hospitality
  {'id':'h1','cat':'Hospitality','name':'NOVA WATER PLASTIC 1X40','unit':'cartoon','opening':149,'safety':300},
  {'id':'h2','cat':'Hospitality','name':'NOVA WATER GLASS 1X24','unit':'cartoon','opening':1,'safety':30},
  {'id':'h3','cat':'Hospitality','name':'Almarai Milk 1 Liter','unit':'pcs','opening':40,'safety':84},
  {'id':'h4','cat':'Hospitality','name':'DUNKIN COFFEE 1X24','unit':'packet','opening':35,'safety':10},
  {'id':'h5','cat':'Hospitality','name':'PAPER CUP LARGE 8 OZ','unit':'pcs','opening':2440,'safety':3000},
  {'id':'h6','cat':'Hospitality','name':'PAPER CUP SMALL 4 OZ','unit':'pcs','opening':2190,'safety':500},
  {'id':'h7','cat':'Hospitality','name':'PAPER CUP COVER LARGE','unit':'pcs','opening':2050,'safety':500},
  {'id':'h8','cat':'Hospitality','name':'PAPER CUP COVER SMALL','unit':'pcs','opening':1250,'safety':500},
  {'id':'h9','cat':'Hospitality','name':'NESCAFE CLASSIC','unit':'pcs','opening':62,'safety':10},
  {'id':'h10','cat':'Hospitality','name':'ARABIANA COFFEE','unit':'packet','opening':42,'safety':10},
  {'id':'h11','cat':'Hospitality','name':'COFFEE MATE','unit':'pcs','opening':108,'safety':15},
  {'id':'h12','cat':'Hospitality','name':'COFFEE BEANS','unit':'packet','opening':63,'safety':20},
  {'id':'h13','cat':'Hospitality','name':'TURKISH COFFEE','unit':'packet','opening':75,'safety':5},
  {'id':'h14','cat':'Hospitality','name':'WOODEN STIRRER','unit':'box','opening':132,'safety':10},
  {'id':'h15','cat':'Hospitality','name':'WHITE SUGAR STICK','unit':'box','opening':122,'safety':10},
  {'id':'h16','cat':'Hospitality','name':'SUGAR (AL OSRA) 1X20','unit':'bag','opening':61,'safety':15},
  {'id':'h17','cat':'Hospitality','name':'RED TEA - LIPTON','unit':'box','opening':5,'safety':15},
  {'id':'h18','cat':'Hospitality','name':'GREEN TEA','unit':'box','opening':105,'safety':10},
  {'id':'h19','cat':'Hospitality','name':'OCTOBER COFFEE','unit':'packet','opening':90,'safety':50},
  {'id':'h20','cat':'Hospitality','name':'SILKY SUFRA','unit':'roll','opening':110,'safety':20},
  {'id':'h21','cat':'Hospitality','name':'STEVIANA LEAVE','unit':'pcs','opening':87,'safety':10},
  {'id':'h22','cat':'Hospitality','name':'Bonny Milk 170x96g','unit':'pcs','opening':282,'safety':50},
  {'id':'h23','cat':'Hospitality','name':'PAPER PLATE','unit':'pcs','opening':187,'safety':100},
  {'id':'h24','cat':'Hospitality','name':'CUTLERY SET','unit':'pcs','opening':3586,'safety':200},
  {'id':'h25','cat':'Hospitality','name':'SPOON LARGE','unit':'pcs','opening':750,'safety':500},
  {'id':'h26','cat':'Hospitality','name':'SPOON SMALL','unit':'pcs','opening':6108,'safety':500},
  {'id':'h27','cat':'Hospitality','name':'PLASTIC PLATE SMALL','unit':'pcs','opening':300,'safety':500},
  {'id':'h28','cat':'Hospitality','name':'PLASTIC TRAY LARGE','unit':'pcs','opening':300,'safety':500},
  {'id':'h29','cat':'Hospitality','name':'STRAW','unit':'pcs','opening':100,'safety':300},
  {'id':'h30','cat':'Hospitality','name':'ESPRESSO CAPSULES','unit':'box','opening':34,'safety':25},
  {'id':'h31','cat':'Hospitality','name':'COFFEE FILTERS','unit':'packet','opening':9,'safety':10},
  {'id':'h32','cat':'Hospitality','name':'HIBISCUS','unit':'box','opening':0,'safety':2},
  {'id':'h33','cat':'Hospitality','name':'SPARKLING WATER 1x24','unit':'cartoon','opening':22,'safety':5},
  {'id':'h34','cat':'Hospitality','name':'JUICE CUP (1x50)','unit':'pcs','opening':3200,'safety':500},
  {'id':'h35','cat':'Hospitality','name':'JUICE CUP COVER','unit':'pcs','opening':3575,'safety':500},
  {'id':'h36','cat':'Hospitality','name':'WATER GALLON','unit':'pcs','opening':17,'safety':10},
  # Cleaning
  {'id':'c1','cat':'Cleaning','name':'Fine Tissue Roll','unit':'pcs','opening':202,'safety':100},
  {'id':'c2','cat':'Cleaning','name':'Interfold Tissue','unit':'pcs','opening':230,'safety':100},
  {'id':'c3','cat':'Cleaning','name':'Outkat Tissue Roll','unit':'roll','opening':0,'safety':25},
  {'id':'c4','cat':'Cleaning','name':'Bathroom Tissue Roll','unit':'roll','opening':5,'safety':100},
  {'id':'c5','cat':'Cleaning','name':'Garbage Bag 55 Gallon','unit':'bag','opening':90,'safety':30},
  {'id':'c6','cat':'Cleaning','name':'Garbage Bags 10 Gallon','unit':'roll','opening':5,'safety':25},
  {'id':'c7','cat':'Cleaning','name':'Lux Hand Soap','unit':'pcs','opening':89,'safety':20},
  {'id':'c8','cat':'Cleaning','name':'Cloth','unit':'pcs','opening':28,'safety':10},
  {'id':'c9','cat':'Cleaning','name':'Cottage Airfreshner','unit':'pcs','opening':51,'safety':30},
  {'id':'c10','cat':'Cleaning','name':'Lamont Airfreshner','unit':'pcs','opening':67,'safety':5},
  {'id':'c11','cat':'Cleaning','name':'Norsina Airfreshner','unit':'pcs','opening':0,'safety':5},
  {'id':'c12','cat':'Cleaning','name':'Dry Mop','unit':'pcs','opening':12,'safety':5},
  {'id':'c13','cat':'Cleaning','name':'Wet Mop','unit':'pcs','opening':20,'safety':5},
  {'id':'c14','cat':'Cleaning','name':'Hand Gloves','unit':'pcs','opening':53,'safety':20},
  {'id':'c15','cat':'Cleaning','name':'Face Mask','unit':'pcs','opening':70,'safety':20},
  {'id':'c16','cat':'Cleaning','name':'Sponge','unit':'pcs','opening':77,'safety':10},
  {'id':'c17','cat':'Cleaning','name':'Furniture Polish','unit':'pcs','opening':14,'safety':15},
  {'id':'c18','cat':'Cleaning','name':'Steel Polish','unit':'pcs','opening':66,'safety':5},
  {'id':'c19','cat':'Cleaning','name':'Oven Cleaner','unit':'pcs','opening':10,'safety':5},
  {'id':'c20','cat':'Cleaning','name':'Raid','unit':'pcs','opening':53,'safety':5},
  {'id':'c21','cat':'Cleaning','name':'Sanitizer','unit':'pcs','opening':86,'safety':5},
  {'id':'c22','cat':'Cleaning','name':'Harpic','unit':'pcs','opening':55,'safety':5},
  {'id':'c23','cat':'Cleaning','name':'Gento','unit':'pcs','opening':6,'safety':5},
  {'id':'c24','cat':'Cleaning','name':'Fairy','unit':'pcs','opening':82,'safety':5},
  {'id':'c25','cat':'Cleaning','name':'Dettol','unit':'pcs','opening':2,'safety':10},
  {'id':'c26','cat':'Cleaning','name':'Rana All Purpose','unit':'litre','opening':82,'safety':10},
  {'id':'c27','cat':'Cleaning','name':'Toilet Brush','unit':'pcs','opening':6,'safety':20},
  {'id':'c28','cat':'Cleaning','name':'All Purpose Chemical','unit':'litre','opening':85,'safety':20},
  {'id':'c29','cat':'Cleaning','name':'Floor Wiper','unit':'pcs','opening':19,'safety':5},
  {'id':'c30','cat':'Cleaning','name':'Glass Cleaner Chemical','unit':'pcs','opening':2,'safety':5},
  {'id':'c31','cat':'Cleaning','name':'Dust Feather','unit':'pcs','opening':7,'safety':5},
  {'id':'c32','cat':'Cleaning','name':'Glass Cleaner Wiper','unit':'pcs','opening':2,'safety':5},
  {'id':'c33','cat':'Cleaning','name':'Cotton Glass Wiper','unit':'pcs','opening':1,'safety':30},
  {'id':'c34','cat':'Cleaning','name':'Spray Gallon Plastic','unit':'pcs','opening':13,'safety':10},
  {'id':'c35','cat':'Cleaning','name':'Carpet Cleaner','unit':'litre','opening':20,'safety':20},
  {'id':'c36','cat':'Cleaning','name':'Broom Brush','unit':'pcs','opening':13,'safety':25},
  {'id':'c37','cat':'Cleaning','name':'Broom With Dustpan','unit':'pcs','opening':23,'safety':30},
  {'id':'c38','cat':'Cleaning','name':'Mop Stick','unit':'pcs','opening':5,'safety':100},
  {'id':'c39','cat':'Cleaning','name':'Dust Pan','unit':'pcs','opening':8,'safety':25},
  {'id':'c40','cat':'Cleaning','name':'Glass Cleaner','unit':'pcs','opening':36,'safety':100},
  {'id':'c41','cat':'Cleaning','name':'Mop Holder','unit':'pcs','opening':0,'safety':100},
  {'id':'c42','cat':'Cleaning','name':'Wet Tissue','unit':'box','opening':891,'safety':40},
  # Maintenance
  {'id':'m1','cat':'Maintenance','name':'7W LED Bulb K-RAY','unit':'pcs','opening':33,'safety':5},
  {'id':'m2','cat':'Maintenance','name':'7W LED Bulb PHILIPS','unit':'pcs','opening':10,'safety':2},
  {'id':'m3','cat':'Maintenance','name':'6W LED Bulb FSL','unit':'pcs','opening':18,'safety':2},
  {'id':'m4','cat':'Maintenance','name':'7W LED Lamp SPARKLING','unit':'pcs','opening':22,'safety':5},
  {'id':'m5','cat':'Maintenance','name':'9W LED Bulb K-RAY','unit':'pcs','opening':1,'safety':5},
  {'id':'m6','cat':'Maintenance','name':'12W LED Bulb MFZ','unit':'pcs','opening':4,'safety':5},
  {'id':'m7','cat':'Maintenance','name':'5W LED Bulb JAMS','unit':'pcs','opening':17,'safety':5},
  {'id':'m8','cat':'Maintenance','name':'8W Bulb MOVAL','unit':'pcs','opening':1,'safety':1},
  {'id':'m9','cat':'Maintenance','name':'26W Bulb OSRAM','unit':'pcs','opening':5,'safety':2},
  {'id':'m10','cat':'Maintenance','name':'150W Bulb PHILIPS','unit':'pcs','opening':2,'safety':2},
  {'id':'m11','cat':'Maintenance','name':'4W Bulb MOVAL','unit':'pcs','opening':16,'safety':2},
  {'id':'m12','cat':'Maintenance','name':'18W LED Bulb OMAHA','unit':'pcs','opening':1,'safety':1},
  {'id':'m13','cat':'Maintenance','name':'5W LED Warm KODAK','unit':'pcs','opening':7,'safety':2},
  {'id':'m14','cat':'Maintenance','name':'10W Garden Lamp RMAX','unit':'pcs','opening':9,'safety':2},
  {'id':'m15','cat':'Maintenance','name':'20W Garden Light SIERA','unit':'pcs','opening':2,'safety':1},
  {'id':'m16','cat':'Maintenance','name':'LED Tube 18W PHILIPS','unit':'pcs','opening':10,'safety':5},
  {'id':'m17','cat':'Maintenance','name':'15W Bulb WONDERFUL','unit':'pcs','opening':0,'safety':1},
  {'id':'m18','cat':'Maintenance','name':'15W Bulb DANLIGHT','unit':'pcs','opening':4,'safety':1},
  {'id':'m19','cat':'Maintenance','name':'C2 Battery','unit':'pcs','opening':11,'safety':2},
  {'id':'m20','cat':'Maintenance','name':'Board Cover XL','unit':'pcs','opening':3,'safety':0},
  {'id':'m21','cat':'Maintenance','name':'Board Cover Large','unit':'pcs','opening':3,'safety':0},
  {'id':'m22','cat':'Maintenance','name':'Board Cover Medium','unit':'pcs','opening':4,'safety':0},
  {'id':'m23','cat':'Maintenance','name':'Board Cover Small','unit':'pcs','opening':5,'safety':0},
  {'id':'m24','cat':'Maintenance','name':'Double Switch White','unit':'pcs','opening':1,'safety':2},
  {'id':'m25','cat':'Maintenance','name':'FLB Switch 3 Pin Black','unit':'pcs','opening':10,'safety':1},
  {'id':'m26','cat':'Maintenance','name':'Plug 3 Pin','unit':'pcs','opening':10,'safety':5},
  {'id':'m27','cat':'Maintenance','name':'Plug Fuse','unit':'pcs','opening':8,'safety':1},
  {'id':'m28','cat':'Maintenance','name':'Hand Shower Set','unit':'set','opening':37,'safety':5},
  {'id':'m29','cat':'Maintenance','name':'Hand Shower Unit White','unit':'pcs','opening':46,'safety':5},
  {'id':'m30','cat':'Maintenance','name':'Hand Shower Unit Silver','unit':'pcs','opening':42,'safety':5},
  {'id':'m31','cat':'Maintenance','name':'Discharger Rubber Set','unit':'pcs','opening':49,'safety':5},
  {'id':'m32','cat':'Maintenance','name':'Dual Flush Mechanism','unit':'pcs','opening':40,'safety':5},
  {'id':'m33','cat':'Maintenance','name':'Hand Shower Pipe','unit':'pcs','opening':72,'safety':2},
  {'id':'m34','cat':'Maintenance','name':'Hose Pipe Flush','unit':'pcs','opening':9,'safety':2},
  {'id':'m35','cat':'Maintenance','name':'Genetron 410A Refrigerant','unit':'pcs','opening':1,'safety':1},
  {'id':'m36','cat':'Maintenance','name':'Genetron 22 Refrigerant','unit':'pcs','opening':2,'safety':1},
  {'id':'m37','cat':'Maintenance','name':'Insulation Tape','unit':'pcs','opening':0,'safety':5},
  {'id':'m38','cat':'Maintenance','name':'Capacitor 70 UF','unit':'pcs','opening':2,'safety':1},
  {'id':'m39','cat':'Maintenance','name':'Capacitor 55 UF','unit':'pcs','opening':3,'safety':1},
  {'id':'m40','cat':'Maintenance','name':'Capacitor 3 UF','unit':'pcs','opening':4,'safety':1},
  {'id':'m41','cat':'Maintenance','name':'Capacitor 4 UF','unit':'pcs','opening':4,'safety':1},
]

def seed_items():
    if Item.query.count() == 0:
        for d in DEFAULT_ITEMS:
            db.session.add(Item(**d))
        db.session.commit()
        print(f"[seed] Seeded {len(DEFAULT_ITEMS)} items.")

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Auth
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if username == SK_USERNAME and password == SK_PASSWORD:
        session['role'] = 'storekeeper'
        session['username'] = username
        return jsonify({'ok': True, 'role': 'storekeeper'})
    return jsonify({'ok': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
def me():
    return jsonify({'role': session.get('role', 'viewer'),
                    'username': session.get('username', '')})

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Items
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/items', methods=['GET'])
def get_items():
    return jsonify([i.to_dict() for i in Item.query.order_by(Item.cat, Item.name).all()])

@app.route('/api/items', methods=['POST'])
@sk_required
def add_item():
    d = request.get_json()
    name = d.get('name','').strip()
    cat  = d.get('cat','').strip()
    unit = d.get('unit','').strip()
    if not name or not cat or not unit:
        return jsonify({'error': 'name, cat and unit are required'}), 400
    if Item.query.filter_by(name=name, cat=cat).first():
        return jsonify({'error': 'Item already exists in this category'}), 409
    item = Item(cat=cat, name=name, unit=unit,
                opening=float(d.get('opening',0)),
                safety=float(d.get('safety',0)))
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201

@app.route('/api/items/<item_id>', methods=['DELETE'])
@sk_required
def del_item(item_id):
    item = Item.query.get_or_404(item_id)
    Transaction.query.filter_by(item_id=item_id).delete()
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Transactions
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    txns = Transaction.query.order_by(Transaction.date.desc(),
                                       Transaction.created_at.desc()).all()
    return jsonify([t.to_dict() for t in txns])

@app.route('/api/transactions', methods=['POST'])
@sk_required
def add_transaction():
    d = request.get_json()
    item_id = d.get('itemId','').strip()
    txn_type = d.get('type','').strip().upper()
    txn_date = d.get('date','').strip()
    qty = float(d.get('qty', 0))
    if not item_id or not txn_type or not txn_date or qty <= 0:
        return jsonify({'error': 'itemId, type, date and qty > 0 are required'}), 400
    if txn_type not in ('IN','OUT'):
        return jsonify({'error': 'type must be IN or OUT'}), 400
    if not Item.query.get(item_id):
        return jsonify({'error': 'Item not found'}), 404

    dn = d.get('deliveryNote')
    txn = Transaction(
        type=txn_type, date=txn_date, item_id=item_id, qty=qty,
        ref=d.get('ref',''), person=d.get('person',''),
        building=d.get('building',''), remarks=d.get('remarks',''),
        delivery_note_data=dn.get('dataUri') if dn else None,
        delivery_note_name=dn.get('name') if dn else None,
    )
    db.session.add(txn)
    db.session.commit()
    return jsonify(txn.to_dict()), 201

@app.route('/api/transactions/<txn_id>', methods=['DELETE'])
@sk_required
def del_transaction(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    db.session.delete(txn)
    db.session.commit()
    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDED TEMPLATE (no templates/ folder needed)
# ─────────────────────────────────────────────────────────────────────────────
INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Derna FM — Inventory</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.5.0/dist/tabler-icons.min.css">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --green:#0F6E56;--green2:#1D9E75;--green-light:#E1F5EE;
  --orange:#E07B20;--blue:#378ADD;--coral:#D85A30;
  --bg:#f0f2f5;--card:#fff;--border:#e2e2e2;--border2:#d0d0d0;
  --txt:#1a1a1a;--txt2:#6b6b6b;--txt3:#9b9b9b;
  --font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
}
body{font-family:var(--font);background:var(--bg);color:var(--txt);min-height:100vh}

/* ── HEADER ── */
.hdr{background:linear-gradient(135deg,#0a4a38 0%,#0F6E56 100%);color:#fff;padding:10px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:500;box-shadow:0 2px 8px rgba(0,0,0,.18)}
.hdr-left{display:flex;align-items:center;gap:12px}
.hdr-left img{height:44px;width:auto;background:#fff;border-radius:8px;padding:3px 8px;object-fit:contain}
.hdr-left h1{font-size:15px;font-weight:600;line-height:1.2}
.hdr-left p{font-size:11px;opacity:.75}
.hdr-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.hbtn{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);color:#fff;border-radius:8px;padding:6px 12px;font-size:12px;cursor:pointer;display:flex;align-items:center;gap:5px;transition:background .15s}
.hbtn:hover{background:rgba(255,255,255,.28)}
.role-badge{font-size:11px;padding:3px 10px;border-radius:20px;font-weight:600}
.role-sk{background:#E07B20;color:#fff}
.role-view{background:rgba(255,255,255,.2);color:#fff}

/* ── NAV ── */
.nav{display:flex;gap:4px;padding:10px 16px 0;background:#fff;border-bottom:1px solid var(--border);overflow-x:auto;position:sticky;top:65px;z-index:400}
.navbtn{background:none;border:none;border-bottom:2px solid transparent;padding:8px 14px;font-size:13px;color:var(--txt2);cursor:pointer;display:flex;align-items:center;gap:6px;white-space:nowrap;transition:all .15s;border-radius:6px 6px 0 0}
.navbtn:hover{color:var(--green);background:var(--green-light)}
.navbtn.active{color:var(--green);border-bottom-color:var(--green);font-weight:600}
.sk-only{display:none}
body.sk .sk-only{display:flex}

/* ── LAYOUT ── */
.page{padding:16px;max-width:1300px;margin:0 auto}
.hidden{display:none!important}
.card{background:var(--card);border-radius:12px;border:1px solid var(--border);padding:16px;margin-bottom:14px}
.ch3{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;font-size:14px;font-weight:600;color:var(--txt);gap:8px}
.g4{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:14px}
.g3{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:14px}
.kpi{border-radius:12px;padding:16px;border:1px solid var(--border)}
.kpi-green{background:linear-gradient(135deg,#E1F5EE,#c8f0e0)}
.kpi-blue{background:linear-gradient(135deg,#E6F1FB,#cce0f5)}
.kpi-coral{background:linear-gradient(135deg,#FCEAE6,#f5d0c8)}
.kpi-amber{background:linear-gradient(135deg,#FEF3E2,#fde6bc)}
.klbl{font-size:11px;color:var(--txt2);font-weight:500;margin-bottom:4px}
.kval{font-size:28px;font-weight:700;color:var(--txt)}
.ksub{font-size:11px;color:var(--txt3);margin-top:2px}

/* ── TABLE ── */
.wrap{overflow-x:auto;border-radius:8px;border:1px solid var(--border)}
table{border-collapse:collapse;width:100%;min-width:500px;font-size:12.5px}
thead tr{background:#f7f7f7}
th{padding:9px 10px;text-align:left;font-weight:600;color:var(--txt2);white-space:nowrap;border-bottom:1px solid var(--border)}
td{padding:8px 10px;border-bottom:1px solid #f0f0f0;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafafa}

/* ── FORM ── */
.form-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-bottom:10px}
.fld{display:flex;flex-direction:column;gap:4px}
.fld label{font-size:12px;font-weight:500;color:var(--txt2)}
.fld input,.fld select,.fld textarea{border:1px solid var(--border2);border-radius:8px;padding:7px 10px;font-size:13px;font-family:var(--font);outline:none;transition:border .15s;background:#fff;color:var(--txt)}
.fld input:focus,.fld select:focus,.fld textarea:focus{border-color:var(--green2)}
.fld textarea{resize:vertical;min-height:60px}
.btn-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}

/* ── BUTTONS ── */
.btn-p{background:var(--green2);color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-family:var(--font);transition:background .15s}
.btn-p:hover{background:var(--green)}
.btn-s{background:#fff;color:var(--txt2);border:1px solid var(--border2);border-radius:8px;padding:7px 14px;font-size:13px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-family:var(--font);transition:all .15s}
.btn-s:hover{border-color:var(--green2);color:var(--green)}
.btn-r{background:var(--green-light);color:var(--green);border:1px solid #b8e8d5;border-radius:8px;padding:7px 14px;font-size:13px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-family:var(--font)}
.ico-del{background:none;border:none;cursor:pointer;color:#ccc;padding:3px;border-radius:4px;transition:color .15s}
.ico-del:hover{color:#D85A30}

/* ── BADGES ── */
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:500}
.bin{background:#E1F5EE;color:#085041}
.bout{background:#FCEAE6;color:#7A2A1A}
.bh{background:#E1F5EE;color:#085041}
.bc{background:#E6F1FB;color:#0C447C}
.bm{background:#FEF0E6;color:#7A3A10}
.bok{background:#E1F5EE;color:#085041}
.blow{background:#FEF3E2;color:#7A4A00}
.bcrit{background:#FCEAE6;color:#7A1A1A}
.bzero{background:#F0F0F0;color:#666}

/* ── TOOLBAR ── */
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.toolbar input,.toolbar select{border:1px solid var(--border2);border-radius:8px;padding:6px 10px;font-size:12.5px;outline:none;background:#fff}
.toolbar input:focus,.toolbar select:focus{border-color:var(--green2)}
.pi{font-size:12px;color:var(--txt3)}

/* ── ALERTS ── */
.alert-bar{background:#FCEAE6;border:1px solid #f5c5b5;border-radius:10px;padding:10px 14px;margin-bottom:14px;font-size:12.5px;color:#7A2A1A;display:none}
.merr{color:#A32D2D;font-size:12.5px;margin-top:6px;padding:6px 10px;background:#FEF0EE;border-radius:6px}
.mok{color:#085041;font-size:12.5px;margin-top:6px;padding:6px 10px;background:#E1F5EE;border-radius:6px}

/* ── MODAL ── */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:800;display:flex;align-items:center;justify-content:center;padding:16px}
.modal-box{background:#fff;border-radius:14px;padding:24px;width:100%;max-width:480px;max-height:90vh;overflow-y:auto;box-shadow:0 8px 40px rgba(0,0,0,.2)}
.modal-box.wide{max-width:820px}
.modal-close{float:right;background:transparent;border:none;font-size:20px;cursor:pointer;color:var(--txt2);line-height:1}
.modal-title{font-size:15px;font-weight:600;color:var(--green);margin-bottom:4px;display:flex;align-items:center;gap:8px}
.modal-sub{font-size:12px;color:var(--txt2);margin-bottom:16px}

/* ── SNAPSHOT ── */
.snap-stat{display:inline-flex;align-items:center;gap:5px;font-size:12px;padding:4px 10px;border-radius:20px;font-weight:500}
.snap-ok{background:#E1F5EE;color:#085041}
.snap-low{background:#FEF3E2;color:#633806}
.snap-crit{background:#FCEAE6;color:#A32D2D}
.snap-zero{background:#F1EFE8;color:#5F5E5A}

/* ── DELIVERY NOTES GRID ── */
.dn-card{background:#fff;border:1px solid var(--border);border-radius:12px;padding:10px;cursor:pointer;transition:box-shadow .15s}
.dn-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.1)}
.dn-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin-top:4px}

/* ── REPORT SEGMENTS ── */
.rpt-seg{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.rseg{background:#fff;border:1px solid var(--border2);border-radius:8px;padding:6px 12px;font-size:12.5px;cursor:pointer;color:var(--txt2);display:inline-flex;align-items:center;gap:5px;transition:all .15s}
.rseg.active{background:var(--green);color:#fff;border-color:var(--green)}

/* ── LOGIN SCREEN ── */
#login-screen{position:fixed;inset:0;background:linear-gradient(135deg,#0a4a38,#1D9E75);display:flex;align-items:center;justify-content:center;z-index:9000;padding:20px}
.login-box{background:#fff;border-radius:16px;padding:32px;width:100%;max-width:360px;box-shadow:0 8px 40px rgba(0,0,0,.3)}
.login-box h2{font-size:18px;font-weight:700;color:var(--green);margin-bottom:4px}
.login-box p{font-size:12.5px;color:var(--txt2);margin-bottom:20px}
.login-box .fld{margin-bottom:12px}
#login-err{color:#A32D2D;font-size:12px;margin-top:8px;min-height:18px}

/* ── RESPONSIVE ── */
@media(max-width:600px){
  .hdr{padding:8px 12px}.hdr-left h1{font-size:13px}
  .page{padding:10px}.g4,.g3{grid-template-columns:1fr 1fr}
  .kval{font-size:22px}
}
</style>
</head>
<body>

<!-- ════════ LOGIN MODAL (storekeeper) ════════ -->
<div id="login-screen" class="hidden">
  <div class="login-box">
    <div style="text-align:center;margin-bottom:16px">
      <div style="width:52px;height:52px;background:var(--green-light);border-radius:12px;display:inline-flex;align-items:center;justify-content:center;font-size:24px;color:var(--green)"><i class="ti ti-lock"></i></div>
    </div>
    <h2>Storekeeper Login</h2>
    <p>Enter your credentials to make changes to the inventory.</p>
    <div class="fld"><label>Username</label><input type="text" id="li-user" placeholder="storekeeper" autocomplete="username"></div>
    <div class="fld"><label>Password</label><input type="password" id="li-pass" placeholder="••••••••" autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()"></div>
    <div id="login-err"></div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn-p" style="flex:1" onclick="doLogin()"><i class="ti ti-login"></i> Login</button>
      <button class="btn-s" onclick="closeLogin()">Cancel</button>
    </div>
  </div>
</div>

<!-- ════════ MAIN APP ════════ -->
<div id="main-app">

<!-- Header -->
<div class="hdr">
  <div class="hdr-left">
    <img src="/static/logo.jpg" alt="Derna FM" onerror="this.style.display='none'">
    <div>
      <h1>Inventory Management System</h1>
      <p id="hdate">Loading…</p>
    </div>
  </div>
  <div class="hdr-right">
    <span id="role-badge" class="role-badge role-view"><i class="ti ti-eye"></i> View Only</span>
    <button class="hbtn" id="auth-btn" onclick="onAuthBtn()"><i class="ti ti-lock"></i> Storekeeper Login</button>
    <button class="hbtn" onclick="openSnapshot()"><i class="ti ti-calendar-stats"></i> Stock Snapshot</button>
  </div>
</div>

<!-- Nav -->
<div class="nav">
  <button class="navbtn active" onclick="go('dashboard')"><i class="ti ti-layout-dashboard"></i> Dashboard</button>
  <button class="navbtn sk-only" onclick="go('entry')"><i class="ti ti-plus"></i> New Entry</button>
  <button class="navbtn" onclick="go('history')"><i class="ti ti-history"></i> History</button>
  <button class="navbtn sk-only" onclick="go('items')"><i class="ti ti-list"></i> Manage Items</button>
  <button class="navbtn" onclick="go('reports')"><i class="ti ti-chart-bar"></i> Reports</button>
  <button class="navbtn" onclick="go('notes')"><i class="ti ti-file-text"></i> Delivery Notes</button>
</div>

<div class="page">

<!-- ═══ DASHBOARD ═══ -->
<div id="tab-dashboard">
  <div class="g4">
    <div class="kpi kpi-green"><div class="klbl">Total Items</div><div class="kval" id="s-tot">—</div><div class="ksub">all categories</div></div>
    <div class="kpi kpi-blue"><div class="klbl">IN Today</div><div class="kval" id="s-in">—</div><div class="ksub">units received</div></div>
    <div class="kpi kpi-coral"><div class="klbl">OUT Today</div><div class="kval" id="s-out">—</div><div class="ksub">units issued</div></div>
    <div class="kpi kpi-amber"><div class="klbl">Alerts</div><div class="kval" id="s-alert">—</div><div class="ksub">below minimum</div></div>
  </div>
  <div class="g3" id="cat-cards"></div>
  <div class="alert-bar" id="alert-bar"></div>
  <div class="card">
    <div class="ch3">
      <span><i class="ti ti-table"></i> Live stock overview</span>
      <div style="display:flex;gap:6px">
        <select id="df-cat" onchange="renderDash()" style="font-size:12px;height:30px;border:1px solid var(--border2);border-radius:8px;padding:0 8px">
          <option value="all">All categories</option><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option>
        </select>
        <select id="df-st" onchange="renderDash()" style="font-size:12px;height:30px;border:1px solid var(--border2);border-radius:8px;padding:0 8px">
          <option value="all">All status</option><option value="alert">Alerts only</option><option value="ok">OK only</option>
        </select>
      </div>
    </div>
    <div class="toolbar"><input type="text" id="df-s" placeholder="Search items…" oninput="renderDash()"></div>
    <div class="wrap"><table>
      <thead><tr><th>Item</th><th>Category</th><th>Unit</th><th>Opening</th><th>Total IN</th><th>Total OUT</th><th>Balance</th><th>Safety</th><th>Status</th></tr></thead>
      <tbody id="dtb"></tbody>
    </table></div>
    <div class="pi" id="d-pi" style="margin-top:8px"></div>
  </div>
</div>

<!-- ═══ NEW ENTRY (SK only) ═══ -->
<div id="tab-entry" class="hidden">
  <div class="card">
    <div class="ch3"><span><i class="ti ti-edit"></i> Record material movement</span></div>
    <div class="form-row">
      <div class="fld"><label>Type *</label><select id="et" onchange="toggleBldRow()"><option value="IN">IN — Received / Restocked</option><option value="OUT">OUT — Consumed / Issued</option></select></div>
      <div class="fld"><label>Date *</label><input type="date" id="ed"></div>
      <div class="fld"><label>Category *</label><select id="ec" onchange="popSel()"><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option></select></div>
    </div>
    <div class="form-row">
      <div class="fld" style="grid-column:1/span 2"><label>Item *</label><select id="ei" onchange="ePrev()"></select></div>
      <div class="fld"><label>Quantity *</label><input type="number" id="eq" min="0.01" step="0.01" placeholder="Qty" oninput="ePrev()"></div>
    </div>
    <div id="eprev" style="font-size:13px;color:var(--txt2);margin-bottom:8px"></div>
    <div class="form-row">
      <div class="fld"><label>Reference / PO No.</label><input type="text" id="eref" placeholder="Optional"></div>
      <div class="fld"><label>Received / Issued By</label><input type="text" id="eperson" placeholder="Name"></div>
    </div>
    <div class="form-row" id="building-row" style="display:none">
      <div class="fld" style="grid-column:1/-1"><label>Issued To — Building *</label>
        <select id="ebld">
          <option value="">— Select building —</option>
          <option>Operation Building</option><option>Bab Jadid</option><option>Bait Banaja</option>
          <option>Baladiya Building</option><option>Bait Naseef</option><option>Bait Matbooli</option>
          <option>Bait Nazlawy</option><option>MOC1</option><option>Vibration Building</option>
          <option>Al Mustafeddin</option><option>Nagi Building 3rd Floor</option>
          <option>Nagi Building 4th Floor</option><option>Nagi Building 5th Floor</option>
          <option>Nagi Building 6th Floor</option><option>Athar Building</option><option>Majlis Al Balad</option>
        </select>
      </div>
    </div>
    <div class="fld" style="margin-bottom:10px"><label>Remarks</label><textarea id="erm" placeholder="Notes…"></textarea></div>
    <!-- Delivery Note upload — IN only -->
    <div id="dn-upload-row" style="margin-bottom:14px">
      <label style="font-size:12px;font-weight:500;color:var(--txt2);display:block;margin-bottom:6px"><i class="ti ti-paperclip"></i> Delivery Note / GRN (IN entries only)</label>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <label class="btn-s" style="cursor:pointer"><i class="ti ti-upload"></i> Attach File<input type="file" id="dn-file-input" accept="image/*,.pdf" style="display:none" onchange="onDNFileChange(event)"></label>
        <span id="dn-file-name" style="font-size:12px;color:var(--txt2)">No file attached</span>
        <button class="btn-s" type="button" id="dn-clear-btn" onclick="clearDeliveryNote()" style="display:none;color:#A32D2D;border-color:#A32D2D"><i class="ti ti-x"></i> Remove</button>
      </div>
      <div id="dn-preview" style="margin-top:8px;display:none">
        <img id="dn-preview-img" style="max-height:120px;max-width:100%;border-radius:8px;border:1px solid var(--border);object-fit:contain" alt="Preview">
        <div id="dn-pdf-label" style="display:none;font-size:12px;padding:6px 10px;background:#FFF3E0;border-radius:6px;color:#7A4A00"><i class="ti ti-file-type-pdf"></i> PDF attached — will be saved with this transaction.</div>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn-p" onclick="saveEntry()"><i class="ti ti-check"></i> Save Entry</button>
      <button class="btn-s" onclick="clearEntry()">Clear</button>
    </div>
    <div id="emsg" style="margin-top:8px"></div>
  </div>
</div>

<!-- ═══ HISTORY ═══ -->
<div id="tab-history" class="hidden">
  <div class="card">
    <div class="ch3"><span><i class="ti ti-history"></i> Transaction History</span><span id="hcnt" class="pi"></span></div>
    <div class="toolbar">
      <input type="text" id="hs" placeholder="Search…" oninput="renderHistory()">
      <select id="hcat" onchange="renderHistory()"><option value="all">All categories</option><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option></select>
      <select id="htp" onchange="renderHistory()"><option value="all">IN + OUT</option><option value="IN">IN only</option><option value="OUT">OUT only</option></select>
      <input type="date" id="hdt" onchange="renderHistory()">
      <button class="btn-s" onclick="document.getElementById('hdt').value='';renderHistory()">Clear date</button>
    </div>
    <div class="wrap"><table>
      <thead><tr><th>Date</th><th>Type</th><th>Category</th><th>Item</th><th>Qty</th><th>Unit</th><th>Building</th><th>Ref</th><th>By</th><th>Remarks</th><th>D.Note</th><th id="del-col" class="hidden"></th></tr></thead>
      <tbody id="htb"></tbody>
    </table></div>
  </div>
</div>

<!-- ═══ MANAGE ITEMS (SK only) ═══ -->
<div id="tab-items" class="hidden">
  <div class="card">
    <div class="ch3"><span><i class="ti ti-plus"></i> Add New Item</span></div>
    <div class="form-row">
      <div class="fld"><label>Category *</label><select id="nc"><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option></select></div>
      <div class="fld"><label>Item Name *</label><input type="text" id="nn" placeholder="Item name"></div>
      <div class="fld"><label>Unit *</label><input type="text" id="nu" placeholder="pcs / box…"></div>
      <div class="fld"><label>Opening Stock</label><input type="number" id="no" placeholder="0" min="0" step="0.01"></div>
      <div class="fld"><label>Safety Limit</label><input type="number" id="ns" placeholder="0" min="0" step="0.01"></div>
    </div>
    <div class="btn-row"><button class="btn-r" onclick="addItem()"><i class="ti ti-plus"></i> Add Item</button></div>
    <div id="nim" style="margin-top:6px"></div>
  </div>
  <div class="card">
    <div class="ch3"><span><i class="ti ti-list"></i> All Items</span><span id="icnt" class="pi"></span></div>
    <div class="toolbar">
      <input type="text" id="its" placeholder="Search…" oninput="renderItems()">
      <select id="itc" onchange="renderItems()"><option value="all">All categories</option><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option></select>
    </div>
    <div class="wrap"><table>
      <thead><tr><th>Name</th><th>Category</th><th>Unit</th><th>Opening</th><th>Safety</th><th>Balance</th><th></th></tr></thead>
      <tbody id="ittb"></tbody>
    </table></div>
  </div>
</div>

<!-- ═══ REPORTS ═══ -->
<div id="tab-reports" class="hidden">
  <div class="card" style="margin-bottom:14px">
    <div class="ch3"><span><i class="ti ti-adjustments-horizontal"></i> Report Options</span></div>
    <div style="margin-bottom:10px">
      <div style="font-size:11px;color:var(--txt2);font-weight:600;margin-bottom:5px">REPORT TYPE</div>
      <div class="rpt-seg">
        <button class="rseg active" id="rtype-dispatch" onclick="setRtype('dispatch')"><i class="ti ti-building"></i> Daily Dispatch</button>
        <button class="rseg" id="rtype-analytics" onclick="setRtype('analytics')"><i class="ti ti-chart-bar"></i> Analytics</button>
      </div>
    </div>
    <div style="margin-bottom:10px">
      <div style="font-size:11px;color:var(--txt2);font-weight:600;margin-bottom:5px">PERIOD</div>
      <div class="rpt-seg">
        <button class="rseg active" id="rseg-daily" onclick="setRpt('daily')">Single Day</button>
        <button class="rseg" id="rseg-range" onclick="setRpt('range')">Date Range</button>
        <button class="rseg" id="rseg-weekly" onclick="setRpt('weekly')">This Week</button>
        <button class="rseg" id="rseg-monthly" onclick="setRpt('monthly')">This Month</button>
      </div>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;align-items:flex-end">
      <div class="fld" style="margin:0"><label id="rdt-label">Date</label><input type="date" id="rdt"></div>
      <div class="fld" id="rdt2-wrap" style="margin:0;display:none"><label>End Date</label><input type="date" id="rdt2"></div>
      <div class="fld" style="margin:0"><label>Category</label>
        <select id="rcat" onchange="rptCat=this.value">
          <option value="all">All Categories</option><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option>
        </select>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn-r" onclick="genReport()"><i class="ti ti-refresh"></i> Generate</button>
      <button class="btn-p" onclick="printReport()" style="background:#444"><i class="ti ti-printer"></i> Print</button>
    </div>
  </div>
  <div id="rpt-out"></div>
</div>

<!-- ═══ DELIVERY NOTES ═══ -->
<div id="tab-notes" class="hidden">
  <div class="card">
    <div class="ch3"><span><i class="ti ti-file-text"></i> Delivery Notes Archive</span><span id="dn-cnt" class="pi"></span></div>
    <div class="toolbar">
      <input type="text" id="dn-s" placeholder="Search by item / ref / person…" oninput="renderNotes()">
      <input type="date" id="dn-dt" onchange="renderNotes()">
      <button class="btn-s" onclick="document.getElementById('dn-dt').value='';renderNotes()">Clear date</button>
    </div>
    <div id="dn-grid" class="dn-grid"></div>
    <div id="dn-empty" class="hidden" style="text-align:center;padding:3rem;color:var(--txt3)"><i class="ti ti-file-off" style="font-size:2rem"></i><br><br>No delivery notes found.</div>
  </div>
</div>

</div><!-- end .page -->
</div><!-- end #main-app -->

<!-- ═══ STOCK SNAPSHOT MODAL ═══ -->
<div id="snapshot-modal" class="modal-overlay hidden" onclick="if(event.target===this)closeSnapshot()">
  <div class="modal-box wide">
    <button class="modal-close" onclick="closeSnapshot()">&times;</button>
    <div class="modal-title"><i class="ti ti-calendar-stats"></i> Stock Snapshot</div>
    <div class="modal-sub">View available stock balance as of any date — perfect for end-of-month checks.</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:14px">
      <div class="fld" style="margin:0"><label style="font-size:12px">Snapshot Date</label><input type="date" id="snap-date" style="height:34px"></div>
      <div class="fld" style="margin:0"><label style="font-size:12px">Category</label>
        <select id="snap-cat" style="height:34px;min-width:140px">
          <option value="all">All Categories</option><option value="Hospitality">Hospitality</option><option value="Cleaning">Cleaning</option><option value="Maintenance">Maintenance</option>
        </select>
      </div>
      <div class="fld" style="margin:0"><label style="font-size:12px">Status</label>
        <select id="snap-st" style="height:34px;min-width:130px">
          <option value="all">All Items</option><option value="alert">Alerts Only</option><option value="ok">OK Only</option>
        </select>
      </div>
      <button class="btn-r" onclick="genSnapshot()"><i class="ti ti-search"></i> Generate</button>
      <button class="btn-p" onclick="exportSnapshotCSV()" style="background:#1D7A45"><i class="ti ti-download"></i> Export CSV</button>
    </div>
    <div id="snap-summary" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px"></div>
    <div id="snap-out"></div>
  </div>
</div>

<!-- ═══ DELIVERY NOTE VIEWER MODAL ═══ -->
<div id="dn-modal" class="modal-overlay hidden" onclick="if(event.target===this)closeDNModal()">
  <div class="modal-box wide">
    <button class="modal-close" onclick="closeDNModal()">&times;</button>
    <div class="modal-title" id="dn-modal-title"><i class="ti ti-file-text"></i> Delivery Note</div>
    <div class="modal-sub" id="dn-modal-sub"></div>
    <div id="dn-modal-body" style="text-align:center;margin-top:12px"></div>
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <button class="btn-p" onclick="downloadDN()" style="background:#1D7A45"><i class="ti ti-download"></i> Download</button>
      <button class="btn-s" onclick="closeDNModal()">Close</button>
    </div>
  </div>
</div>

<!-- Chart.js -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════
let items = [], txns = [], role = 'viewer';
let rptMode = 'daily', rptType = 'dispatch', rptCat = 'all';
let _snapData = [], _viewingDN = null, _dnDataUri = null, _dnFileName = '';
let chartInst = null;

const CAT_B = {Hospitality:'bh', Cleaning:'bc', Maintenance:'bm'};
const BUILDINGS = ['Operation Building','Bab Jadid','Bait Banaja','Baladiya Building','Bait Naseef','Bait Matbooli','Bait Nazlawy','MOC1','Vibration Building','Al Mustafeddin','Nagi Building 3rd Floor','Nagi Building 4th Floor','Nagi Building 5th Floor','Nagi Building 6th Floor','Athar Building','Majlis Al Balad'];

function tod(){ return new Date().toISOString().slice(0,10); }
function fmt(n){ return Math.round((n||0)*100)/100; }
function uid(){ return 'x'+Date.now()+Math.random().toString(36).slice(2,5); }

function getB(id){
  const it = items.find(x=>x.id===id); if(!it) return 0;
  return txns.reduce((b,t)=>t.itemId===id?(t.type==='IN'?b+t.qty:b-t.qty):b, it.opening||0);
}
function stat(bal,safety){
  if(bal<=0) return{l:'Out of stock',c:'bzero'};
  if(!safety||safety===0) return{l:'OK',c:'bok'};
  if(bal<safety*0.5) return{l:'Critical',c:'bcrit'};
  if(bal<safety*0.75) return{l:'Low',c:'blow'};
  return{l:'OK',c:'bok'};
}

// ═══════════════════════════════════════════════════════════════
// API CALLS
// ═══════════════════════════════════════════════════════════════
async function apiFetch(url, opts={}){
  const r = await fetch(url, {headers:{'Content-Type':'application/json'}, credentials:'same-origin', ...opts});
  if(!r.ok){ const e=await r.json().catch(()=>({})); throw new Error(e.error||r.statusText); }
  return r.json();
}

async function loadData(){
  [items, txns] = await Promise.all([
    apiFetch('/api/items'),
    apiFetch('/api/transactions'),
  ]);
}

async function checkRole(){
  const me = await apiFetch('/api/me');
  role = me.role;
  applyRole();
}

function applyRole(){
  const isSK = role === 'storekeeper';
  document.body.classList.toggle('sk', isSK);
  document.getElementById('role-badge').className = 'role-badge ' + (isSK ? 'role-sk' : 'role-view');
  document.getElementById('role-badge').innerHTML = isSK
    ? '<i class="ti ti-shield-check"></i> Storekeeper'
    : '<i class="ti ti-eye"></i> View Only';
  document.getElementById('auth-btn').innerHTML = isSK
    ? '<i class="ti ti-logout"></i> Logout'
    : '<i class="ti ti-lock"></i> Storekeeper Login';
  document.getElementById('del-col').classList.toggle('hidden', !isSK);
  // hide entry/items tabs for viewers
  if(!isSK && currentTab === 'entry') go('dashboard');
  if(!isSK && currentTab === 'items') go('dashboard');
}

// ═══════════════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════════════
function onAuthBtn(){
  if(role === 'storekeeper') doLogout();
  else openLogin();
}
function openLogin(){ document.getElementById('login-screen').classList.remove('hidden'); document.getElementById('li-user').focus(); }
function closeLogin(){ document.getElementById('login-screen').classList.add('hidden'); document.getElementById('login-err').textContent=''; }
async function doLogin(){
  const user = document.getElementById('li-user').value.trim();
  const pass = document.getElementById('li-pass').value;
  document.getElementById('login-err').textContent = '';
  try{
    await apiFetch('/api/login',{method:'POST',body:JSON.stringify({username:user,password:pass})});
    role = 'storekeeper';
    applyRole();
    closeLogin();
    document.getElementById('li-pass').value='';
  } catch(e){
    document.getElementById('login-err').textContent = 'Invalid username or password.';
  }
}
async function doLogout(){
  await apiFetch('/api/logout',{method:'POST'});
  role = 'viewer';
  applyRole();
}

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════
let currentTab = 'dashboard';
const TABS = ['dashboard','entry','history','items','reports','notes'];

function go(name){
  if((name==='entry'||name==='items') && role!=='storekeeper'){
    openLogin(); return;
  }
  currentTab = name;
  TABS.forEach(t=>document.getElementById('tab-'+t).classList.toggle('hidden',t!==name));
  document.querySelectorAll('.navbtn').forEach(b=>{
    const t=b.getAttribute('onclick').match(/'(\w+)'/)[1];
    b.classList.toggle('active',t===name);
  });
  if(name==='dashboard'){rStats();rCats();rAlerts();renderDash();}
  if(name==='entry'){popSel();ePrev();toggleBldRow();}
  if(name==='history') renderHistory();
  if(name==='items') renderItems();
  if(name==='reports'){document.getElementById('rdt').value=tod();genReport();}
  if(name==='notes') renderNotes();
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════
function rStats(){
  const td=tod(); let inT=0,outT=0,al=0;
  txns.forEach(t=>{if(t.date===td){if(t.type==='IN')inT+=t.qty;else outT+=t.qty;}});
  items.forEach(it=>{const s=stat(getB(it.id),it.safety);if(s.c!=='bok')al++;});
  document.getElementById('s-tot').textContent=items.length;
  document.getElementById('s-in').textContent=fmt(inT);
  document.getElementById('s-out').textContent=fmt(outT);
  document.getElementById('s-alert').textContent=al;
}
function rCats(){
  const cats=['Hospitality','Cleaning','Maintenance'];
  const cols={Hospitality:'#1D9E75',Cleaning:'#378ADD',Maintenance:'#D85A30'};
  document.getElementById('cat-cards').innerHTML=cats.map(c=>{
    const its=items.filter(x=>x.cat===c);
    const al=its.filter(x=>stat(getB(x.id),x.safety).c!=='bok').length;
    return`<div class="kpi" style="border-color:${cols[c]}22;background:${cols[c]}0d">
      <div class="klbl" style="color:${cols[c]}">${c}</div>
      <div class="kval">${its.length} <span style="font-size:13px;color:var(--txt2)">items</span></div>
      <div class="ksub">${al>0?`<span style="color:#A32D2D">${al} alert${al>1?'s':''}</span>`:'All OK'}</div>
    </div>`;
  }).join('');
}
function rAlerts(){
  const low=items.filter(it=>stat(getB(it.id),it.safety).c!=='bok');
  const bar=document.getElementById('alert-bar');
  if(!low.length){bar.style.display='none';return;}
  bar.style.display='';
  bar.innerHTML=`<strong><i class="ti ti-alert-triangle"></i> ${low.length} item(s) need attention:</strong> `
    +low.slice(0,8).map(it=>`<span class="badge ${stat(getB(it.id),it.safety).c}" style="margin:2px">${it.name}</span>`).join(' ')
    +(low.length>8?` + ${low.length-8} more`:'');
}
function renderDash(){
  const s=document.getElementById('df-s').value.toLowerCase();
  const cat=document.getElementById('df-cat').value;
  const st=document.getElementById('df-st').value;
  const inM={},outM={};
  txns.forEach(t=>{if(t.type==='IN')inM[t.itemId]=(inM[t.itemId]||0)+t.qty;else outM[t.itemId]=(outM[t.itemId]||0)+t.qty;});
  const f=items.filter(it=>{
    if(cat!=='all'&&it.cat!==cat) return false;
    if(s&&!it.name.toLowerCase().includes(s)) return false;
    const sv=stat(getB(it.id),it.safety);
    if(st==='alert'&&sv.c==='bok') return false;
    if(st==='ok'&&sv.c!=='bok') return false;
    return true;
  });
  document.getElementById('d-pi').textContent=`Showing ${f.length} of ${items.length} items`;
  const tbody=document.getElementById('dtb');
  if(!f.length){tbody.innerHTML=`<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--txt3)">No items match your filters</td></tr>`;return;}
  tbody.innerHTML=f.map(it=>{
    const b=getB(it.id);const sv=stat(b,it.safety);
    return`<tr>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${it.name}">${it.name}</td>
      <td><span class="badge ${CAT_B[it.cat]}">${it.cat}</span></td>
      <td style="color:var(--txt2)">${it.unit}</td>
      <td>${it.opening||0}</td>
      <td style="color:#0F6E56;font-weight:500">${fmt(inM[it.id]||0)}</td>
      <td style="color:#993C1D;font-weight:500">${fmt(outM[it.id]||0)}</td>
      <td style="font-weight:500;color:${b<=0?'#A32D2D':b<(it.safety*0.75||0)?'#854F0B':'#0F6E56'}">${fmt(b)}</td>
      <td style="color:var(--txt2)">${it.safety||'—'}</td>
      <td><span class="badge ${sv.c}">${sv.l}</span></td>
    </tr>`;
  }).join('');
}

// ═══════════════════════════════════════════════════════════════
// NEW ENTRY
// ═══════════════════════════════════════════════════════════════
function popSel(){
  const cat=document.getElementById('ec').value;
  const sel=document.getElementById('ei');
  sel.innerHTML=items.filter(i=>i.cat===cat).map(i=>`<option value="${i.id}">${i.name} (${i.unit})</option>`).join('');
  ePrev();
}
function ePrev(){
  const id=document.getElementById('ei').value;
  const qty=parseFloat(document.getElementById('eq').value)||0;
  const type=document.getElementById('et').value;
  const it=items.find(x=>x.id===id); const box=document.getElementById('eprev');
  if(!it){box.textContent='';return;}
  const b=getB(id); const after=type==='IN'?b+qty:b-qty;
  box.innerHTML=`Current balance: <strong>${fmt(b)} ${it.unit}</strong>${qty>0?` → after: <strong style="color:${after<0?'#A32D2D':'#0F6E56'}">${fmt(after)} ${it.unit}</strong>`:''}`;
}
function toggleBldRow(){
  const isOut=document.getElementById('et').value==='OUT';
  document.getElementById('building-row').style.display=isOut?'':'none';
  document.getElementById('dn-upload-row').style.display=isOut?'none':'';
  if(!isOut) document.getElementById('ebld').value='';
}

async function saveEntry(){
  const type=document.getElementById('et').value;
  const date=document.getElementById('ed').value;
  const itemId=document.getElementById('ei').value;
  const qty=parseFloat(document.getElementById('eq').value);
  const ref=document.getElementById('eref').value.trim();
  const person=document.getElementById('eperson').value.trim();
  const building=document.getElementById('ebld').value.trim();
  const remarks=document.getElementById('erm').value.trim();
  const msg=document.getElementById('emsg');
  if(!date||!itemId||!qty||qty<=0){msg.className='merr';msg.textContent='Fill in date, item and a valid quantity.';return;}
  if(type==='OUT'&&!building){msg.className='merr';msg.textContent='Please select the destination building for OUT entries.';return;}
  const payload={type,date,itemId,qty,ref,person,building,remarks};
  if(type==='IN'&&_dnDataUri) payload.deliveryNote={dataUri:_dnDataUri,name:_dnFileName};
  try{
    const txn = await apiFetch('/api/transactions',{method:'POST',body:JSON.stringify(payload)});
    txns.unshift(txn);
    const it=items.find(x=>x.id===itemId);
    msg.className='mok';msg.textContent=`✓ Saved! ${type} of ${qty} ${it?it.unit:''} for "${it?it.name:'item'}".${payload.deliveryNote?' Delivery note attached.':''}`;
    document.getElementById('eq').value='';document.getElementById('eref').value='';document.getElementById('erm').value='';document.getElementById('ebld').value='';
    clearDeliveryNote();ePrev();
    setTimeout(()=>msg.textContent='',5000);
  } catch(e){msg.className='merr';msg.textContent='Error: '+e.message;}
}

function clearEntry(){['eq','eref','eperson','erm'].forEach(id=>document.getElementById(id).value='');document.getElementById('ebld').value='';document.getElementById('emsg').textContent='';clearDeliveryNote();ePrev();toggleBldRow();}

// Delivery Note file pick (web — uses file input)
function onDNFileChange(evt){
  const file=evt.target.files[0]; if(!file) return;
  const reader=new FileReader();
  reader.onload=e=>{
    _dnDataUri=e.target.result; _dnFileName=file.name;
    document.getElementById('dn-file-name').textContent=file.name;
    document.getElementById('dn-clear-btn').style.display='';
    const prev=document.getElementById('dn-preview');
    const img=document.getElementById('dn-preview-img');
    const pdf=document.getElementById('dn-pdf-label');
    prev.style.display='';
    if(file.type==='application/pdf'){img.style.display='none';pdf.style.display='';}
    else{img.src=e.target.result;img.style.display='';pdf.style.display='none';}
  };
  reader.readAsDataURL(file);
}
function clearDeliveryNote(){
  _dnDataUri=null;_dnFileName='';
  document.getElementById('dn-file-name').textContent='No file attached';
  document.getElementById('dn-clear-btn').style.display='none';
  document.getElementById('dn-preview').style.display='none';
  document.getElementById('dn-preview-img').src='';
  document.getElementById('dn-file-input').value='';
}

// ═══════════════════════════════════════════════════════════════
// HISTORY
// ═══════════════════════════════════════════════════════════════
function renderHistory(){
  const s=document.getElementById('hs').value.toLowerCase();
  const cat=document.getElementById('hcat').value;
  const tp=document.getElementById('htp').value;
  const dt=document.getElementById('hdt').value;
  const list=[...txns].filter(t=>{
    if(tp!=='all'&&t.type!==tp) return false;
    if(dt&&t.date!==dt) return false;
    const it=items.find(x=>x.id===t.itemId);
    if(cat!=='all'&&(!it||it.cat!==cat)) return false;
    if(s){const n=it?it.name.toLowerCase():'';if(!n.includes(s)&&!(t.ref||'').toLowerCase().includes(s)&&!(t.person||'').toLowerCase().includes(s)&&!(t.building||'').toLowerCase().includes(s))return false;}
    return true;
  });
  document.getElementById('hcnt').textContent=`${list.length} transaction(s)`;
  const tbody=document.getElementById('htb');
  if(!list.length){tbody.innerHTML=`<tr><td colspan="12" style="text-align:center;padding:2rem;color:var(--txt3)">No transactions found</td></tr>`;return;}
  tbody.innerHTML=list.map(t=>{
    const it=items.find(x=>x.id===t.itemId);
    const dnBtn=t.deliveryNote
      ?`<button class="btn-s" onclick="openDNModal('${t.id}')" style="padding:2px 8px;font-size:11px;color:#0C447C;border-color:#0C447C"><i class="ti ti-file-text"></i> View</button>`
      :`<span style="color:var(--txt3);font-size:11px">—</span>`;
    const delBtn=role==='storekeeper'
      ?`<button class="ico-del" onclick="delTxn('${t.id}')"><i class="ti ti-trash"></i></button>`:'';
    return`<tr>
      <td style="white-space:nowrap">${t.date}</td>
      <td><span class="badge ${t.type==='IN'?'bin':'bout'}">${t.type}</span></td>
      <td><span class="badge ${it?CAT_B[it.cat]:'bzero'}">${it?it.cat:'—'}</span></td>
      <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${it?it.name:'Unknown'}</td>
      <td style="font-weight:500">${t.qty}</td>
      <td style="color:var(--txt2)">${it?it.unit:'—'}</td>
      <td style="font-size:12px">${t.building&&t.type==='OUT'?`<span style="font-size:11px;background:#E6F1FB;color:#0C447C;border-radius:12px;padding:2px 8px">${t.building}</span>`:'—'}</td>
      <td style="font-size:12px;color:var(--txt2)">${t.ref||'—'}</td>
      <td style="font-size:12px;color:var(--txt2)">${t.person||'—'}</td>
      <td style="font-size:12px;color:var(--txt2);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.remarks||'—'}</td>
      <td>${dnBtn}</td>
      <td>${delBtn}</td>
    </tr>`;
  }).join('');
}

async function delTxn(id){
  if(!confirm('Delete this transaction? This cannot be undone.')) return;
  try{
    await apiFetch('/api/transactions/'+id,{method:'DELETE'});
    txns=txns.filter(t=>t.id!==id);
    renderHistory();
  } catch(e){ alert('Error: '+e.message); }
}

// ═══════════════════════════════════════════════════════════════
// MANAGE ITEMS
// ═══════════════════════════════════════════════════════════════
function renderItems(){
  const s=document.getElementById('its').value.toLowerCase();
  const cat=document.getElementById('itc').value;
  const f=items.filter(it=>(cat==='all'||it.cat===cat)&&(!s||it.name.toLowerCase().includes(s)));
  document.getElementById('icnt').textContent=`${f.length} of ${items.length}`;
  const tbody=document.getElementById('ittb');
  if(!f.length){tbody.innerHTML=`<tr><td colspan="7" style="text-align:center;padding:2rem;color:var(--txt3)">No items</td></tr>`;return;}
  tbody.innerHTML=f.map(it=>{const b=getB(it.id);return`<tr>
    <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${it.name}</td>
    <td><span class="badge ${CAT_B[it.cat]}">${it.cat}</span></td>
    <td>${it.unit}</td><td>${it.opening||0}</td><td>${it.safety||'—'}</td>
    <td style="font-weight:500;color:${b<=0?'#A32D2D':'#0F6E56'}">${fmt(b)}</td>
    <td><button class="ico-del" onclick="delItem('${it.id}')"><i class="ti ti-trash"></i></button></td>
  </tr>`;}).join('');
}

async function addItem(){
  const cat=document.getElementById('nc').value;
  const name=document.getElementById('nn').value.trim();
  const unit=document.getElementById('nu').value.trim();
  const opening=parseFloat(document.getElementById('no').value)||0;
  const safety=parseFloat(document.getElementById('ns').value)||0;
  const msg=document.getElementById('nim');
  if(!name||!unit){msg.className='merr';msg.textContent='Name and unit are required.';return;}
  try{
    const item=await apiFetch('/api/items',{method:'POST',body:JSON.stringify({cat,name,unit,opening,safety})});
    items.push(item);
    ['nn','nu','no','ns'].forEach(id=>document.getElementById(id).value='');
    msg.className='mok';msg.textContent=`✓ "${name}" added to ${cat}.`;
    renderItems(); setTimeout(()=>msg.textContent='',4000);
  } catch(e){msg.className='merr';msg.textContent='Error: '+e.message;}
}

async function delItem(id){
  const it=items.find(x=>x.id===id);
  if(!confirm(`Remove "${it?it.name:'this item'}"? All its transactions will also be deleted.`)) return;
  try{
    await apiFetch('/api/items/'+id,{method:'DELETE'});
    items=items.filter(x=>x.id!==id);
    txns=txns.filter(t=>t.itemId!==id);
    renderItems();
  } catch(e){ alert('Error: '+e.message); }
}

// ═══════════════════════════════════════════════════════════════
// REPORTS
// ═══════════════════════════════════════════════════════════════
function setRtype(t){
  rptType=t;
  ['dispatch','analytics'].forEach(k=>document.getElementById('rtype-'+k).classList.toggle('active',k===t));
}
function setRpt(m){
  rptMode=m;
  ['daily','range','weekly','monthly'].forEach(k=>document.getElementById('rseg-'+k).classList.toggle('active',k===m));
  document.getElementById('rdt2-wrap').style.display=m==='range'?'':'none';
}
function getDateRange(){
  const d=document.getElementById('rdt').value||tod();
  if(rptMode==='daily') return{from:d,to:d};
  if(rptMode==='range') return{from:d,to:document.getElementById('rdt2').value||d};
  if(rptMode==='weekly'){const dt=new Date(d);const day=dt.getDay();const mon=new Date(dt);mon.setDate(dt.getDate()-day+1);const sun=new Date(mon);sun.setDate(mon.getDate()+6);return{from:mon.toISOString().slice(0,10),to:sun.toISOString().slice(0,10)};}
  if(rptMode==='monthly'){const dt=new Date(d);const from=new Date(dt.getFullYear(),dt.getMonth(),1).toISOString().slice(0,10);const to=new Date(dt.getFullYear(),dt.getMonth()+1,0).toISOString().slice(0,10);return{from,to};}
  return{from:d,to:d};
}
function genReport(){
  const{from,to}=getDateRange();
  const cat=rptCat;
  const fTxns=txns.filter(t=>t.date>=from&&t.date<=to&&(cat==='all'||items.find(x=>x.id===t.itemId)?.cat===cat));
  const out=document.getElementById('rpt-out');
  if(rptType==='dispatch'){
    const byBld={};
    fTxns.filter(t=>t.type==='OUT').forEach(t=>{
      const bld=t.building||'Unknown';
      if(!byBld[bld]) byBld[bld]=[];
      byBld[bld].push(t);
    });
    if(!Object.keys(byBld).length){out.innerHTML='<div class="card" style="color:var(--txt3);text-align:center;padding:2rem">No OUT transactions in this period.</div>';return;}
    out.innerHTML=Object.entries(byBld).map(([bld,ts])=>`
      <div class="card">
        <div class="ch3"><span><i class="ti ti-building"></i> ${bld}</span><span class="pi">${ts.length} issue(s)</span></div>
        <div class="wrap"><table>
          <thead><tr><th>Date</th><th>Item</th><th>Qty</th><th>Unit</th><th>Ref</th><th>By</th></tr></thead>
          <tbody>${ts.map(t=>{const it=items.find(x=>x.id===t.itemId);return`<tr>
            <td>${t.date}</td><td>${it?it.name:'?'}</td><td><strong>${t.qty}</strong></td>
            <td style="color:var(--txt2)">${it?it.unit:'—'}</td>
            <td style="color:var(--txt2)">${t.ref||'—'}</td><td style="color:var(--txt2)">${t.person||'—'}</td>
          </tr>`;}).join('')}</tbody>
        </table></div>
      </div>`).join('');
  } else {
    // Analytics
    const inTot=fTxns.filter(t=>t.type==='IN').reduce((a,t)=>a+t.qty,0);
    const outTot=fTxns.filter(t=>t.type==='OUT').reduce((a,t)=>a+t.qty,0);
    const topOut={};
    fTxns.filter(t=>t.type==='OUT').forEach(t=>{topOut[t.itemId]=(topOut[t.itemId]||0)+t.qty;});
    const topItems=Object.entries(topOut).sort((a,b)=>b[1]-a[1]).slice(0,10);
    out.innerHTML=`
      <div class="g4" style="margin-bottom:14px">
        <div class="kpi kpi-blue"><div class="klbl">Total IN</div><div class="kval">${fmt(inTot)}</div><div class="ksub">${from===to?from:from+' → '+to}</div></div>
        <div class="kpi kpi-coral"><div class="klbl">Total OUT</div><div class="kval">${fmt(outTot)}</div><div class="ksub">units issued</div></div>
        <div class="kpi kpi-amber"><div class="klbl">Transactions</div><div class="kval">${fTxns.length}</div><div class="ksub">in this period</div></div>
      </div>
      <div class="card">
        <div class="ch3"><span><i class="ti ti-trophy"></i> Top 10 Most Issued Items</span></div>
        <div class="wrap"><table>
          <thead><tr><th>#</th><th>Item</th><th>Category</th><th>Total OUT</th><th>Unit</th></tr></thead>
          <tbody>${topItems.map(([id,qty],i)=>{const it=items.find(x=>x.id===id);return`<tr>
            <td style="color:var(--txt3)">${i+1}</td>
            <td>${it?it.name:'?'}</td>
            <td><span class="badge ${it?CAT_B[it.cat]:'bzero'}">${it?it.cat:'—'}</span></td>
            <td><strong>${fmt(qty)}</strong></td>
            <td style="color:var(--txt2)">${it?it.unit:'—'}</td>
          </tr>`;}).join('')}</tbody>
        </table></div>
      </div>`;
  }
}
function printReport(){ window.print(); }

// ═══════════════════════════════════════════════════════════════
// STOCK SNAPSHOT
// ═══════════════════════════════════════════════════════════════
function openSnapshot(){
  const now=new Date();
  const lastDay=new Date(now.getFullYear(),now.getMonth()+1,0);
  document.getElementById('snap-date').value=lastDay.toISOString().slice(0,10);
  document.getElementById('snap-cat').value='all';
  document.getElementById('snap-st').value='all';
  document.getElementById('snap-summary').innerHTML='';
  document.getElementById('snap-out').innerHTML='<div style="color:var(--txt3);font-size:13px;padding:2rem;text-align:center">Choose a date and click Generate.</div>';
  document.getElementById('snapshot-modal').classList.remove('hidden');
}
function closeSnapshot(){ document.getElementById('snapshot-modal').classList.add('hidden'); }

function getBalanceAt(itemId,dateStr){
  const it=items.find(x=>x.id===itemId); if(!it) return 0;
  return txns.filter(t=>t.itemId===itemId&&t.date<=dateStr).reduce((b,t)=>t.type==='IN'?b+t.qty:b-t.qty, it.opening||0);
}
function genSnapshot(){
  const dateStr=document.getElementById('snap-date').value;
  if(!dateStr){alert('Please select a snapshot date.');return;}
  const cat=document.getElementById('snap-cat').value;
  const stF=document.getElementById('snap-st').value;
  let filtered=items.filter(it=>cat==='all'||it.cat===cat);
  _snapData=filtered.map(it=>{const bal=getBalanceAt(it.id,dateStr);const sv=stat(bal,it.safety);return{...it,bal,sv};});
  if(stF==='alert') _snapData=_snapData.filter(x=>x.sv.c!=='bok');
  if(stF==='ok')    _snapData=_snapData.filter(x=>x.sv.c==='bok');
  const total=_snapData.length;
  const okC=_snapData.filter(x=>x.sv.c==='bok').length;
  const lowC=_snapData.filter(x=>x.sv.c==='blow').length;
  const critC=_snapData.filter(x=>x.sv.c==='bcrit').length;
  const zeroC=_snapData.filter(x=>x.sv.c==='bzero').length;
  const fmtD=new Date(dateStr+'T00:00:00').toLocaleDateString('en-SA',{year:'numeric',month:'long',day:'numeric'});
  document.getElementById('snap-summary').innerHTML=`
    <span class="snap-stat snap-ok"><i class="ti ti-circle-check"></i> OK: ${okC}</span>
    <span class="snap-stat snap-low"><i class="ti ti-alert-triangle"></i> Low: ${lowC}</span>
    <span class="snap-stat snap-crit"><i class="ti ti-alert-circle"></i> Critical: ${critC}</span>
    <span class="snap-stat snap-zero"><i class="ti ti-ban"></i> Out of stock: ${zeroC}</span>
    <span style="font-size:12px;color:var(--txt2);margin-left:4px">— as of <strong>${fmtD}</strong> (${total} items)</span>`;
  if(!_snapData.length){document.getElementById('snap-out').innerHTML='<div style="color:var(--txt3);font-size:13px;padding:2rem;text-align:center">No items match.</div>';return;}
  const tbody=_snapData.map((it,i)=>{
    const totalIn=txns.filter(t=>t.itemId===it.id&&t.date<=dateStr&&t.type==='IN').reduce((a,t)=>a+t.qty,0);
    const totalOut=txns.filter(t=>t.itemId===it.id&&t.date<=dateStr&&t.type==='OUT').reduce((a,t)=>a+t.qty,0);
    return`<tr>
      <td style="color:var(--txt3);font-size:11px">${i+1}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500">${it.name}</td>
      <td><span class="badge ${CAT_B[it.cat]}">${it.cat}</span></td>
      <td style="color:var(--txt2)">${it.unit}</td>
      <td>${it.opening||0}</td>
      <td style="color:#0F6E56;font-weight:500">${fmt(totalIn)}</td>
      <td style="color:#993C1D;font-weight:500">${fmt(totalOut)}</td>
      <td style="font-weight:600;color:${it.bal<=0?'#A32D2D':it.bal<(it.safety*0.75||0)?'#854F0B':'#0F6E56'}">${fmt(it.bal)}</td>
      <td style="color:var(--txt2)">${it.safety||'—'}</td>
      <td><span class="badge ${it.sv.c}">${it.sv.l}</span></td>
    </tr>`;
  }).join('');
  document.getElementById('snap-out').innerHTML=`<div class="wrap"><table>
    <thead><tr><th>#</th><th>Item</th><th>Category</th><th>Unit</th><th>Opening</th><th>Total IN</th><th>Total OUT</th><th>Balance</th><th>Safety</th><th>Status</th></tr></thead>
    <tbody>${tbody}</tbody>
  </table></div>`;
}
function exportSnapshotCSV(){
  const dateStr=document.getElementById('snap-date').value;
  if(!dateStr||!_snapData.length){alert('Generate a snapshot first.');return;}
  const esc=v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"';
  const hdr=['Item','Category','Unit','Opening Stock','Total IN','Total OUT','Balance as of '+dateStr,'Safety Limit','Status'];
  const rows=_snapData.map(it=>{
    const totalIn=txns.filter(t=>t.itemId===it.id&&t.date<=dateStr&&t.type==='IN').reduce((a,t)=>a+t.qty,0);
    const totalOut=txns.filter(t=>t.itemId===it.id&&t.date<=dateStr&&t.type==='OUT').reduce((a,t)=>a+t.qty,0);
    return[it.name,it.cat,it.unit,it.opening||0,fmt(totalIn),fmt(totalOut),fmt(it.bal),it.safety||0,it.sv.l].map(esc).join(',');
  });
  const csv=[hdr.map(esc).join(','),...rows].join('\r\n');
  const blob=new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`stock_snapshot_${dateStr}.csv`;a.click();
}

// ═══════════════════════════════════════════════════════════════
// DELIVERY NOTES TAB
// ═══════════════════════════════════════════════════════════════
function renderNotes(){
  const s=document.getElementById('dn-s').value.toLowerCase();
  const dt=document.getElementById('dn-dt').value;
  const list=[...txns].filter(t=>{
    if(!t.deliveryNote) return false;
    if(dt&&t.date!==dt) return false;
    if(s){const it=items.find(x=>x.id===t.itemId);const hay=[(it?it.name:''),t.ref||'',t.person||'',t.date].join(' ').toLowerCase();if(!hay.includes(s))return false;}
    return true;
  });
  const grid=document.getElementById('dn-grid');
  const empty=document.getElementById('dn-empty');
  document.getElementById('dn-cnt').textContent=`${list.length} note(s)`;
  if(!list.length){grid.innerHTML='';empty.classList.remove('hidden');return;}
  empty.classList.add('hidden');
  grid.innerHTML=list.map(t=>{
    const it=items.find(x=>x.id===t.itemId);
    const isPdf=t.deliveryNote.dataUri.includes('application/pdf');
    const thumb=isPdf
      ?`<div style="height:130px;display:flex;align-items:center;justify-content:center;background:#FFF3E0;border-radius:8px;color:#7A4A00;font-size:2.5rem"><i class="ti ti-file-type-pdf"></i></div>`
      :`<img src="${t.deliveryNote.dataUri}" style="width:100%;height:130px;object-fit:cover;border-radius:8px;border:1px solid var(--border)" alt="Delivery note">`;
    return`<div class="dn-card" onclick="openDNModal('${t.id}')">
      ${thumb}
      <div style="margin-top:8px">
        <div style="font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${it?it.name:'Unknown item'}</div>
        <div style="font-size:11px;color:var(--txt2);margin-top:2px">${t.date} &nbsp;·&nbsp; <span class="badge bin">IN</span></div>
        <div style="font-size:11px;color:var(--txt2)">${t.ref?'Ref: '+t.ref:''} ${t.person?'· '+t.person:''}</div>
        <div style="font-size:11px;color:var(--txt3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.deliveryNote.name}</div>
      </div>
    </div>`;
  }).join('');
}

function openDNModal(txnId){
  const t=txns.find(x=>x.id===txnId); if(!t||!t.deliveryNote) return;
  const it=items.find(x=>x.id===t.itemId);
  _viewingDN=t;
  document.getElementById('dn-modal-title').innerHTML=`<i class="ti ti-file-text"></i> ${t.deliveryNote.name}`;
  document.getElementById('dn-modal-sub').textContent=`${it?it.name:'Unknown'} · ${t.date}${t.ref?' · Ref: '+t.ref:''}${t.person?' · '+t.person:''}`;
  const body=document.getElementById('dn-modal-body');
  const isPdf=t.deliveryNote.dataUri.includes('application/pdf');
  if(isPdf){
    body.innerHTML=`<div style="padding:2rem;background:#FFF3E0;border-radius:8px;color:#7A4A00;font-size:14px"><i class="ti ti-file-type-pdf" style="font-size:2rem"></i><br><br>PDF delivery note.<br>Click <strong>Download</strong> to save and open it.</div>`;
  } else {
    body.innerHTML=`<img src="${t.deliveryNote.dataUri}" style="max-width:100%;max-height:460px;border-radius:8px;border:1px solid var(--border);object-fit:contain" alt="Delivery note">`;
  }
  document.getElementById('dn-modal').classList.remove('hidden');
}
function closeDNModal(){ document.getElementById('dn-modal').classList.add('hidden'); _viewingDN=null; }
function downloadDN(){
  if(!_viewingDN||!_viewingDN.deliveryNote) return;
  const dn=_viewingDN.deliveryNote;
  const a=document.createElement('a');a.href=dn.dataUri;a.download=dn.name;a.click();
}

// ═══════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════
async function init(){
  // Date in header
  document.getElementById('hdate').textContent=new Date().toLocaleDateString('en-SA',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
  // Set today's date in entry form
  document.getElementById('ed').value=tod();
  // Load role & data
  await checkRole();
  await loadData();
  // Render dashboard
  rStats(); rCats(); rAlerts(); renderDash();
}
init();
</script>
</body>
</html>

"""

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTE — serve the SPA
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return app.response_class(INDEX_HTML, mimetype='text/html')

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    seed_items()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
