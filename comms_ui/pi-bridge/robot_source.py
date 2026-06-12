import math
import random
import time

def get_fake_telemetry():
    t = time.time()
    """
    return {
        "time_ms": int(t * 1000),
        "angle_deg": round(8 * math.sin(t), 2),
        "gyro_dps": round(8 * math.cos(t), 2),
        "motor_left": int(120 + random.uniform(-15, 15)),
        "motor_right": int(120 + random.uniform(-15, 15)),
        "battery_v": round(7.6 + random.uniform(-0.05, 0.05), 2),
        "mode": "SIM",
        "package_dropped": random.random() < 0.02
    }
"""
    return {
        "time_ms": 1,
        "angle_deg": 1,
        "gyro_dps": 1,
        "motor_left": 1,
        "motor_right": 1,
        "battery_v": 1,
        "mode": "SIM",
        "package_dropped": 0
    }
