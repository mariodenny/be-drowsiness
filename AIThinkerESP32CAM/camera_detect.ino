#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include "base64.h"
#include <WebServer.h>
#include <WiFiClient.h>

// ================== DEBUG SETTINGS ==================
#define DEBUG_SERIAL true          // Enable serial debug
#define DEBUG_STREAM true          // Enable stream debug
#define DEBUG_DETECTION true       // Enable detection debug
#define DEBUG_WIFI true            // Enable WiFi debug

// ================== WIFI ==================
const char* ssid = "KodingNextCemaraLt2";
const char* password = "KNCemara01#";

// ================== SERVER VPS CONFIG ==================
// Masukkan IP dan Port VPS di sini (Tanpa http://)
const char* serverHost = "103.197.188.191";
const int serverPort = 7001;

// Endpoint paths
const char* detectEndpoint = "/api/detect";
const char* streamPushEndpoint = "/api/stream/push/";
const char* notifyDrowsyEndpoint = "/api/stream/notify_drowsy/";

// Helper untuk URL lengkap (dipakai detection & notify)
String getVpsUrl() {
    return "http://" + String(serverHost) + ":" + String(serverPort);
}

// ================== WEBSERVER FOR LOCAL CONTROL ==================
WebServer localServer(80);

// ================== CAMERA PIN (AI THINKER) ==================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define LED_FLASH 4

// ================== GLOBAL VARIABLES ==================
bool isDrowsy = false;
float ear = 0, mar = 0, headTilt = 0;
String esp32Id = "ESP32-CAM-001";

// Timing variables
unsigned long lastDetection = 0;
unsigned long lastStreamFrame = 0;
unsigned long lastStatusUpdate = 0;
const unsigned long DETECTION_INTERVAL = 3000;    // 3 detik
const unsigned long STREAM_INTERVAL = 200;        // 5 FPS (200ms)
const unsigned long STATUS_INTERVAL = 5000;       // 5 detik status update
bool isStreaming = true;

// Statistics
unsigned long streamFrameCount = 0;
unsigned long detectionCount = 0;
unsigned long streamBytesSent = 0;
unsigned long streamErrors = 0;
unsigned long detectionErrors = 0;

// ================== CAMERA CONFIG ==================
camera_config_t camera_config = {
  .pin_pwdn = PWDN_GPIO_NUM,
  .pin_reset = RESET_GPIO_NUM,
  .pin_xclk = XCLK_GPIO_NUM,
  .pin_sccb_sda = SIOD_GPIO_NUM,
  .pin_sccb_scl = SIOC_GPIO_NUM,
  .pin_d7 = Y9_GPIO_NUM,
  .pin_d6 = Y8_GPIO_NUM,
  .pin_d5 = Y7_GPIO_NUM,
  .pin_d4 = Y6_GPIO_NUM,
  .pin_d3 = Y5_GPIO_NUM,
  .pin_d2 = Y4_GPIO_NUM,
  .pin_d1 = Y3_GPIO_NUM,
  .pin_d0 = Y2_GPIO_NUM,
  .pin_vsync = VSYNC_GPIO_NUM,
  .pin_href = HREF_GPIO_NUM,
  .pin_pclk = PCLK_GPIO_NUM,
  .xclk_freq_hz = 20000000,
  .ledc_timer = LEDC_TIMER_0,
  .ledc_channel = LEDC_CHANNEL_0,
  .pixel_format = PIXFORMAT_JPEG,
  .frame_size = FRAMESIZE_VGA,
  .jpeg_quality = 12,
  .fb_count = 2
};

// ================== FUNCTION PROTOTYPES ==================
void debugPrint(String message);
void debugPrintln(String message);
void debugPrintf(const char* format, ...);
void connectWiFi();
void handleRoot();
void handleStatus();
void handleCapture();
void handleLED();
void handleRestart();
void handleStreamToggle();
void handleTestVPS();
void handleDebug();
void handleStats();
void sendFrameToVPS();
void sendDetectionToVPS();
void notifyDrowsyToVPS();
void testVPSConnection();
void printDebugInfo();
void printStatistics();

// ================== DEBUG FUNCTIONS ==================
void debugPrint(String message) {
    if (DEBUG_SERIAL) Serial.print(message);
}

void debugPrintln(String message) {
    if (DEBUG_SERIAL) Serial.println(message);
}

void debugPrintf(const char* format, ...) {
    if (DEBUG_SERIAL) {
        char buffer[256];
        va_list args;
        va_start(args, format);
        vsnprintf(buffer, sizeof(buffer), format, args);
        va_end(args);
        Serial.print(buffer);
    }
}

// ================== SETUP ==================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    pinMode(LED_FLASH, OUTPUT);
    digitalWrite(LED_FLASH, LOW);
    
    debugPrintln("\n");
    debugPrintln("==================================================");
    debugPrintln("🚀 ESP32-CAM DROWSINESS DETECTION SYSTEM");
    debugPrintln("==================================================");
    debugPrintf("Firmware Version: 1.1.0 (Fixed Stream)\n");
    debugPrintf("Build Date: %s %s\n", __DATE__, __TIME__);
    debugPrintln("==================================================");
    
    // Generate unique ID based on MAC address
    esp32Id = "ESP32-CAM-" + String((uint32_t)ESP.getEfuseMac(), HEX).substring(0, 6);
    debugPrintf("Device ID: %s\n", esp32Id.c_str());
    debugPrintf("Chip ID: %08X\n", ESP.getEfuseMac());
    debugPrintf("Free Heap: %d bytes\n", ESP.getFreeHeap());
    
    // Connect to WiFi
    connectWiFi();
    
    // Initialize camera
    debugPrintln("\n📷 Initializing camera...");
    esp_err_t camStatus = esp_camera_init(&camera_config);
    if (camStatus != ESP_OK) {
        debugPrintf("❌ Camera initialization failed with error: 0x%x\n", camStatus);
        debugPrintln("Possible causes:");
        debugPrintln("1. Wrong pin configuration");
        debugPrintln("2. Insufficient power");
        debugPrintln("3. Hardware issue");
        while (true) {
            delay(1000);
            digitalWrite(LED_FLASH, !digitalRead(LED_FLASH));
        }
    }
    
    sensor_t *sensor = esp_camera_sensor_get();
    debugPrintf("✅ Camera initialized successfully\n");
    debugPrintf("   Resolution: %dx%d\n", 
                sensor->status.framesize == FRAMESIZE_VGA ? 640 : 0,
                sensor->status.framesize == FRAMESIZE_VGA ? 480 : 0);
    debugPrintf("   Quality: %d\n", sensor->status.quality);
    
    // Setup local web server routes
    debugPrintln("\n🌐 Setting up local web server...");
    localServer.on("/", HTTP_GET, handleRoot);
    localServer.on("/status", HTTP_GET, handleStatus);
    localServer.on("/capture", HTTP_GET, handleCapture);
    localServer.on("/led", HTTP_GET, handleLED);
    localServer.on("/restart", HTTP_GET, handleRestart);
    localServer.on("/stream_toggle", HTTP_GET, handleStreamToggle);
    localServer.on("/test_vps", HTTP_GET, handleTestVPS);
    localServer.on("/debug", HTTP_GET, handleDebug);
    localServer.on("/stats", HTTP_GET, handleStats);
    
    localServer.begin();
    debugPrintf("✅ Local web server started\n");
    debugPrintf("   Local URL: http://%s\n", WiFi.localIP().toString().c_str());
    debugPrintf("   VPS URL: %s\n", getVpsUrl().c_str());
    
    // Test VPS connection
    debugPrintln("\n🔗 Testing VPS connection...");
    testVPSConnection();
    
    // Print initial debug info
    printDebugInfo();
    
    debugPrintln("\n✅ System initialization complete!");
    debugPrintln("==================================================");
}

// ================== MAIN LOOP ==================
void loop() {
    localServer.handleClient();
    
    unsigned long currentMillis = millis();
    
    // Send frame to VPS for streaming
    if (isStreaming && (currentMillis - lastStreamFrame >= STREAM_INTERVAL)) {
        if (DEBUG_STREAM) debugPrint("📤 ");
        sendFrameToVPS();
        lastStreamFrame = currentMillis;
    }
    
    // Send detection to VPS
    if (currentMillis - lastDetection >= DETECTION_INTERVAL) {
        if (DEBUG_DETECTION) debugPrint("🔍 ");
        sendDetectionToVPS();
        lastDetection = currentMillis;
    }
    
    // Print periodic status update
    if (currentMillis - lastStatusUpdate >= STATUS_INTERVAL) {
        printStatistics();
        lastStatusUpdate = currentMillis;
    }
}

// ================== VPS FUNCTIONS ==================

// [PERBAIKAN UTAMA] Fungsi ini ditulis ulang total pakai WiFiClient langsung
void sendFrameToVPS() {
    unsigned long startTime = millis();
    camera_fb_t *fb = esp_camera_fb_get();
    
    if (!fb) {
        if (DEBUG_STREAM) debugPrintln("❌ Failed to capture frame for streaming");
        streamErrors++;
        return;
    }
    
    if (fb->len > 0) {
        // Gunakan WiFiClient murni untuk kontrol socket yang lebih baik
        WiFiClient client;
        
        if (!client.connect(serverHost, serverPort)) {
            if (DEBUG_STREAM) debugPrintln("❌ Connection to VPS failed");
            streamErrors++;
            esp_camera_fb_return(fb);
            return;
        }

        String path = String(streamPushEndpoint) + esp32Id;
        String boundary = "ESP32CAM" + String(millis());
        
        String head = "--" + boundary + "\r\n";
        head += "Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n";
        head += "Content-Type: image/jpeg\r\n\r\n";
        String tail = "\r\n--" + boundary + "--\r\n";

        uint32_t imageLen = fb->len;
        uint32_t extraLen = head.length() + tail.length();
        uint32_t totalLen = imageLen + extraLen;

        // Manual HTTP POST Request
        client.print("POST " + path + " HTTP/1.1\r\n");
        client.print("Host: " + String(serverHost) + ":" + String(serverPort) + "\r\n");
        client.print("Connection: close\r\n");
        client.print("Content-Type: multipart/form-data; boundary=" + boundary + "\r\n");
        client.print("Content-Length: " + String(totalLen) + "\r\n");
        client.print("\r\n"); // End of headers
        
        // Kirim Body
        client.print(head);
        
        // Kirim Gambar (Chunking untuk stabilitas jika perlu, tapi write langsung biasanya oke)
        // Kita kirim dalam buffer chunks kecil jika gambar besar, tapi write buffer esp32 biasanya handle ini.
        client.write(fb->buf, fb->len);
        
        client.print(tail);

        // Baca Response (Optional, timeout pendek biar gak blocking streaming)
        unsigned long timeout = millis();
        while (client.connected() && millis() - timeout < 2000) {
            if (client.available()) {
                String line = client.readStringUntil('\n');
                if (line.indexOf("200 OK") != -1 || line.indexOf("frame_received") != -1) {
                    // Sukses
                    streamFrameCount++;
                    streamBytesSent += fb->len;
                    if (DEBUG_STREAM) debugPrintln("✅ OK");
                }
                break; // Gak perlu baca semua body, hemat waktu
            }
        }
        
        client.stop();

    } else {
        if (DEBUG_STREAM) debugPrintln("❌ Empty frame captured");
        streamErrors++;
    }
    
    esp_camera_fb_return(fb);
}

void sendDetectionToVPS() {
    unsigned long startTime = millis();
    camera_fb_t *fb = esp_camera_fb_get();
    
    if (!fb) {
        if (DEBUG_DETECTION) debugPrintln("❌ Failed to capture frame for detection");
        detectionErrors++;
        return;
    }
    
    if (DEBUG_DETECTION) debugPrintf("Sending detection #%lu (%d bytes)...\n", 
                                    detectionCount + 1, fb->len);
    
    // Convert to base64
    String imageBase64 = base64::encode(fb->buf, fb->len);
    
    // Create JSON
    DynamicJsonDocument doc(120000); // Buffer digedein dikit
    doc["esp32_id"] = esp32Id;
    doc["image"] = imageBase64;
    
    String body;
    serializeJson(doc, body);
    
    if (DEBUG_DETECTION) debugPrintf("JSON size: %d bytes\n", body.length());
    
    // Send HTTP POST to detection endpoint
    HTTPClient http;
    WiFiClientSecure clientSecure;
    
    String url = getVpsUrl() + String(detectEndpoint);
    
    // Logic HTTPS vs HTTP (Sekarang pakai HTTP dari config)
    http.begin(url); // Langsung begin karena pakai HTTP
    
    http.setTimeout(15000);
    http.addHeader("Content-Type", "application/json");
    
    int code = http.POST(body);
    unsigned long endTime = millis();
    
    if (code <= 0) {
        detectionErrors++;
        if (DEBUG_DETECTION) {
            debugPrintf("❌ HTTP error: %s (code: %d)\n", 
                       http.errorToString(code).c_str(), code);
        }
        http.end();
        esp_camera_fb_return(fb);
        return;
    }
    
    String response = http.getString();
    http.end();
    
    if (DEBUG_DETECTION) {
        debugPrintf("✅ Detection sent in %lu ms, HTTP code: %d\n", 
                   endTime - startTime, code);
    }
    
    // Parse response
    DynamicJsonDocument resDoc(512);
    DeserializationError err = deserializeJson(resDoc, response);
    
    if (err) {
        if (DEBUG_DETECTION) {
            debugPrintf("❌ JSON parse error: %s\n", err.c_str());
            // debugPrintf("   Response: %s\n", response.c_str()); // Uncomment kalau mau liat raw response
        }
    } else {
        bool newIsDrowsy = resDoc["is_drowsy"];
        ear = resDoc["ear"];
        mar = resDoc["mar"];
        headTilt = resDoc["head_tilt"];
        
        detectionCount++;
        
        // Check if drowsiness status changed
        if (newIsDrowsy != isDrowsy) {
            isDrowsy = newIsDrowsy;
            
            // Notify VPS about drowsiness status change
            if (isDrowsy) {
                notifyDrowsyToVPS();
                if (DEBUG_DETECTION) debugPrintln("🚨 DROWSINESS DETECTED! Alert sent to VPS!");
                
                // Flash LED pattern for drowsy
                for (int i = 0; i < 5; i++) {
                    digitalWrite(LED_FLASH, HIGH);
                    delay(200);
                    digitalWrite(LED_FLASH, LOW);
                    delay(200);
                }
            } else {
                if (DEBUG_DETECTION) debugPrintln("✅ Driver is AWAKE");
                digitalWrite(LED_FLASH, LOW);
            }
        }
        
        if (DEBUG_DETECTION) {
            // Cek ada nama driver gak
            String driverName = resDoc["driver"] | "Unknown";
            debugPrintf("📊 Driver: %s | Status: %s | EAR: %.2f | MAR: %.2f\n",
                      driverName.c_str(),
                      isDrowsy ? "DROWSY" : "AWAKE", 
                      ear, mar);
        }
    }
    
    esp_camera_fb_return(fb);
}

void notifyDrowsyToVPS() {
    HTTPClient http;
    String url = getVpsUrl() + String(notifyDrowsyEndpoint) + esp32Id;
    
    if (DEBUG_DETECTION) debugPrintf("Notifying drowsy status to: %s\n", url.c_str());
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    DynamicJsonDocument doc(200);
    doc["is_drowsy"] = isDrowsy;
    doc["ear"] = ear;
    doc["mar"] = mar;
    doc["head_tilt"] = headTilt;
    doc["timestamp"] = millis();
    doc["esp32_id"] = esp32Id;
    
    String body;
    serializeJson(doc, body);
    
    int code = http.POST(body);
    
    if (code == 200) {
        if (DEBUG_DETECTION) debugPrintln("📢 Drowsy notification sent to VPS");
    } else {
        if (DEBUG_DETECTION) debugPrintf("❌ Failed to notify VPS: %d\n", code);
    }
    
    http.end();
}

void testVPSConnection() {
    debugPrintln("Testing VPS connection...");
    
    HTTPClient http;
    String url = getVpsUrl() + "/";
    http.begin(url);
    
    http.setTimeout(5000);
    
    int code = http.GET();
    
    if (code > 0) {
        debugPrintf("✅ VPS connection successful! HTTP code: %d\n", code);
    } else {
        debugPrintf("❌ VPS connection failed: %d - %s\n", 
                    code, http.errorToString(code).c_str());
        debugPrintln("Possible issues: Wrong IP, Port Blocked, Server Down.");
    }
    
    http.end();
}

// ================== DEBUG & STATISTICS ==================
void printDebugInfo() {
    debugPrintln("\n📊 SYSTEM INFORMATION:");
    debugPrintf("   ESP32 ID: %s\n", esp32Id.c_str());
    debugPrintf("   WiFi SSID: %s\n", ssid);
    debugPrintf("   WiFi Status: %s\n", WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected");
    debugPrintf("   IP Address: %s\n", WiFi.localIP().toString().c_str());
    debugPrintf("   RSSI: %d dBm\n", WiFi.RSSI());
    debugPrintf("   Free Heap: %d bytes\n", ESP.getFreeHeap());
    debugPrintf("   VPS URL: %s\n", getVpsUrl().c_str());
    debugPrintf("   Streaming: %s\n", isStreaming ? "ACTIVE" : "PAUSED");
    debugPrintf("   Stream FPS: %.1f\n", 1000.0 / STREAM_INTERVAL);
    debugPrintf("   Detection Interval: %lu ms\n", DETECTION_INTERVAL);
}

void printStatistics() {
    debugPrintln("\n📈 SYSTEM STATISTICS:");
    debugPrintf("   Uptime: %lu seconds\n", millis() / 1000);
    debugPrintf("   Stream Frames Sent: %lu\n", streamFrameCount);
    debugPrintf("   Total Bytes Sent: %lu (%.2f MB)\n", 
                streamBytesSent, streamBytesSent / 1024.0 / 1024.0);
    debugPrintf("   Stream Errors: %lu\n", streamErrors);
    debugPrintf("   Detections Sent: %lu\n", detectionCount);
    debugPrintf("   Detection Errors: %lu\n", detectionErrors);
    debugPrintf("   Current Drowsy Status: %s\n", isDrowsy ? "DROWSY" : "AWAKE");
    debugPrintf("   Free Heap: %d bytes\n", ESP.getFreeHeap());
    debugPrintf("   WiFi RSSI: %d dBm\n", WiFi.RSSI());
    
    // Calculate throughput
    if (millis() > 0) {
        float kbps = (streamBytesSent * 8.0) / (millis() / 1000.0) / 1024.0;
        debugPrintf("   Average Throughput: %.2f kbps\n", kbps);
    }
}

// ================== LOCAL SERVER HANDLERS ==================
void handleRoot() {
    String html = "<!DOCTYPE html><html><head><title>ESP32-CAM Control</title>";
    html += "<meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<style>";
    html += "body{font-family:Arial,sans-serif;background:#1a1a1a;color:white;margin:20px;}";
    html += ".container{max-width:800px;margin:0 auto;}";
    html += ".header{background:#667eea;padding:20px;border-radius:10px;text-align:center;}";
    html += ".stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin:20px 0;}";
    html += ".stat-box{background:#2d2d2d;padding:15px;border-radius:8px;text-align:center;}";
    html += "button{background:#667eea;color:white;border:none;padding:12px 20px;border-radius:5px;cursor:pointer;margin:5px;}";
    html += ".status-indicator{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;}";
    html += ".green{background:#48bb78;}.red{background:#f56565;}.orange{background:#ed8936;}";
    html += "</style></head><body>";
    html += "<div class='container'>";
    html += "<div class='header'><h1>ESP32-CAM Control Panel</h1>";
    html += "<p>ID: " + esp32Id + " | IP: " + WiFi.localIP().toString() + "</p>";
    html += "<p>VPS: " + getVpsUrl() + "</p></div>";
    
    html += "<div class='stat-grid'>";
    html += "<div class='stat-box'><h3>Drowsy Status</h3><div style='font-size:24px;font-weight:bold;color:" + String(isDrowsy ? "#f56565" : "#48bb78") + "'>" + String(isDrowsy ? "YES" : "NO") + "</div></div>";
    html += "<div class='stat-box'><h3>EAR</h3><div style='font-size:24px;font-weight:bold;'>" + String(ear, 2) + "</div><small>Eye Aspect Ratio</small></div>";
    html += "<div class='stat-box'><h3>MAR</h3><div style='font-size:24px;font-weight:bold;'>" + String(mar, 2) + "</div><small>Mouth Aspect Ratio</small></div>";
    html += "<div class='stat-box'><h3>Head Tilt</h3><div style='font-size:24px;font-weight:bold;'>" + String(headTilt, 1) + "°</div></div>";
    html += "</div>";
    
    html += "<div style='background:#2d2d2d;padding:20px;border-radius:10px;margin:20px 0;'>";
    html += "<h3>Connection Status</h3>";
    html += "<p>WiFi: <span class='status-indicator " + String(WiFi.status() == WL_CONNECTED ? "green" : "red") + "'></span>" + String(WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected") + " (" + String(WiFi.RSSI()) + " dBm)</p>";
    html += "<p>Streaming: <span class='status-indicator " + String(isStreaming ? "green" : "orange") + "'></span>" + String(isStreaming ? "ACTIVE" : "PAUSED") + "</p>";
    html += "<p>Frames Sent: " + String(streamFrameCount) + " | Detections: " + String(detectionCount) + "</p>";
    html += "</div>";
    
    html += "<div style='text-align:center;margin:20px 0;'>";
    html += "<button onclick=\"fetch('/stream_toggle')\">" + String(isStreaming ? "⏸️ Pause Stream" : "▶️ Resume Stream") + "</button>";
    html += "<button onclick=\"fetch('/capture')\">📸 Capture & Detect</button>";
    html += "<button onclick=\"fetch('/led')\">💡 Toggle Flash</button>";
    html += "<button onclick=\"fetch('/test_vps')\">📡 Test VPS</button>";
    html += "<button onclick=\"fetch('/debug')\">🐛 Debug Info</button>";
    html += "<button onclick=\"fetch('/stats')\">📊 Statistics</button>";
    html += "<button onclick=\"fetch('/restart')\">🔄 Restart</button>";
    html += "<button onclick=\"location.reload()\">🔄 Refresh</button>";
    html += "</div>";
    
    html += "<div style='background:#2d2d2d;padding:20px;border-radius:10px;'>";
    html += "<h3>System Information</h3>";
    html += "<p><strong>Uptime:</strong> " + String(millis() / 1000) + " seconds</p>";
    html += "<p><strong>Free Heap:</strong> " + String(ESP.getFreeHeap()) + " bytes</p>";
    html += "<p><strong>Stream FPS:</strong> " + String(1000.0 / STREAM_INTERVAL, 1) + "</p>";
    html += "<p><strong>Detection Interval:</strong> " + String(DETECTION_INTERVAL / 1000.0, 1) + " seconds</p>";
    html += "</div>";
    
    html += "</div>";
    html += "<script>";
    html += "async function updateStatus(){";
    html += "try{const r=await fetch('/status');const d=await r.json();";
    html += "document.querySelectorAll('.stat-box')[0].querySelector('div').textContent=d.isDrowsy?'YES':'NO';";
    html += "document.querySelectorAll('.stat-box')[0].querySelector('div').style.color=d.isDrowsy?'#f56565':'#48bb78';";
    html += "document.querySelectorAll('.stat-box')[1].querySelector('div').textContent=d.ear.toFixed(2);";
    html += "document.querySelectorAll('.stat-box')[2].querySelector('div').textContent=d.mar.toFixed(2);";
    html += "document.querySelectorAll('.stat-box')[3].querySelector('div').textContent=d.headTilt.toFixed(1)+'°';";
    html += "}catch(e){console.error(e);}}";
    html += "setInterval(updateStatus,2000);";
    html += "</script>";
    html += "</body></html>";
    
    localServer.send(200, "text/html", html);
}

void handleStatus() {
    DynamicJsonDocument doc(512);
    doc["isDrowsy"] = isDrowsy;
    doc["ear"] = ear;
    doc["mar"] = mar;
    doc["headTilt"] = headTilt;
    doc["esp32_id"] = esp32Id;
    doc["uptime"] = millis() / 1000;
    doc["isStreaming"] = isStreaming;
    doc["freeHeap"] = ESP.getFreeHeap();
    doc["wifiRSSI"] = WiFi.RSSI();
    doc["streamFrameCount"] = streamFrameCount;
    doc["detectionCount"] = detectionCount;
    doc["streamErrors"] = streamErrors;
    doc["detectionErrors"] = detectionErrors;
    doc["ipAddress"] = WiFi.localIP().toString();
    
    String response;
    serializeJson(doc, response);
    localServer.send(200, "application/json", response);
}

void handleCapture() {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) {
        sendDetectionToVPS();
        esp_camera_fb_return(fb);
        localServer.send(200, "text/plain", "Photo captured and sent to VPS for detection");
    } else {
        localServer.send(500, "text/plain", "Failed to capture photo");
    }
}

void handleLED() {
    static bool ledState = false;
    ledState = !ledState;
    digitalWrite(LED_FLASH, ledState);
    localServer.send(200, "text/plain", ledState ? "LED ON" : "LED OFF");
}

void handleRestart() {
    localServer.send(200, "text/plain", "Restarting ESP32...");
    delay(1000);
    ESP.restart();
}

void handleStreamToggle() {
    isStreaming = !isStreaming;
    localServer.send(200, "text/plain", isStreaming ? "Streaming RESUMED" : "Streaming PAUSED");
    debugPrintln(isStreaming ? "▶️ Streaming resumed" : "⏸️ Streaming paused");
}

void handleTestVPS() {
    testVPSConnection();
    localServer.send(200, "text/plain", "VPS test completed - check Serial Monitor");
}

void handleDebug() {
    String debugInfo = "=== ESP32-CAM DEBUG INFO ===\n\n";
    debugInfo += "Device ID: " + esp32Id + "\n";
    debugInfo += "IP Address: " + WiFi.localIP().toString() + "\n";
    debugInfo += "WiFi SSID: " + String(ssid) + "\n";
    debugInfo += "WiFi RSSI: " + String(WiFi.RSSI()) + " dBm\n";
    debugInfo += "VPS URL: " + getVpsUrl() + "\n";
    debugInfo += "Streaming: " + String(isStreaming ? "ACTIVE" : "PAUSED") + "\n";
    debugInfo += "Drowsy Status: " + String(isDrowsy ? "DROWSY" : "AWAKE") + "\n";
    debugInfo += "EAR: " + String(ear, 2) + " | MAR: " + String(mar, 2) + " | Tilt: " + String(headTilt, 1) + "°\n";
    debugInfo += "Free Heap: " + String(ESP.getFreeHeap()) + " bytes\n";
    debugInfo += "Uptime: " + String(millis() / 1000) + " seconds\n";
    debugInfo += "\n=== STATISTICS ===\n";
    debugInfo += "Stream Frames Sent: " + String(streamFrameCount) + "\n";
    debugInfo += "Total Bytes Sent: " + String(streamBytesSent) + " (" + String(streamBytesSent / 1024.0 / 1024.0, 2) + " MB)\n";
    debugInfo += "Stream Errors: " + String(streamErrors) + "\n";
    debugInfo += "Detections Sent: " + String(detectionCount) + "\n";
    debugInfo += "Detection Errors: " + String(detectionErrors) + "\n";
    
    localServer.send(200, "text/plain", debugInfo);
}

void handleStats() {
    DynamicJsonDocument doc(512);
    doc["streamFrameCount"] = streamFrameCount;
    doc["streamBytesSent"] = streamBytesSent;
    doc["streamErrors"] = streamErrors;
    doc["detectionCount"] = detectionCount;
    doc["detectionErrors"] = detectionErrors;
    doc["isStreaming"] = isStreaming;
    doc["isDrowsy"] = isDrowsy;
    doc["uptime"] = millis() / 1000;
    doc["freeHeap"] = ESP.getFreeHeap();
    doc["wifiRSSI"] = WiFi.RSSI();
    
    String response;
    serializeJson(doc, response);
    localServer.send(200, "application/json", response);
}

// ================== WIFI CONNECTION ==================
void connectWiFi() {
    if (DEBUG_WIFI) debugPrintf("Connecting to WiFi: %s\n", ssid);
    
    WiFi.begin(ssid, password);
    
    unsigned long startTime = millis();
    int attempts = 0;
    
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        if (DEBUG_WIFI) debugPrint(".");
        attempts++;
        
        // Timeout after 15 seconds
        if (millis() - startTime > 15000) {
            if (DEBUG_WIFI) debugPrintln("\n❌ WiFi connection timeout!");
            break;
        }
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        if (DEBUG_WIFI) {
            debugPrintln("\n✅ WiFi connected!");
            debugPrintf("   IP Address: %s\n", WiFi.localIP().toString().c_str());
            debugPrintf("   MAC Address: %s\n", WiFi.macAddress().c_str());
            debugPrintf("   Signal Strength: %d dBm\n", WiFi.RSSI());
        }
    } else {
        if (DEBUG_WIFI) {
            debugPrintln("\n❌ WiFi connection failed!");
            debugPrintln("📡 Starting Access Point mode...");
        }
        
        // Start AP mode if can't connect
        WiFi.softAP("ESP32-CAM-Driver", "driver123");
        
        if (DEBUG_WIFI) {
            debugPrintf("   AP SSID: ESP32-CAM-Driver\n");
            debugPrintf("   AP Password: driver123\n");
            debugPrintf("   AP IP: %s\n", WiFi.softAPIP().toString().c_str());
        }
    }
}