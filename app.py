from flask import Flask, request, jsonify, render_template, Response, send_from_directory
from flask_cors import CORS
import base64
import cv2
import numpy as np
import mysql.connector
import os
import pickle
import time
from datetime import datetime
from werkzeug.utils import secure_filename

# --- AI LIBRARIES ---
# Pastikan library terinstall: pip install deepface tf-keras mediapipe
from deepface import DeepFace
import mediapipe as mp

# Matikan log tensorflow yang berisik
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

app = Flask(__name__)
CORS(app)

# ================= KONFIGURASI =================
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_CONFIG = {
    "host": "localhost",
    "user": "heidi",
    "password": "Kucing123",
    "database": "drowsiness_db"
}

# --- THRESHOLD (BATAS AMBANG) ---
EAR_THRESHOLD = 0.21        # Batas mata tertutup
MAR_THRESHOLD = 0.5         # Batas mulut menguap
HEAD_TILT_THRESHOLD = 20    # Batas kemiringan kepala

# Global Streaming Buffer
stream_buffers = {} 
stream_metadata = {} 

# Inisialisasi MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    refine_landmarks=True
)

# ================= HELPER FUNCTIONS =================
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ DB Error: {err}")
        return None

# --- MEDIAPIPE LOGIC (DROWSINESS) ---
def calculate_distance(p1, p2):
    return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def get_ear(landmarks, indices):
    p1 = landmarks[indices[0]]; p4 = landmarks[indices[3]]
    p2 = landmarks[indices[1]]; p6 = landmarks[indices[5]]
    p3 = landmarks[indices[2]]; p5 = landmarks[indices[4]]
    dist_horizontal = calculate_distance(p1, p4)
    dist_vertical_1 = calculate_distance(p2, p6)
    dist_vertical_2 = calculate_distance(p3, p5)
    if dist_horizontal == 0: return 0
    return (dist_vertical_1 + dist_vertical_2) / (2.0 * dist_horizontal)

def get_mar(landmarks, indices):
    p1 = landmarks[indices[0]]; p4 = landmarks[indices[3]]
    p2 = landmarks[indices[1]]; p6 = landmarks[indices[5]]
    p3 = landmarks[indices[2]]; p5 = landmarks[indices[4]]
    dist_horizontal = calculate_distance(p1, p4)
    dist_vertical_1 = calculate_distance(p2, p6)
    dist_vertical_2 = calculate_distance(p3, p5)
    if dist_horizontal == 0: return 0
    return (dist_vertical_1 + dist_vertical_2) / (2.0 * dist_horizontal)

def analyze_drowsiness(image):
    h, w, _ = image.shape
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_image)
    ear = 0; mar = 0; head_tilt = 0; is_drowsy = False
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            lm = face_landmarks.landmark
            LEFT_EYE = [33, 160, 158, 133, 153, 144]
            RIGHT_EYE = [362, 385, 387, 263, 373, 380]
            LIPS = [61, 291, 39, 181, 0, 17]
            
            left_ear = get_ear(lm, LEFT_EYE)
            right_ear = get_ear(lm, RIGHT_EYE)
            ear = (left_ear + right_ear) / 2.0
            mar = get_mar(lm, LIPS)
            
            top_head = lm[10]; chin = lm[152]
            dx = (chin.x - top_head.x) * w; dy = (chin.y - top_head.y) * h
            head_tilt = abs(np.degrees(np.arctan2(dx, dy)))
            
            if ear < EAR_THRESHOLD or mar > MAR_THRESHOLD or head_tilt > HEAD_TILT_THRESHOLD:
                is_drowsy = True
            break
    return is_drowsy, ear, mar, head_tilt

# --- DEEPFACE LOGIC (RECOGNITION) ---
def extract_face_embedding(image):
    try:
        embedding_objs = DeepFace.represent(
            img_path = image,
            model_name = "Facenet",
            enforce_detection = False,
            detector_backend = "opencv"
        )
        if len(embedding_objs) > 0: return embedding_objs[0]["embedding"]
        return None
    except Exception as e:
        print(f"⚠️ Embed Error: {e}")
        return None

def cosine_similarity(a, b):
    a = np.array(a); b = np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0: return 0
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# ================= ROUTES =================

@app.route("/")
def index(): return render_template("index.html")

@app.route("/admin")
def drivers(): return render_template("admin.html")

@app.route("/reports")
def reports(): return render_template("reports.html")

# --- ROUTE PENTING: AKSES FOTO DRIVER ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- API DRIVERS ---
@app.route("/api/drivers", methods=["GET", "POST"])
def drivers_api():
    conn = get_db_connection()
    if not conn: 
        return jsonify({"error": "Failed to connect to database"}), 500
    
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == "GET":
            # Tambahkan try-except disini agar tidak crash 500 HTML
            cursor.execute("SELECT * FROM drivers ORDER BY created_at DESC")
            drivers = cursor.fetchall()
            for d in drivers: 
                # Handle jika created_at None atau error konversi
                if d["created_at"]:
                    d["created_at"] = str(d["created_at"])
            
            return jsonify({"drivers": drivers}), 200
        
        elif request.method == "POST":
            # ... (Logic POST sama seperti sebelumnya) ...
            driver_name = request.form.get("driver_name"); employee_id = request.form.get("employee_id")
            face_blob = None; photo_path = None

            if 'photo' in request.files:
                photo = request.files['photo']
                if photo.filename != '':
                    filename = secure_filename(f"{employee_id}_{int(time.time())}.jpg")
                    photo_path = os.path.join(UPLOAD_FOLDER, filename)
                    photo.save(photo_path)
                    
                    img = cv2.imread(photo_path)
                    embed = extract_face_embedding(img)
                    if embed: face_blob = pickle.dumps(embed)
                    else: return jsonify({"error": "Wajah tidak terdeteksi!"}), 400

            cursor.execute("""
                INSERT INTO drivers (driver_name, employee_id, phone, email, photo_path, face_embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (driver_name, employee_id, request.form.get("phone"), request.form.get("email"), photo_path, face_blob))
            conn.commit()
            return jsonify({"message": "OK"}), 201

    except mysql.connector.Error as err:
        print(f"❌ SQL Error: {err}") # Ini akan muncul di terminal
        return jsonify({"error": f"Database Error: {err}"}), 500
    except Exception as e:
        print(f"❌ General Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# --- API STREAMING ---
@app.route('/api/stream/push/<esp32_id>', methods=['POST'])
def push_stream_frame(esp32_id):
    if 'image' not in request.files: return jsonify({"error": "No image"}), 400
    file = request.files['image']
    stream_buffers[esp32_id] = file.read()
    stream_metadata[esp32_id] = {'last_seen': datetime.now(), 'is_active': True, 'drowsy_status': stream_metadata.get(esp32_id, {}).get('drowsy_status', False)}
    return jsonify({"status": "received"}), 200

@app.route('/api/stream/<esp32_id>')
def stream_video(esp32_id):
    def generate():
        while True:
            if esp32_id in stream_buffers:
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + stream_buffers[esp32_id] + b'\r\n')
            time.sleep(0.1)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stream/list', methods=['GET'])
def stream_list():
    active = []
    now = datetime.now()
    for esp, meta in stream_metadata.items():
        if (now - meta['last_seen']).total_seconds() < 10:
            active.append({"esp32_id": esp, "is_active": True, "is_drowsy": meta.get('drowsy_status', False)})
    return jsonify({"streams": active}), 200

# --- CORE LOGIC: DETECT & IDENTIFY ---
@app.route("/api/detect", methods=["POST"])
def detect():
    data = request.get_json(force=True, silent=True)
    esp32_id = data.get("esp32_id"); img_b64 = data.get("image")
    if not esp32_id or not img_b64: return jsonify({"error": "Invalid"}), 400

    try:
        img_bytes = base64.b64decode(img_b64)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        fname = f"{esp32_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        fpath = os.path.join(UPLOAD_FOLDER, fname)
        cv2.imwrite(fpath, frame)
    except: return jsonify({"error": "Image Decode Failed"}), 500

    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)

    # 1. IDENTIFIKASI DRIVER (DeepFace)
    curr_embed = extract_face_embedding(frame)
    driver_id = None; driver_name = "Unknown"
    
    if curr_embed:
        cursor.execute("SELECT id, driver_name, face_embedding FROM drivers WHERE face_embedding IS NOT NULL")
        rows = cursor.fetchall()
        best_score = 0
        for row in rows:
            try:
                db_embed = pickle.loads(row['face_embedding'])
                score = cosine_similarity(curr_embed, db_embed)
                if score > best_score and score > 0.45: # Threshold kecocokan
                    best_score = score; driver_id = row['id']; driver_name = row['driver_name']
            except: continue
    
    # 2. DETEKSI NGANTUK (MediaPipe)
    is_drowsy, ear, mar, head_tilt = analyze_drowsiness(frame)
    if esp32_id in stream_metadata: stream_metadata[esp32_id]['drowsy_status'] = is_drowsy

    # 3. SIMPAN DB
    try:
        cursor.execute("INSERT IGNORE INTO devices (esp32_id) VALUES (%s)", (esp32_id,))
        cursor.execute("""
            INSERT INTO detections (driver_id, esp32_id, eye_aspect_ratio, mouth_aspect_ratio, head_tilt, is_drowsy, image_path) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
            (driver_id, esp32_id, ear, mar, head_tilt, is_drowsy, fpath))
        
        if is_drowsy:
            alert_type = 'YAWNING' if mar > MAR_THRESHOLD else 'DROWSY'
            print(f"🚨 ALERT: {driver_name} - {alert_type}")
            cursor.execute("INSERT INTO alerts (driver_id, esp32_id, alert_type, confidence, vehicle_number) VALUES (%s, %s, %s, 0.95, 'UNKNOWN')", (driver_id, esp32_id, alert_type))
            
        conn.commit()
    except Exception as e: print(f"DB Error: {e}")
    finally: cursor.close(); conn.close()

    return jsonify({
        "driver": driver_name, "is_drowsy": is_drowsy, 
        "ear": round(ear, 2), "mar": round(mar, 2), "tilt": round(head_tilt, 1)
    })

# --- STATS API ---
@app.route("/api/stats", methods=["GET"])
def get_stats():
    conn = get_db_connection(); 
    if not conn: return jsonify({}), 500
    cursor = conn.cursor(dictionary=True)
    stats = {}
    cursor.execute("SELECT COUNT(*) as t FROM drivers"); stats['total_drivers'] = cursor.fetchone()['t']
    cursor.execute("SELECT COUNT(*) as t FROM alerts WHERE DATE(created_at) = CURDATE()"); stats['alerts_today'] = cursor.fetchone()['t']
    cursor.execute("SELECT COUNT(*) as t FROM alerts WHERE alert_type IN ('DROWSY','YAWNING') AND DATE(created_at) = CURDATE()"); stats['critical_today'] = cursor.fetchone()['t']
    stats['alerts_week'] = 0 
    cursor.close(); conn.close()
    return jsonify(stats)

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    conn = get_db_connection(); 
    if not conn: return jsonify({"alerts": []}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT a.id, d.driver_name, a.alert_type as status, a.confidence, a.esp32_id, a.created_at as alert_time FROM alerts a LEFT JOIN drivers d ON a.driver_id = d.id ORDER BY a.created_at DESC LIMIT 20")
    alerts = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify({"alerts": alerts})

if __name__ == "__main__":
    print("🚀 Server starting on http://localhost:7001 ...")
    app.run(host="0.0.0.0", port=7001, debug=True)