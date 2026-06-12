import threading
import time
import cv2
import numpy as np
from serial_link import send_serial_command

class RobotController:
    def __init__(self, camera):
        self.camera = camera
        self.autonomy_mode = "manual"
        self.running = False
        self.thread = None
        self.FRAME_CENTER_X = 160 #320
        self.speed = 5
        self.kp = 1
        self.kd = 0.0
        self.previous_error = 0
        self.last_path_direction = 0
        self.lost_frames = 0
        self.LINE_LOST_THRESHOLD = 2
        self.FAR_ROI_Y1 = 80
        self.FAR_ROI_Y2 = 150
        self.NEAR_ROI_Y1 = 150
        self.NEAR_ROI_Y2 = 240
        self.obstacle_report_pending = False
        self.qr_detector = cv2.QRCodeDetector()
        self.approach_started = False
        self.approach_start_time = None
        self.last_qr_data = None
        self.obstacle_report_pending = False
        self.control_generation = 0
        self.mode_lock = threading.Lock()
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict)
        self.marker_counter = 0
        self.last_marker_id = None
        self.last_marker_time = 0
        self.marker_detected = False
        self.obstacle_mode = "NONE"

    def start(self):
        self.running = True
        send_serial_command("MODE:MANUAL")
        send_serial_command("L:0 R:0")
        self.thread = threading.Thread(target=self.control_loop)
        self.thread.start()

    def set_mode(self, mode):
        with self.mode_lock:
            print(f"Switchinng mode to: {mode}")
            self.autonomy_mode = mode
            self.control_generation += 1
        self.previous_error = 0

        if mode == "manual":
            send_serial_command("L:0 R:0")
            self.obstacle_mode = "NONE"

    def manual_command(self, command):
        if self.autonomy_mode != "manual":
            return
        
        if (command == "FORWARD"):
            send_serial_command(f"L:{self.speed} R:{self.speed}")
        elif (command == "BACKWARD"):
            send_serial_command(f"L:-{self.speed} R:-{self.speed}")
        elif (command == "RIGHT"):
            send_serial_command(f"L:{self.speed} R:-{self.speed}")  
        elif (command == "LEFT"):
            send_serial_command(f"L:-{self.speed} R:{self.speed}")
        elif (command == "STOP"):
            send_serial_command("L:0 R:0")

    def update_obstacle(self, value):
        if value == 1:
            self.obstacle_mode = "OBSTACLE_APPROACH"
        elif value == 0:
            self.obstacle_mode = "NONE"

    def control_loop(self):
        while self.running:
            if self.autonomy_mode == "line_follow":

                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                if self.obstacle_mode == "NONE":
                    self.marker_counter += 1
                    if self.marker_counter % 5 == 0:
                        self.detect_markers(frame)
                    if not self.marker_detected:
                        self.run_line_following(frame)
                    else:
                        self.interpret_marker(frame)
                elif self.obstacle_mode == "OBSTACLE_APPROACH":
                    self.approach_obstacle(frame)
                elif self.obstacle_mode == "OBSTACLE_AVOID":
                    time.sleep(0.01)
                    continue
            time.sleep(0.01)
    
    def run_line_following(self, frame):
        my_generation = self.control_generation
        
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        output = frame.copy()

        far_roi = thresh[self.FAR_ROI_Y1:self.FAR_ROI_Y2,:]
        near_roi = thresh[self.NEAR_ROI_Y1:self.NEAR_ROI_Y2,:]
        far_contours, _ = cv2.findContours(far_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        near_contours, _ = cv2.findContours(near_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        near_detected = False
        near_error = 0
        far_error = 0

        if len(far_contours) > 0:
            far_largest = max(far_contours, key=cv2.contourArea)
            if cv2.contourArea(far_largest) > 200:

                far_shifted = far_largest.copy()
                far_shifted[:,:,1] += self.FAR_ROI_Y1
                cv2.drawContours(output, [far_shifted], -1, (255, 0, 0), 2)

                M = cv2.moments(far_largest)
                if M["m00"] != 0:
                    far_cx = int(M['m10']/M['m00'])
                    far_cy = int(M['m01']/M['m00']) + self.FAR_ROI_Y1

                    far_error = (far_cx - self.FRAME_CENTER_X) / self.FRAME_CENTER_X

                    cv2.circle(output, (far_cx,far_cy), 8, (255, 0, 255), -1)

                    if far_error < -0.1:
                        self.last_path_direction = -1
                    elif far_error > 0.1:
                        self.last_path_direction = 1
        
        if len(near_contours) > 0:
            near_largest = max(near_contours, key=cv2.contourArea)

            if cv2.contourArea(near_largest) > 500:
                near_detected = True

                near_shifted = near_largest.copy()
                near_shifted[:,:,1] += self.NEAR_ROI_Y1
                cv2.drawContours(output, [near_shifted], -1, (0, 255, 0), 2)

                M = cv2.moments(near_largest)
                if M["m00"] != 0:
                    near_cx = int(M['m10']/M['m00'])
                    near_cy = int(M['m01']/M['m00']) + self.NEAR_ROI_Y1

                    near_error = (near_cx - self.FRAME_CENTER_X) / self.FRAME_CENTER_X

                    cv2.circle(output, (near_cx,near_cy), 8, (0, 0, 255), -1)

        line_detected = near_detected

        if near_detected:
            combined_error = (0.6*near_error) + (0.4*far_error)
            derivative = combined_error - self.previous_error
            self.previous_error = combined_error

            turn = (self.kp*combined_error) + (self.kd*derivative)
            left_speed = self.speed + turn
            right_speed = self.speed - turn
            left_speed = max(-5, min(5, left_speed))
            right_speed = max(-5, min(5, right_speed))
            if my_generation != self.control_generation:
                return
            send_serial_command(f"L:{left_speed:.2f} R:{right_speed:.2f}")

        if not line_detected:
            self.lost_frames += 1
        else:
            self.lost_frames = 0

        if self.lost_frames > self.LINE_LOST_THRESHOLD:

            if self.last_path_direction > 0:
                left = self.speed
                right = -self.speed
            else:
                left = -self.speed
                right = self.speed

            left = max(-5, min(5, left))
            right = max(-5, min(5, right))

            if my_generation != self.control_generation:
                return

            send_serial_command(f"L:{left:.2f} R:{right:.2f}")

            cv2.putText(
                output,
                "RECOVERY MODE",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        cv2.rectangle(
            output,
            (0, self.FAR_ROI_Y1),
            (320, self.FAR_ROI_Y2),
            (255, 255, 0),
            2
        )

        cv2.rectangle(
            output,
            (0, self.NEAR_ROI_Y1),
            (320, self.NEAR_ROI_Y2),
            (255, 0, 0),
            2
        )

        cv2.putText(
            output,
            f"Path Dir: {self.last_path_direction}",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        self.camera.set_debug_frame(output)
    
    def approach_obstacle(self, frame):
        if not self.approach_started:
            self.approach_started = True
            self.approach_start_time = time.time()
            self.obstacle_report_pending = True
            send_serial_command("MODE:OBSTACLE_APPROACH")
            send_serial_command("L:0.5 R:0.5")

        output = frame.copy()

        cv2.putText(
            output,
            "APPROACHING QR",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2
        )

        data, bbox, _ = self.qr_detector.detectAndDecode(frame)

        if bbox is not None:
            bbox = bbox.astype(int)

            # Draw box around QR code
            for i in range(len(bbox[0])):
                pt1 = tuple(bbox[0][i])
                pt2 = tuple(bbox[0][(i + 1) % len(bbox[0])])

                cv2.line(output, pt1, pt2, (0, 255, 0), 2)

            # Print detected data
            if data:
                send_serial_command("L:0 R:0")
                self.last_qr_data = data
                self.approach_started = False
                send_serial_command(f"MODE:OBSTACLE_AVOID")
                self.obstacle_mode = "OBSTACLE_AVOID"
                cv2.putText(
                    output,
                    data,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                self.camera.set_debug_frame(output)
                return

        if time.time() - self.approach_start_time > 60:
            self.last_qr_data = "UNKNOWN"
            send_serial_command(f"MODE:OBSTACLE_AVOID")
            self.obstacle_mode = "OBSTACLE_AVOID"
            self.approach_started = False
    
        self.camera.set_debug_frame(output)

    def detect_markers(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        corners, ids, _ = self.aruco_detector.detectMarkers(gray)
        if ids is None:
            self.marker_detected = False
            self.last_marker_id = None
        else:
            self.marker_detected = True
            send_serial_command("L:0 R:0")
            self.last_marker_id = int(ids[0][0])
    
    def interpret_marker(self,frame):
        if self.last_marker_id is None:
            return
        if not self.obstacle_report_pending:
            self.marker_detected = False
            return

        if 0<= self.last_marker_id < 15:
            self.aquire_deviation(frame)
        elif self.last_marker_id == 15:
            send_serial_command("L:0 R:0")
            send_serial_command("MODE:DEVIATION_RETURN")
    
    def aquire_deviation(self, frame):        
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.erode(thresh, kernel, iterations=1)
        thresh = cv2.dilate(thresh, kernel, iterations=2)

        roi = thresh[self.ROI_Y:240,:]

        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        output = frame.copy()

        line_detected = False

        send_serial_command(f"L:{self.speed} R:{-self.speed}")

        if len(contours) > 0:
            largest = max(contours, key=cv2.contourArea)

            if cv2.contourArea(largest) > 500:
                self.marker_detected = False

        if not line_detected:
            self.lost_frames += 1
        else:
            self.lost_frames = 0

        if self.lost_frames > self.LINE_LOST_THRESHOLD:

            left = self.speed
            right = -self.speed

            left = max(-5, min(5, left))
            right = max(-5, min(5, right))

            send_serial_command(f"L:{left:.2f} R:{right:.2f}")

            cv2.putText(
                output,
                "DEVIATION RECOVERY",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        self.camera.set_debug_frame(output)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        send_serial_command("L:0 R:0")

    def update_tuning(self, name, value):
        print(f"Tuning update: {name} = {value}")

        if name == "speed":
            self.speed = value

        elif name == "auto_kp":
            self.kp = value

        elif name == "auto_kd":
            self.kd = value

        elif name == "auto_ki":
            self.ki = value

        elif name in ["speed_kp", "speed_kd", "speed_ki", "balance_kp", "balance_kd"]:
            print(f"Sending {name} -> {value}")
            send_serial_command(f"TUNE:{name.upper()}:{value}")

        else:
            print(f"Unknown tuning parameter: {name}")