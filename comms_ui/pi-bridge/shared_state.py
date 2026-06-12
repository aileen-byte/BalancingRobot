import asyncio

latest_telemetry = {
    "time_ms": 0,
    "angle_deg": 0.0,
    "gyro_dps": 0.0,
    "motor_left": 0,
    "motor_right": 0,
    "battery_v": 0.0,
    "mode": "WAITING"
}

command_queue = asyncio.Queue()