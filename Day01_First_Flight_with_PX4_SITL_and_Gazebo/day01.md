# Day 01 — First Flight with PX4 SITL and Gazebo

## Goal

Set up a complete PX4 drone simulation workflow on Ubuntu 22.04 (WSL2), connect QGroundControl to PX4 SITL, inspect basic vehicle states, and integrate a RadioMaster Pocket for manual control in Gazebo.

---

## System Architecture

```text
RadioMaster Pocket
        ↓ USB
      Windows
        ↓ usbipd
       WSL2
        ↓
QGroundControl
        ↓ MAVLink
     PX4 SITL
        ↕
      Gazebo
```

### Component Roles

- **Gazebo**: simulates the world, drone physics, motors, IMU, GPS, and other sensors.
- **PX4 SITL**: runs the PX4 flight-control software on the computer instead of a physical flight controller.
- **QGroundControl (QGC)**: acts as the Ground Control Station (GCS), displays vehicle state, sends commands, and reads joystick input.
- **MAVLink**: communication protocol between QGroundControl and PX4.
- **RadioMaster Pocket**: provides manual pilot input through USB joystick mode.

---

# 1. Project Locations

PX4 repository:

```bash
~/Phenix_Project/Drone/PX4-Autopilot
```

QGroundControl:

```bash
~/Phenix_Project/Drone/QGroundControl
```

---

# 2. PX4 Development Environment

PX4 dependencies and Gazebo Harmonic were installed using:

```bash
cd ~/Phenix_Project/Drone/PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
```

Because Conda interfered with the system Python environment, PX4 Python dependencies were also installed using the Ubuntu system Python:

```bash
python3 -m pip install --user -r Tools/setup/requirements.txt
```

Verification:

```bash
which python3
python3 --version
which gz
gz sim --versions
```

Expected environment:

```text
Python 3.10.x
Gazebo Harmonic 8.x
```

---

# 3. Start PX4 SITL + Gazebo

Launch the PX4 x500 simulation:

```bash
cd ~/Phenix_Project/Drone/PX4-Autopilot
make px4_sitl gz_x500
```

Successful startup should open Gazebo and show:

```text
pxh>
```

in the PX4 terminal.

The simulation loop is:

```text
Gazebo simulated sensors
        ↓
      PX4 SITL
        ↓
 motor commands
        ↓
      Gazebo
```

---

# 4. QGroundControl

QGroundControl AppImage location:

```bash
~/Phenix_Project/Drone/QGroundControl/QGroundControl-x86_64.AppImage
```

Basic launch:

```bash
cd ~/Phenix_Project/Drone/QGroundControl
./QGroundControl-x86_64.AppImage
```

QGroundControl automatically connects to PX4 SITL through MAVLink.

When the connection is healthy, QGC should show:

```text
Ready To Fly
```

Important concept:

```text
QGC does not directly detect the Gazebo model.

Gazebo → PX4 SITL → MAVLink → QGroundControl
```

The position, attitude, altitude, battery, and other telemetry shown by QGC are simulated/estimated vehicle states provided by PX4.

---

# 5. First Takeoff and Landing

PX4 shell command for takeoff:

```bash
commander takeoff
```

PX4 shell command for landing:

```bash
commander land
```

Successful landing messages included:

```text
Landing at current position
Landing detected
Disarmed by landing
```

This confirmed that the complete control loop was working:

```text
QGC / PX4 command
      ↓
   PX4 SITL
      ↓
motor control
      ↓
    Gazebo
      ↓
simulated motion
```

---

# 6. Inspect PX4 Vehicle State

Read PX4 local position:

```bash
listener vehicle_local_position -n 1
```

Important fields:

```text
x
y
z

vx
vy
vz

heading
```

PX4 uses a **NED coordinate frame**:

```text
x = North
y = East
z = Down
```

Therefore:

```text
z = -3 m
```

means the drone is approximately 3 meters above the local reference point.

Example fields observed:

```text
ref_lat
ref_lon
x
y
z
vx
vy
vz
heading
xy_valid
z_valid
heading_good_for_control
```

---

# 7. RadioMaster Pocket → WSL2

The Pocket was configured as a USB joystick.

Windows detected the Pocket as:

```text
VID:PID = 1209:4f54
Generic Radiomaster Pocket Joystick
```

Because Ubuntu is running in WSL2, the USB device must be passed from Windows into WSL.

## Windows PowerShell

List USB devices:

```powershell
usbipd list
```

The Pocket appeared as something similar to:

```text
6-3    1209:4f54    USB Input Device
```

Allow WSL to use the device:

```powershell
usbipd bind --busid 6-3
```

Attach it to WSL:

```powershell
usbipd attach --wsl --busid 6-3
```

> The BUSID may change after reconnecting the device. Always run `usbipd list` first.

---

# 8. Verify Pocket Inside Ubuntu

Check USB detection:

```bash
lsusb
```

Expected device:

```text
1209:4f54 Generic Radiomaster Pocket Joystick
```

Check joystick device:

```bash
ls -l /dev/input/js0
```

Test raw joystick input:

```bash
jstest /dev/input/js0
```

The Pocket exposes:

```text
8 axes
24 buttons
```

---

# 9. Linux Input Permission

QGroundControl needs permission to read Linux input event devices.

One-time setup:

```bash
sudo usermod -aG input nicklee
```

For the current shell session:

```bash
newgrp input
```

Verify:

```bash
groups
```

The output should include:

```text
input
```

After a full WSL restart, new terminals should automatically have this permission.

---

# 10. Pocket Axis Mapping

The actual RadioMaster Pocket stick axes were identified using SDL2:

```text
Axis 0 = Roll
Axis 1 = Pitch
Axis 2 = Throttle
Axis 3 = Yaw
```

For Mode 2:

```text
Left stick vertical    = Throttle
Left stick horizontal  = Yaw

Right stick vertical   = Pitch
Right stick horizontal = Roll
```

---

# 11. QGroundControl SDL Mapping Fix

The default SDL mapping treated the throttle axis incorrectly, causing QGroundControl joystick calibration to fail.

The working mapping is:

```bash
export SDL_GAMECONTROLLERCONFIG="0300000009120000544f000011010000,EdgeTX Radiomaster Pocket Joystick,a:b0,b:b1,x:b3,y:b4,back:b10,guide:b12,start:b11,leftstick:b13,rightstick:b14,leftshoulder:b6,rightshoulder:b7,leftx:a0,lefty:a1,rightx:a3,righty:a2,lefttrigger:a4,righttrigger:a5,platform:Linux"
```

Launch QGroundControl from the same terminal:

```bash
cd ~/Phenix_Project/Drone/QGroundControl
./QGroundControl-x86_64.AppImage
```

Recommended combined startup:

```bash
export SDL_GAMECONTROLLERCONFIG="0300000009120000544f000011010000,EdgeTX Radiomaster Pocket Joystick,a:b0,b:b1,x:b3,y:b4,back:b10,guide:b12,start:b11,leftstick:b13,rightstick:b14,leftshoulder:b6,rightshoulder:b7,leftx:a0,lefty:a1,rightx:a3,righty:a2,lefttrigger:a4,righttrigger:a5,platform:Linux"

cd ~/Phenix_Project/Drone/QGroundControl
./QGroundControl-x86_64.AppImage
```

---

# 12. QGroundControl Joystick Calibration

In QGroundControl:

```text
Vehicle Configuration
→ Joystick
→ Calibration
→ Start
```

After calibration, verify:

```text
Right stick left/right  → Roll
Right stick up/down     → Pitch
Left stick left/right   → Yaw
Left stick up/down      → Throttle
```

PX4 joystick input mode was verified with:

```bash
param show COM_RC_IN_MODE
```

Expected:

```text
COM_RC_IN_MODE = 1
```

---

# 13. Arm / Disarm

PX4 Mode 2 stick gestures:

```text
ARM
Left stick ↘
Throttle minimum + Yaw right
```

```text
DISARM
Left stick ↙
Throttle minimum + Yaw left
```

`Ready To Fly` usually means the drone is healthy and ready to arm.

`Armed` means motor output is enabled.

---

# 14. Acro Mode Setup

Acro mode was selected for manual FPV-style flight.

Parameters used:

```bash
param set MC_ACRO_R_MAX 500
param set MC_ACRO_P_MAX 500
param set MC_ACRO_Y_MAX 360

param set MC_ACRO_EXPO 0.60
param set MC_ACRO_EXPO_Y 0.55
param set MC_ACRO_SUPEXPO 0.60
param set MC_ACRO_SUPEXPOY 0.60
```

Acro input behavior:

```text
Throttle → thrust
Yaw      → yaw rate
Pitch    → pitch rate
Roll     → roll rate
```

Unlike Position mode, Acro mode does not automatically hold position.

---

# 15. How to Start Everything Next Time

## Terminal 1 — PX4 + Gazebo

```bash
cd ~/Phenix_Project/Drone/PX4-Autopilot
make px4_sitl gz_x500
```

Wait for:

```text
pxh>
```

---

## Windows PowerShell — Pocket USB

```powershell
usbipd list
```

If the Pocket is not attached:

```powershell
usbipd attach --wsl --busid 6-3
```

If it has never been shared before:

```powershell
usbipd bind --busid 6-3
usbipd attach --wsl --busid 6-3
```

---

## Terminal 2 — Verify Pocket

```bash
ls /dev/input/js0
```

Optional:

```bash
jstest /dev/input/js0
```

---

## Terminal 3 — QGroundControl

```bash
export SDL_GAMECONTROLLERCONFIG="0300000009120000544f000011010000,EdgeTX Radiomaster Pocket Joystick,a:b0,b:b1,x:b3,y:b4,back:b10,guide:b12,start:b11,leftstick:b13,rightstick:b14,leftshoulder:b6,rightshoulder:b7,leftx:a0,lefty:a1,rightx:a3,righty:a2,lefttrigger:a4,righttrigger:a5,platform:Linux"

cd ~/Phenix_Project/Drone/QGroundControl
./QGroundControl-x86_64.AppImage
```

Then:

```text
1. Confirm Ready To Fly
2. Select Acro
3. Throttle to minimum
4. Arm
5. Fly manually with the Pocket
6. Land
7. Disarm
```

---

# 16. Important Note About Gazebo Reset

Avoid using Gazebo **Reset Simulation** while PX4 SITL is running.

It can reset/remove the Gazebo model while PX4 is still connected to the previous simulation state.

If the drone disappears or QGC loses connection:

```text
Stop PX4
→ restart PX4 SITL + Gazebo
→ verify Pocket USB
→ restart QGroundControl
```

---

# Day 01 Result

```text
PX4 development environment     ✅
Gazebo Harmonic                 ✅
PX4 SITL                        ✅
x500 quadrotor                  ✅
QGroundControl                  ✅
MAVLink connection              ✅
Takeoff / landing               ✅
vehicle_local_position          ✅
NED coordinate basics           ✅
RadioMaster Pocket → WSL2       ✅
Linux joystick                  ✅
SDL2 joystick debugging         ✅
Custom axis mapping             ✅
QGC joystick calibration        ✅
Arm / Disarm                    ✅
Acro mode configuration         ✅
```

## Key Takeaway

The complete manual-control pipeline is now understood and working:

```text
RadioMaster Pocket
        ↓
QGroundControl
        ↓ MAVLink
     PX4 SITL
        ↕
      Gazebo
```

This simulation setup can later be extended with ROS 2 for autonomous flight and eventually migrated from PX4 SITL to a real PX4 flight controller.

