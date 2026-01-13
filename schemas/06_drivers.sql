-- DRIVERS TABLE (for admin management)
CREATE TABLE drivers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    driver_name VARCHAR(100) NOT NULL,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    photo_path VARCHAR(255),
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ALERTS TABLE (enhanced for reports)
ALTER TABLE alerts 
ADD COLUMN driver_id INT NULL,
ADD COLUMN confidence FLOAT DEFAULT 0.0,
ADD COLUMN vehicle_number VARCHAR(20),
ADD FOREIGN KEY (driver_id) REFERENCES drivers(id);