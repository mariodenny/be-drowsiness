from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import cv2
import numpy as np
import mysql.connector
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024  # 6 MB

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ======================
# DATABASE CONNECTION
# ======================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="drowsiness_db"
)

cursor = db.cursor()

# ======================
# DROWSINESS LOGIC (SIMPLE RULE)
# ======================
def analyze_frame(image):
    """
    NANTI diganti ML / Mediapipe
    sekarang dummy + rule-based
    """

    # ---- dummy nilai awal ----
    ear = np.random.uniform(0.18, 0.35)
    mar = np.random.uniform(0.30, 0.70)
    head_tilt = np.random.uniform(0, 15)

    # ---- rule drowsy ----
    is_drowsy = False

    if ear < 0.22:
        is_drowsy = True
    if mar > 0.6:
        is_drowsy = True
    if head_tilt > 12:
        is_drowsy = True

    return ear, mar, head_tilt, is_drowsy


# ======================
# API ENDPOINT
# ======================
@app.route("/")
def hello_world():
    return jsonify({
        "message" : "Hello World!"
    })

@app.route("/api/detect", methods=["POST"])
def detect():
    data = request.get_json(force=True, silent=True)

    if not data:
        print("JSON PARSE FAILED")
        return jsonify({"error": "Invalid JSON"}), 400

    print("REQUEST MASUK", data)

    esp32_id = data.get("esp32_id")
    image_base64 = data.get("image")

    if not esp32_id or not image_base64:
        return jsonify({"error": "Invalid payload"}), 400

    # ===== Decode base64 safely =====
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        print("BASE64 ERROR:", e)
        return jsonify({"error": "Invalid image"}), 400

    # ===== Decode image =====
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "Image decode failed"}), 400

    # ===== Save image =====
    filename = f"{esp32_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    cv2.imwrite(image_path, frame)

    # ===== Analyze =====
    ear, mar, head_tilt, is_drowsy = analyze_frame(frame)

    # ===== Save detection =====
    cursor.execute("""
        INSERT INTO detections
        (esp32_id, eye_aspect_ratio, mouth_aspect_ratio, head_tilt, is_drowsy, image_path)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        esp32_id, ear, mar, head_tilt, is_drowsy, image_path
    ))
    db.commit()

    detection_id = cursor.lastrowid

    # ===== Alert =====
    if is_drowsy:
        cursor.execute("""
            INSERT INTO alerts (detection_id, alert_type)
            VALUES (%s, %s)
        """, (detection_id, "warning"))
        db.commit()

    # ===== Response =====
    return jsonify({
        "is_drowsy": is_drowsy,
        "ear": round(ear, 2),
        "mar": round(mar, 2),
        "head_tilt": round(head_tilt, 1)
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
