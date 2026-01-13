CREATE TABLE detections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    esp32_id VARCHAR(50),
    eye_aspect_ratio FLOAT,
    mouth_aspect_ratio FLOAT,
    head_tilt FLOAT,
    is_drowsy BOOLEAN,
    image_path VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
