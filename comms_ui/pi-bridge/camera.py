try:
    from picamera2 import Picamera2
    PI_CAMERA_AVAILABLE = True
except ImportError:
    Picamera2 = None
    PI_CAMERA_AVAILABLE = False
import threading
import time

class Camera:
    def __init__(self):
        self.picam2 = None
        self.latest_frame = None
        self.latest_debug_frame = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        if not PI_CAMERA_AVAILABLE:
            print("Camera disabled: picamera2 not available on this machine")
            return

        self.picam2 = Picamera2()

        config = self.picam2.create_video_configuration()
        config["sensor_mode"] = {"size": (1640, 1232)}
        config["main"] = {"size": (320, 240), "format": "RGB888"}
        config["buffer_count"] = 3
        self.picam2.configure(config)

    def start(self):
        if self.picam2 is None:
            print("Camera start skipped: no camera available")
            return

        self.picam2.start()
        self.running = True

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            frame = self.picam2.capture_array()

            with self.lock:
                self.latest_frame = frame
                
            time.sleep(0.01)

    def get_frame(self):
        with self.lock:
            return self.latest_frame

    def get_debug_frame(self):
        with self.lock:
            return self.latest_debug_frame
    
    def set_debug_frame(self, frame):
        with self.lock:
            self.latest_debug_frame = frame

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

        if self.picam2 is not None:
            self.picam2.stop()
            self.picam2.close()