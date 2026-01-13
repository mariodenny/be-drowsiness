-- --------------------------------------------------------
-- Host:                         103.197.188.191
-- Server version:               8.0.42-0ubuntu0.20.04.1 - (Ubuntu)
-- Server OS:                    Linux
-- HeidiSQL Version:             12.1.0.6537
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for drowsiness_db
CREATE DATABASE IF NOT EXISTS `drowsiness_db` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `drowsiness_db`;

-- Dumping structure for table drowsiness_db.alerts
CREATE TABLE IF NOT EXISTS `alerts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `detection_id` int NOT NULL,
  `alert_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `alert_type` enum('warning','critical') COLLATE utf8mb4_unicode_ci DEFAULT 'warning',
  `notified` tinyint(1) DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_detection_id` (`detection_id`),
  KEY `idx_alert_time` (`alert_time`),
  KEY `idx_notified` (`notified`),
  KEY `idx_alert_type` (`alert_type`),
  CONSTRAINT `alerts_ibfk_1` FOREIGN KEY (`detection_id`) REFERENCES `detections` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table drowsiness_db.alerts: ~3 rows (approximately)
INSERT INTO `alerts` (`id`, `detection_id`, `alert_time`, `alert_type`, `notified`, `created_at`) VALUES
	(1, 2, '2025-12-22 22:16:54', 'warning', 0, '2025-12-22 15:16:54'),
	(2, 4, '2025-12-22 22:18:06', 'warning', 0, '2025-12-22 15:18:06'),
	(3, 5, '2025-12-22 22:18:36', 'warning', 0, '2025-12-22 15:18:36');

-- Dumping structure for table drowsiness_db.detections
CREATE TABLE IF NOT EXISTS `detections` (
  `id` int NOT NULL AUTO_INCREMENT,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  `esp32_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `eye_aspect_ratio` float DEFAULT NULL,
  `mouth_aspect_ratio` float DEFAULT NULL,
  `head_tilt` float DEFAULT NULL,
  `is_drowsy` tinyint(1) DEFAULT '0',
  `image_path` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_esp32_id` (`esp32_id`),
  KEY `idx_timestamp` (`timestamp`),
  KEY `idx_is_drowsy` (`is_drowsy`),
  KEY `idx_esp32_timestamp` (`esp32_id`,`timestamp`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table drowsiness_db.detections: ~6 rows (approximately)
INSERT INTO `detections` (`id`, `timestamp`, `esp32_id`, `eye_aspect_ratio`, `mouth_aspect_ratio`, `head_tilt`, `is_drowsy`, `image_path`, `created_at`, `updated_at`) VALUES
	(1, '2025-12-22 22:16:28', 'ESP32-CAM-001', 0.320041, 0.405873, 7.56728, 0, 'uploads/ESP32-CAM-001_20251222_221628.jpg', '2025-12-22 15:16:28', '2025-12-22 15:16:28'),
	(2, '2025-12-22 22:16:54', 'ESP32-CAM-001', 0.21826, 0.580548, 12.8063, 1, 'uploads/ESP32-CAM-001_20251222_221654.jpg', '2025-12-22 15:16:54', '2025-12-22 15:16:54'),
	(3, '2025-12-22 22:17:03', 'ESP32-CAM-001', 0.303989, 0.341452, 0.997164, 0, 'uploads/ESP32-CAM-001_20251222_221703.jpg', '2025-12-22 15:17:03', '2025-12-22 15:17:03'),
	(4, '2025-12-22 22:18:06', 'ESP32-CAM-001', 0.264381, 0.35169, 14.8758, 1, 'uploads/ESP32-CAM-001_20251222_221806.jpg', '2025-12-22 15:18:06', '2025-12-22 15:18:06'),
	(5, '2025-12-22 22:18:36', 'ESP32-CAM-001', 0.336905, 0.347491, 13.2254, 1, 'uploads/ESP32-CAM-001_20251222_221836.jpg', '2025-12-22 15:18:36', '2025-12-22 15:18:36'),
	(6, '2025-12-22 22:21:37', 'ESP32-CAM-001', 0.243931, 0.300604, 3.66058, 0, 'uploads/ESP32-CAM-001_20251222_222137.jpg', '2025-12-22 15:21:37', '2025-12-22 15:21:37');

-- Dumping structure for table drowsiness_db.esp32_devices
CREATE TABLE IF NOT EXISTS `esp32_devices` (
  `id` int NOT NULL AUTO_INCREMENT,
  `device_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `device_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `registered_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `last_seen` datetime DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `device_id` (`device_id`),
  KEY `idx_device_id` (`device_id`),
  KEY `idx_is_active` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table drowsiness_db.esp32_devices: ~1 rows (approximately)
INSERT INTO `esp32_devices` (`id`, `device_id`, `device_name`, `registered_at`, `last_seen`, `is_active`) VALUES
	(1, 'ESP32-CAM-001', 'Main Driver Camera', '2025-12-22 22:09:39', NULL, 1);

-- Dumping structure for table drowsiness_db.system_stats
CREATE TABLE IF NOT EXISTS `system_stats` (
  `id` int NOT NULL AUTO_INCREMENT,
  `stat_date` date NOT NULL,
  `total_detections` int DEFAULT '0',
  `drowsy_detections` int DEFAULT '0',
  `avg_ear` float DEFAULT NULL,
  `avg_mar` float DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_stat_date` (`stat_date`),
  KEY `idx_stat_date` (`stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dumping data for table drowsiness_db.system_stats: ~0 rows (approximately)

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
