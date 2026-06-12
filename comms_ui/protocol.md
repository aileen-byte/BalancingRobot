# Sir BalanceAlot Communication Protocol

## Telemetry message

Sent from the robot bridge to the web UI over WebSocket.

```json
{
  "time_ms": 1234,
  "angle_deg": 2.4,
  "gyro_dps": -0.8,
  "motor_left": 120,
  "motor_right": 118,
  "battery_v": 7.6,
  "mode": "BALANCING"
}