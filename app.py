from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import cv2
import numpy as np
import mysql.connector
import os
import hashlib
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ======================
# DATABASE
# ======================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="drowsiness_db"
)
cursor = db.cursor(dictionary=True)

# ======================
# UTILS
# ======================
def generate_token():
    return secrets.token_hex(32)

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# ======================
# FACE EMBEDDING (DUMMY)
# GANTI NANTI DENGAN ML
# ======================
def extract_face_embedding(image):
    """
    sementara dummy
    nanti ganti MediaPipe / FaceNet
    """
    np.random.seed(int(np.mean(image)))
    return np.random.rand(128).tolist()

# ======================
# AUTH VIA FACE
# ======================
@app.route("/")
def index():
    return jsonify(
        {"message" : "Hello, Mom <3"}
    )

@app.route("/api/auth/face", methods=["POST"])
def auth_face():
    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    esp32_id = data.get("esp32_id")
    image_base64 = data.get("image")

    if not esp32_id or not image_base64:
        return jsonify({"error": "Invalid payload"}), 400

    # decode image
    try:
        image_bytes = base64.b64decode(image_base64)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except:
        return jsonify({"error": "Image decode failed"}), 400

    if frame is None:
        return jsonify({"error": "Invalid image"}), 400

    # extract face embedding
    embedding = extract_face_embedding(frame)

    # cari user paling mirip
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

    # ======================
    # LOGIN
    # ======================
    if best_score > THRESHOLD:
        user_id = matched_user_id
        status = "login"

    # ======================
    # REGISTER
    # ======================
    else:
        emb_blob = np.array(embedding, dtype=np.float32).tobytes()
        cursor.execute(
            "INSERT INTO users (face_embedding) VALUES (%s)",
            (emb_blob,)
        )
        db.commit()
        user_id = cursor.lastrowid
        status = "registered"

    # ======================
    # DEVICE
    # ======================
    cursor.execute(
        "SELECT id FROM devices WHERE esp32_id=%s",
        (esp32_id,)
    )
    device = cursor.fetchone()

    if device:
        device_id = device["id"]
        cursor.execute(
            "UPDATE devices SET user_id=%s WHERE id=%s",
            (user_id, device_id)
        )
    else:
        cursor.execute(
            "INSERT INTO devices (esp32_id, user_id) VALUES (%s,%s)",
            (esp32_id, user_id)
        )
        device_id = cursor.lastrowid

    db.commit()

    # ======================
    # SESSION
    # ======================
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

# ======================
# TOKEN VALIDATION
# ======================
def validate_token(token):
    cursor.execute("""
        SELECT user_id FROM sessions
        WHERE token=%s AND expires_at > NOW()
    """, (token,))
    row = cursor.fetchone()
    return row["user_id"] if row else None

# ======================
# DETECT (UPDATE)
# ======================
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

    # decode image
    image_bytes = base64.b64decode(image_base64)
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    filename = f"{esp32_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    cv2.imwrite(image_path, frame)

    # dummy drowsiness
    ear = np.random.uniform(0.18, 0.35)
    mar = np.random.uniform(0.3, 0.7)
    head_tilt = np.random.uniform(0, 15)
    is_drowsy = ear < 0.22 or mar > 0.6 or head_tilt > 12

    cursor.execute("""
        INSERT INTO detections
        (user_id, esp32_id, eye_aspect_ratio, mouth_aspect_ratio,
         head_tilt, is_drowsy, image_path)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id, esp32_id, ear, mar, head_tilt, is_drowsy, image_path
    ))
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

    # cek device
    cursor.execute(
        "SELECT id, device_token FROM devices WHERE esp32_id=%s",
        (esp32_id,)
    )
    device = cursor.fetchone()

    if device:
        return jsonify({
            "status": "already_registered",
            "device_id": device["id"],
            "device_token": device["device_token"]
        }), 200

    # register baru
    device_token = secrets.token_hex(32)

    cursor.execute("""
        INSERT INTO devices (esp32_id, device_token)
        VALUES (%s, %s)
    """, (esp32_id, device_token))
    db.commit()

    return jsonify({
        "status": "registered",
        "device_id": cursor.lastrowid,
        "device_token": device_token
    }), 201

# ======================
# 1️⃣ GET USERS + DEVICES
# ======================
@app.route("/api/users", methods=["GET"])
def get_users_with_devices():
    cursor.execute("""
        SELECT u.id AS user_id, u.name, u.created_at, 
               d.id AS device_id, d.esp32_id, d.device_token, d.registered_at
        FROM users u
        LEFT JOIN devices d ON u.id = d.user_id
    """)
    rows = cursor.fetchall()

    # strukturisasi data: user -> devices[]
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

# ======================
# 2️⃣ GET USER TOKENS
# ======================
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

# ======================
# 3️⃣ GET DEVICE LIST
# ======================
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

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
