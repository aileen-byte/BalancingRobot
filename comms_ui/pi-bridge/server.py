import asyncio
from unicodedata import name
import cv2
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from serial_link import connect_serial, set_obstacle_callback, send_serial_command, start_serial, stop_serial
from robot_source import get_fake_telemetry
from camera import Camera
from robot_controller import RobotController

camera = Camera()
robot = RobotController(camera)
app = FastAPI()

@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.on_event("startup")
async def startup_event():
    connect_serial()
    start_serial()
    camera.start()
    robot.start()
    set_obstacle_callback(robot.update_obstacle)

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web-ui"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send_telemetry():
        while True:
            data = get_fake_telemetry()
            await websocket.send_json(data)
            await asyncio.sleep(0.05)

    async def receive_commands():
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "command":
                command = message.get("command")
                robot.manual_command(command)
            elif message_type == "mode":
                mode = message.get("mode")
                robot.set_mode(mode)
                send_serial_command(f"MODE:{mode.upper()}")
            elif message_type == "tuning":
                values = message.get("values", {})
                for name, value in values.items():
                    robot.update_tuning(name, float(value))

    try:
        await asyncio.gather(
            send_telemetry(),
            receive_commands()
        )
    except Exception:
        print("WebSocket disconnected")

async def mjpeg_generator():
    while True:
        if robot.autonomy_mode == "manual" or robot.obstacle_mode == "OBSTACLE_AVOID":
            frame = camera.get_frame()
        else:
            frame = camera.get_debug_frame()

        if frame is None:
            await asyncio.sleep(0.01)
            continue

        _, buffer = cv2.imencode(".jpg", frame)

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buffer.tobytes() +
            b"\r\n"
        )

        await asyncio.sleep(0.08)


@app.get("/camera-feed")
def camera_feed():
    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.on_event("shutdown")
async def shutdown_event():
    camera.stop()
    robot.stop()
    stop_serial()
    
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web-ui")
