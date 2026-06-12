const statusEl = document.getElementById("status");

const ws = new WebSocket(`ws://${window.location.host}/ws`);

let previousPackageDropped = false;
let packageDropCount = 0;

ws.onopen = () => {
  statusEl.textContent = "Connected";
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.package_dropped && !previousPackageDropped) {
    addPackageDropEvent(data);
  }

  previousPackageDropped = data.package_dropped;

  document.getElementById("angle").textContent = data.angle_deg.toFixed(2);
  document.getElementById("gyro").textContent = data.gyro_dps.toFixed(2);
  document.getElementById("left").textContent = data.motor_left;
  document.getElementById("right").textContent = data.motor_right;
  document.getElementById("battery").textContent = data.battery_v.toFixed(2);
  document.getElementById("mode").textContent = data.mode;
};

ws.onclose = () => {
  statusEl.textContent = "Disconnected";
};

function addPackageDropEvent(data) {
  packageDropCount += 1;

  const now = new Date();
  const eventList = document.getElementById("event-list");
  const noEvents = document.getElementById("no-events");

  noEvents.classList.add("hidden");

  const eventCard = document.createElement("div");
  eventCard.className = "event-card event-green";

  eventCard.innerHTML = `
    <div class="event-card-main">
      <div class="event-icon">📦</div>

      <div class="event-text">
        <div class="event-title">Package dropped #${packageDropCount}</div>
        <div class="event-detail">Time: ${data.package_drop_time || now.toLocaleTimeString()}</div>
        <div class="event-detail">Mode: ${data.mode || "Unknown"}</div>
      </div>

      <button class="clear-event-btn">Clear</button>
    </div>
  `;

  eventCard.querySelector(".clear-event-btn").addEventListener("click", () => {
    eventCard.remove();
    updateActivePackageCount();

    if (eventList.children.length === 0) {
      noEvents.classList.remove("hidden");
    }
  });

  eventList.appendChild(eventCard);
  updateActivePackageCount();

  setTimeout(() => {
    if (eventCard.isConnected) {
      eventCard.classList.remove("event-green");
      eventCard.classList.add("event-orange");
    }
  }, 5000);

  setTimeout(() => {
    if (eventCard.isConnected) {
      eventCard.classList.remove("event-orange");
      eventCard.classList.add("event-red");
    }
  }, 10000);
}

function sendCommand(command) {
  ws.send(JSON.stringify({
    type: "command",
    command: command,
    time_ms: Date.now()
  }));

  console.log("Sent command:", command);
}

function sendMode(mode) {
  ws.send(JSON.stringify({
    type: "mode",
    mode: mode,
    time_ms: Date.now()
  }));

  console.log("Sent mode:", mode);
}

function updateActivePackageCount() {
  const eventList = document.getElementById("event-list");
  const countEl = document.getElementById("active-package-count");

  if (!countEl) return;

  const activeCount = eventList.children.length;
  countEl.textContent = `${activeCount} active`;
}

function sendTuningUpdate() {
  const tuning = {
    speed_kp: Number(document.getElementById("tune-speed-kp").value),
    speed_kd: Number(document.getElementById("tune-speed-kd").value),
    speed_ki: Number(document.getElementById("tune-speed-ki").value),
    balance_kp: Number(document.getElementById("tune-balance-kp").value),
    balance_kd: Number(document.getElementById("tune-balance-kd").value),
    speed: Number(document.getElementById("tune-speed").value),
    auto_kp: Number(document.getElementById("tune-auto-kp").value),
    auto_ki: Number(document.getElementById("tune-auto-ki").value),
    auto_kd: Number(document.getElementById("tune-auto-kd").value),
  };

  ws.send(JSON.stringify({
    type: "tuning",
    values: tuning,
    time_ms: Date.now()
  }));

  console.log("Sent tuning update:", tuning);
}

const tuningPairs = [
  ["tune-balance-kp-slider", "tune-balance-kp"],
  ["tune-balance-kd-slider", "tune-balance-kd"],
  ["tune-speed-kp-slider", "tune-speed-kp"],
  ["tune-speed-kd-slider", "tune-speed-kd"],
  ["tune-speed-ki-slider", "tune-speed-ki"],
  ["tune-speed-slider", "tune-speed"],
  ["tune-auto-kp-slider", "tune-auto-kp"],
  ["tune-auto-ki-slider", "tune-auto-ki"],
  ["tune-auto-kd-slider", "tune-auto-kd"],
];

tuningPairs.forEach(([sliderId, numberId]) => {
  const slider = document.getElementById(sliderId);
  const number = document.getElementById(numberId);

  slider.addEventListener("input", () => {
    number.value = slider.value;
  });

  number.addEventListener("input", () => {
    slider.value = number.value;
  });
});