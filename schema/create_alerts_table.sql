CREATE TABLE alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    detection_id INT NOT NULL,
    alert_type VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (detection_id) REFERENCES detections(id)
);
