from flask import Flask, request, jsonify, render_template, Response, send_file
from flask_cors import CORS
import base64
import cv2
import numpy as np
import mysql.connector
import os
import hashlib
import secrets
from datetime import datetime, timedelta
import threading
import queue
import time
import io
from collections import defaultdict
from werkzeug.utils import secure_filename
import csv

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# db = mysql.connector.connect(
#     host="localhost",
#     user="root",
#     password="",
#     database="drowsiness_db"
# )

db = mysql.connector.connect(
    host="localhost",
    user="heidi",
    password="Kucing123",
    database="drowsiness_db"
)
cursor = db.cursor(dictionary=True)

def generate_token():
    return secrets.token_hex(32)

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def extract_face_embedding(image):
    np.random.seed(int(np.mean(image)))
    return np.random.rand(128).tolist()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def drivers():
    return render_template("admin.html")

@app.route("/reports")
def reports():
    return render_template("reports.html")

@app.route("/api/stats", methods=["GET"])
def get_stats():
    cursor.execute("SELECT COUNT(*) as total FROM drivers")
    total_drivers = cursor.fetchone()["total"]
    
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) as count FROM alerts WHERE DATE(created_at) = %s", (today,))
    alerts_today = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM alerts WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
    alerts_week = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM alerts WHERE alert_type = 'CRITICAL' AND DATE(created_at) = %s", (today,))
    critical_today = cursor.fetchone()["count"]
    
    return jsonify({
        "total_drivers": total_drivers,
        "alerts_today": alerts_today,
        "alerts_week": alerts_week,
        "critical_today": critical_today
    }), 200

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    limit = request.args.get("limit", 20, type=int)
    
    cursor.execute("""
        SELECT 
            a.id,
            d.driver_name,
            d.employee_id,
            d.phone,
            a.alert_type as status,
            a.confidence,
            a.vehicle_number,
            a.created_at as alert_time
        FROM alerts a
        LEFT JOIN drivers d ON a.driver_id = d.id
        ORDER BY a.created_at DESC
        LIMIT %s
    """, (limit,))
    
    alerts = cursor.fetchall()
    
    for alert in alerts:
        alert["alert_time"] = alert["alert_time"].strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({"alerts": alerts}), 200

@app.route("/api/drivers", methods=["GET", "POST"])
def drivers_api():
    if request.method == "GET":
        cursor.execute("""
            SELECT id, driver_name, employee_id, phone, email, 
                   photo_path, status, created_at
            FROM drivers 
            ORDER BY created_at DESC
        """)
        drivers = cursor.fetchall()
        
        for driver in drivers:
            driver["created_at"] = driver["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        
        return jsonify({"drivers": drivers}), 200
    
    elif request.method == "POST":
        driver_name = request.form.get("driver_name")
        employee_id = request.form.get("employee_id")
        phone = request.form.get("phone")
        email = request.form.get("email")
        
        if not driver_name or not employee_id:
            return jsonify({"error": "Driver name and employee ID are required"}), 400
        
        photo_path = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename != '':
                filename = secure_filename(f"{employee_id}_{photo.filename}")
                photo_path = os.path.join(UPLOAD_FOLDER, filename)
                photo.save(photo_path)
        
        cursor.execute("""
            INSERT INTO drivers 
            (driver_name, employee_id, phone, email, photo_path, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
        """, (driver_name, employee_id, phone, email, photo_path))
        
        db.commit()
        
        return jsonify({"message": "Driver added successfully"}), 201

@app.route("/api/reports", methods=["GET"])
def get_reports():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    driver_id = request.args.get("driver_id")
    
    query = """
        SELECT 
            a.id,
            d.driver_name,
            d.employee_id,
            d.phone,
            a.alert_type as status,
            a.confidence,
            a.vehicle_number,
            a.created_at as alert_time
        FROM alerts a
        LEFT JOIN drivers d ON a.driver_id = d.id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND DATE(a.created_at) >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND DATE(a.created_at) <= %s"
        params.append(end_date)
    
    if driver_id:
        query += " AND a.driver_id = %s"
        params.append(driver_id)
    
    query += " ORDER BY a.created_at DESC"
    
    cursor.execute(query, params)
    reports = cursor.fetchall()
    
    for report in reports:
        report["alert_time"] = report["alert_time"].strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({"reports": reports}), 200

@app.route("/api/reports/export", methods=["GET"])
def export_reports():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    driver_id = request.args.get("driver_id")
    
    query = """
        SELECT 
            a.id,
            d.driver_name,
            d.employee_id,
            d.phone,
            a.alert_type as status,
            a.confidence,
            a.vehicle_number,
            a.created_at as alert_time
        FROM alerts a
        LEFT JOIN drivers d ON a.driver_id = d.id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND DATE(a.created_at) >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND DATE(a.created_at) <= %s"
        params.append(end_date)
    
    if driver_id:
        query += " AND a.driver_id = %s"
        params.append(driver_id)
    
    cursor.execute(query, params)
    reports = cursor.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Driver Name', 'Employee ID', 'Phone', 'Status', 
                     'Confidence', 'Vehicle', 'Alert Time'])
    
    for report in reports:
        writer.writerow([
            report['id'],
            report['driver_name'],
            report['employee_id'],
            report['phone'],
            report['status'],
            f"{report['confidence']*100:.1f}%",
            report['vehicle_number'],
            report['alert_time'].strftime("%Y-%m-%d %H:%M:%S")
        ])
    
    response = app.response_class(
        response=output.getvalue(),
        status=200,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=reports.csv'}
    )
    
    return response

@app.route("/api/auth/face", methods=["POST"])
def auth_face():
    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    esp32_id = data.get("esp32_id")
    image_base64 = data.get("image")

    if not esp32_id or not image_base64:
        return jsonify({"error": "Invalid payload"}), 400

    try:
        image_bytes = base64.b64decode(image_base64)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except:
        return jsonify({"error": "Image decode failed"}), 400

    if frame is None:
        return jsonify({"error": "Invalid image"}), 400

    embedding = extract_face_embedding(frame)

    cursor.execute("SELECT id, face_embedding FROM users")
    users = cursor.fetchall()

    matched_user_id = None
    best_score = 0

    for u in users:
        db_embedding = np.frombuffer(u["face_embedding"], dtype=np.float32)
        score = cosine_similarity(embedding, db_embedding)
        if score > best_score:
            best_score = score
            matched_user_id = u["id"]

    THRESHOLD = 0.85

    if best_score > THRESHOLD:
        user_id = matched_user_id
        status = "login"
    else:
        emb_blob = np.array(embedding, dtype=np.float32).tobytes()
        cursor.execute("INSERT INTO users (face_embedding) VALUES (%s)", (emb_blob,))
        db.commit()
        user_id = cursor.lastrowid
        status = "registered"

    cursor.execute("SELECT id FROM devices WHERE esp32_id=%s", (esp32_id,))
    device = cursor.fetchone()

    if device:
        device_id = device["id"]
        cursor.execute("UPDATE devices SET user_id=%s WHERE id=%s", (user_id, device_id))
    else:
        cursor.execute("INSERT INTO devices (esp32_id, user_id) VALUES (%s,%s)", (esp32_id, user_id))
        device_id = cursor.lastrowid

    db.commit()

    token = generate_token()
    expires = datetime.now() + timedelta(days=7)

    cursor.execute("""
        INSERT INTO sessions (user_id, device_id, token, expires_at)
        VALUES (%s,%s,%s,%s)
    """, (user_id, device_id, token, expires))
    db.commit()

    return jsonify({
        "status": status,
        "user_id": user_id,
        "token": token
    }), 200

def validate_token(token):
    cursor.execute("SELECT user_id FROM sessions WHERE token=%s AND expires_at > NOW()", (token,))
    row = cursor.fetchone()
    return row["user_id"] if row else None

@app.route("/api/detect", methods=["POST"])
def detect():
    data = request.get_json(force=True, silent=True)

    token = data.get("token")
    esp32_id = data.get("esp32_id")
    image_base64 = data.get("image")

    if not token or not esp32_id or not image_base64:
        return jsonify({"error": "Invalid payload"}), 400

    user_id = validate_token(token)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    image_bytes = base64.b64decode(image_base64)
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    filename = f"{esp32_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    cv2.imwrite(image_path, frame)

    ear = np.random.uniform(0.18, 0.35)
    mar = np.random.uniform(0.3, 0.7)
    head_tilt = np.random.uniform(0, 15)
    is_drowsy = ear < 0.22 or mar > 0.6 or head_tilt > 12

    cursor.execute("""
        INSERT INTO detections
        (user_id, esp32_id, eye_aspect_ratio, mouth_aspect_ratio,
         head_tilt, is_drowsy, image_path)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (user_id, esp32_id, ear, mar, head_tilt, is_drowsy, image_path))
    db.commit()

    return jsonify({
        "is_drowsy": is_drowsy,
        "ear": round(ear, 2),
        "mar": round(mar, 2),
        "head_tilt": round(head_tilt, 1)
    })

@app.route("/api/device/register", methods=["POST"])
def register_device():
    data = request.get_json(force=True, silent=True)

    esp32_id = data.get("esp32_id")
    if not esp32_id:
        return jsonify({"error": "esp32_id required"}), 400

    cursor.execute("SELECT id, device_token FROM devices WHERE esp32_id=%s", (esp32_id,))
    device = cursor.fetchone()

    if device:
        return jsonify({
            "status": "already_registered",
            "device_id": device["id"],
            "device_token": device["device_token"]
        }), 200

    device_token = secrets.token_hex(32)

    cursor.execute("INSERT INTO devices (esp32_id, device_token) VALUES (%s, %s)", (esp32_id, device_token))
    db.commit()

    return jsonify({
        "status": "registered",
        "device_id": cursor.lastrowid,
        "device_token": device_token
    }), 201

@app.route("/api/users", methods=["GET"])
def get_users_with_devices():
    cursor.execute("""
        SELECT u.id AS user_id, u.name, u.created_at, 
               d.id AS device_id, d.esp32_id, d.device_token, d.registered_at
        FROM users u
        LEFT JOIN devices d ON u.id = d.user_id
    """)
    rows = cursor.fetchall()

    users_dict = {}
    for r in rows:
        uid = r["user_id"]
        if uid not in users_dict:
            users_dict[uid] = {
                "user_id": uid,
                "name": r["name"],
                "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "devices": []
            }
        if r["device_id"]:
            users_dict[uid]["devices"].append({
                "device_id": r["device_id"],
                "esp32_id": r["esp32_id"],
                "device_token": r["device_token"],
                "registered_at": r["registered_at"].strftime("%Y-%m-%d %H:%M:%S")
            })

    return jsonify(list(users_dict.values())), 200

@app.route("/api/users/<int:user_id>/tokens", methods=["GET"])
def get_user_tokens(user_id):
    cursor.execute("""
        SELECT s.id AS session_id, s.token, s.expires_at, d.esp32_id
        FROM sessions s
        JOIN devices d ON s.device_id = d.id
        WHERE s.user_id=%s
    """, (user_id,))
    rows = cursor.fetchall()

    tokens = []
    for r in rows:
        tokens.append({
            "session_id": r["session_id"],
            "token": r["token"],
            "expires_at": r["expires_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "esp32_id": r["esp32_id"]
        })

    return jsonify({"user_id": user_id, "tokens": tokens}), 200

@app.route("/api/devices", methods=["GET"])
def get_devices():
    cursor.execute("""
        SELECT d.id AS device_id, d.esp32_id, d.device_token, d.registered_at, u.id AS user_id, u.name
        FROM devices d
        LEFT JOIN users u ON d.user_id = u.id
    """)
    rows = cursor.fetchall()

    devices = []
    for r in rows:
        devices.append({
            "device_id": r["device_id"],
            "esp32_id": r["esp32_id"],
            "device_token": r["device_token"],
            "registered_at": r["registered_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "user": {
                "user_id": r["user_id"],
                "name": r["name"]
            } if r["user_id"] else None
        })

    return jsonify(devices), 200

stream_queues = defaultdict(queue.Queue)
stream_metadata = defaultdict(dict)

@app.route('/api/stream/list', methods=['GET'])
def stream_list():
    active_streams = []
    for esp32_id in list(stream_queues.keys()):
        active_streams.append({
            "esp32_id": esp32_id,
            "queue_size": stream_queues[esp32_id].qsize(),
            "is_active": stream_queues[esp32_id].qsize() > 0,
            "last_update": stream_metadata.get(esp32_id, {}).get('last_update', None),
            "is_drowsy": stream_metadata.get(esp32_id, {}).get('is_drowsy', False)
        })
    
    return jsonify({"streams": active_streams}), 200

@app.route('/api/stream/<esp32_id>')
def stream_video(esp32_id):
    def generate():
        while True:
            try:
                if esp32_id in stream_queues and not stream_queues[esp32_id].empty():
                    frame = stream_queues[esp32_id].get()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                else:
                    placeholder = b''
                    try:
                        with open('static/placeholder.jpg', 'rb') as f:
                            placeholder = f.read()
                    except:
                        pass
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Stream error: {e}")
                time.sleep(1)
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stream/push/<esp32_id>', methods=['POST'])
def push_stream_frame(esp32_id):
    if 'image' not in request.files:
        return jsonify({"error": "No image file"}), 400
    
    image_file = request.files['image']
    frame_data = image_file.read()
    
    stream_metadata[esp32_id] = {
        'last_update': datetime.now(),
        'frame_count': stream_metadata.get(esp32_id, {}).get('frame_count', 0) + 1,
        'is_drowsy': stream_metadata.get(esp32_id, {}).get('is_drowsy', False)
    }
    
    stream_queues[esp32_id].put(frame_data)
    
    while stream_queues[esp32_id].qsize() > 10:
        stream_queues[esp32_id].get()
    
    return jsonify({"status": "frame_received"}), 200

@app.route('/api/stream/status/<esp32_id>', methods=['GET'])
def stream_status(esp32_id):
    if esp32_id not in stream_queues:
        return jsonify({"error": "Stream not found"}), 404
    
    status = {
        "esp32_id": esp32_id,
        "queue_size": stream_queues[esp32_id].qsize(),
        "is_active": stream_queues[esp32_id].qsize() > 0,
        "last_update": stream_metadata.get(esp32_id, {}).get('last_update'),
        "frame_count": stream_metadata.get(esp32_id, {}).get('frame_count', 0),
        "is_drowsy": stream_metadata.get(esp32_id, {}).get('is_drowsy', False),
        "clients_count": 1
    }
    
    return jsonify(status), 200

@app.route('/api/stream/capture/<esp32_id>', methods=['GET'])
def capture_snapshot(esp32_id):
    if esp32_id not in stream_queues or stream_queues[esp32_id].empty():
        return jsonify({"error": "No frame available"}), 404
    
    frame = stream_queues[esp32_id].queue[-1]
    
    return send_file(
        io.BytesIO(frame),
        mimetype='image/jpeg',
        as_attachment=True,
        download_name=f'snapshot-{esp32_id}-{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
    )

@app.route('/api/stream/notify_drowsy/<esp32_id>', methods=['POST'])
def notify_drowsy(esp32_id):
    data = request.get_json()
    is_drowsy = data.get('is_drowsy', False)
    
    if esp32_id in stream_metadata:
        stream_metadata[esp32_id]['is_drowsy'] = is_drowsy
        stream_metadata[esp32_id]['last_drowsy_update'] = datetime.now()
    
    return jsonify({"status": "drowsy_status_updated"}), 200

@app.route('/api/stream/devices', methods=['GET'])
def get_stream_devices():
    active_devices = []
    
    for esp32_id in stream_queues:
        if stream_queues[esp32_id].qsize() > 0:
            metadata = stream_metadata.get(esp32_id, {})
            active_devices.append({
                'esp32_id': esp32_id,
                'last_seen': metadata.get('last_update'),
                'is_drowsy': metadata.get('is_drowsy', False),
                'frame_count': metadata.get('frame_count', 0)
            })
    
    return jsonify(active_devices), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7001, debug=True)