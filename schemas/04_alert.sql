DROP TABLE IF EXISTS alerts;

CREATE TABLE alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    driver_id INT NULL,
    esp32_id VARCHAR(50),
    alert_type VARCHAR(50), -- Isi: 'DROWSY' atau 'YAWNING'
    confidence FLOAT DEFAULT 0.0,
    vehicle_number VARCHAR(20) DEFAULT 'UNKNOWN',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
);

-- cleanup
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS users;