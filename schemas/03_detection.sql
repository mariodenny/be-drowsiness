DROP TABLE IF EXISTS detections;

CREATE TABLE detections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    driver_id INT NULL, -- NULL jika wajah tidak dikenali (Unknown)
    esp32_id VARCHAR(50),
    eye_aspect_ratio FLOAT,   -- Nilai EAR (Mata)
    mouth_aspect_ratio FLOAT, -- Nilai MAR (Mulut)
    head_tilt FLOAT,          -- Kemiringan Kepala
    is_drowsy BOOLEAN,
    image_path VARCHAR(255),  -- Lokasi file foto bukti
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
);