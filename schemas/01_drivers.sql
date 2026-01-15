-- 

DROP TABLE IF EXISTS drivers;

CREATE TABLE drivers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    driver_name VARCHAR(100) NOT NULL,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    photo_path VARCHAR(255),
    face_embedding BLOB, -- Kolom ini menyimpan data vektor wajah dari DeepFace
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);