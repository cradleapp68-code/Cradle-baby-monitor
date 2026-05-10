import streamlit as st
import time
import streamlit.components.v1 as components
import paho.mqtt.client as mqtt
import datetime
import base64
import struct

st.set_page_config(layout="wide")

# ---------- STYLE ----------
st.markdown("""
<style>
body { background-color: #0E1117; color: white; }

.big-card {
    background-color: #1c1f26;
    padding: 25px;
    border-radius: 15px;
    text-align: center;
    box-shadow: 0px 0px 15px rgba(0,0,0,0.3);
}

.good {color: #00E676; font-size:22px;}
.warn {color: #FFD740; font-size:22px;}
.danger {color: #FF5252; font-size:22px;}

.metric {
    font-size: 40px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

st.title("👶 Smart Diaper Health Monitor")
st.caption("Real-time baby hygiene & safety tracking")

placeholder = st.empty()

# MQTT setup
if 'mqtt_started' not in st.session_state:
    st.session_state.mqtt_started = True
    st.session_state.latest_data = {
        "force": 0,
        "wet": 0,
        "stool": 0,
        "temp": 36.5,
        "time": ""
    }
    st.session_state.history = []

    def on_connect(client, userdata, flags, rc):
        print("Connected to MQTT broker")
        topics = ["cradle/pod/+/telemetry"]  # Subscribe to telemetry from any device
        for topic in topics:
            client.subscribe(topic)

    def on_message(client, userdata, msg):
        try:
            # Decode base64 payload
            decoded = base64.b64decode(msg.payload)
            # Unpack the telemetry packet (little endian)
            # Format: <H h h h h H H B B B B
            # magic (uint16), temp_x100 (int16), accel_x/y/z (int16*3), wetness_raw (uint16), fsr_raw (uint16), diaper (uint8), position (uint8), alerts (uint8), seq (uint8)
            unpacked = struct.unpack('<H h h h h H H B B B B', decoded[:24])  # 24 bytes
            magic = unpacked[0]
            if magic != 0xCAFE:
                print(f"Invalid magic: {magic}")
                return
            temp_x100 = unpacked[1]
            wetness_raw = unpacked[5]
            fsr_raw = unpacked[6]
            # Map to dashboard fields
            temp = temp_x100 / 100.0
            force = fsr_raw
            wet = wetness_raw
            stool = wetness_raw  # Combined in firmware, adjust if needed
            st.session_state.latest_data["temp"] = temp
            st.session_state.latest_data["force"] = force
            st.session_state.latest_data["wet"] = wet
            st.session_state.latest_data["stool"] = stool
            st.session_state.latest_data["time"] = datetime.datetime.now().strftime("%H:%M:%S")
            st.session_state.history.append(st.session_state.latest_data.copy())
            if len(st.session_state.history) > 100:
                st.session_state.history.pop(0)
        except Exception as e:
            print(f"Error parsing message: {e}")

    client = mqtt.Client()
    client.tls_set()  # Enable TLS
    client.username_pw_set("Mahesh", "Mahi@j17")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect("77823e7e7bf049108c6c572c1549e0c5.s1.eu.hivemq.cloud", 8883, 60)
        client.loop_start()
    except Exception as e:
        st.error(f"Failed to connect to MQTT broker: {e}")

# ---------- LOOP ----------
while True:
    with placeholder.container():

        data = st.session_state.latest_data
        history = st.session_state.history

        force = data["force"]
        wet = data["wet"]
        stool = data["stool"]
        temp = data["temp"]
        t = data["time"]

        # ---------- CONDITIONS ----------
        wet_alert = wet > 530

        # Stool only if BOTH stool level AND pressure exist
        force_alert = force < 4000

        # ---------- STATUS ----------
        if force_alert:
            st.error("🚨 STOOL DETECTED – Change immediately!")
        elif wet_alert:
            st.warning("⚠ Wet diaper detected")
        else:
            st.success("✅ Baby is comfortable")

        # ---------- SOUND ----------
        if force_alert or wet_alert or force < 4000:
            components.html("""
                <audio autoplay>
                <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
                </audio>
            """, height=0)

        st.markdown("---")

        # ---------- METRIC CARDS ----------
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.markdown('<div class="big-card"><div>🌡 Temperature</div>'
                        f'<div class="metric">{temp}°C</div></div>',
                        unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="big-card"><div>💧 Wet Level</div>'
                        f'<div class="metric">{wet}</div></div>',
                        unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="big-card"><div>💩 Stool Level</div>'
                        f'<div class="metric">{stool}</div></div>',
                        unsafe_allow_html=True)

        with c4:
            st.markdown('<div class="big-card"><div>🧸 Pressure</div>'
                        f'<div class="metric">{force}</div></div>',
                        unsafe_allow_html=True)

        st.caption(f"🕒 Last update: {t}")

        st.markdown("---")

        # ---------- HISTORY ----------
        if len(history) > 2:
            chart_data = {
                "wet": [item["wet"] for item in history],
                "stool": [item["stool"] for item in history],
                "temp": [item["temp"] for item in history],
            }
            st.subheader("📈 Trend Monitoring")
            st.line_chart(chart_data)

    time.sleep(2)
