# HandDesk

Control your computer with hand gestures and the built-in webcam. HandDesk tracks your
hand locally, shows a live skeleton preview, and turns recognised gestures into
desktop mouse and keyboard actions. Camera frames stay in memory.

## macOS setup

This build targets Apple Silicon Macs with Python 3.12. Open Terminal in the
folder containing `main.py`. If you use Homebrew and need Python, run
`brew install python@3.12`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r requirements.txt
mkdir -p models
curl -fL --retry 2 \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task \
  -o models/hand_landmarker.task
cp -n settings.json settings.local.json
python -B main.py --config settings.local.json
```

Grant your launcher (Terminal, for example) access in **System Settings → Privacy
& Security** under **Camera**, **Accessibility** and **Input Monitoring**. Restart
your launcher after changing permissions if the app asks you to. The
`--preview-only` flag lets you try recognition with the camera without enabling
desktop control. Use `--camera 1` to try a second camera or `--model /path/to/model.task`
to use an existing model. After a fresh launch, wait for the preview and FPS readout.

## Windows setup

Use 64-bit Python 3.12 on Windows 10 or 11. Extract this project and open
PowerShell in the folder containing `main.py`.

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install --only-binary=:all: -r requirements.txt
New-Item -ItemType Directory -Force models | Out-Null
curl.exe -fL --retry 2 "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" -o models/hand_landmarker.task
./.venv/Scripts/python.exe -B main.py
```

Allow desktop apps to access your webcam in Windows camera privacy settings.
Click the preview before pressing **C** to calibrate, **P** for practice mode,
**X** for precision mode, or **Esc / Q** to quit. The tracking pause button is
in the preview. Edit `settings.json` for gesture settings.

Windows uses **Win+Ctrl+Left/Right** to switch desktops, **Win+Tab** for Task
View, and **F11** for fullscreen in apps that support it. The macOS menu bar,
graphical settings dialog and custom app picker are Mac features.

## Gestures

| Action | Gesture |
|---|---|
| Move cursor | Raise your index finger and curl your middle, ring and pinky fingers. |
| Left-click | Hold the cursor steady for 1.5 seconds. |
| Grab and drop | Pinch thumb and index, then release to grab. Point to move. Pinch and release again or show an open palm to drop. |
| Right-click | Hold a peace sign still for 0.8 seconds. |
| Scroll | Move a peace sign up or down. |
| Volume | Raise your middle, ring and pinky fingers and move your hand up or down. |
| Desktop or Mission Control | Swipe an open palm left or right to switch Spaces, or up for Mission Control. |
| Fullscreen | Make a brief fist, then open your palm in the same spot. |
| Minimise | Show your palm, then make a brief fist in the same spot. |
| Pause or resume | Hold a fist for one second to pause, then an open palm for one second to resume. |

Window gestures act on the active window. Fullscreen and Mission Control rely on
the corresponding macOS shortcuts. Esc or Q quits from the preview.

## Quick demo

1. Choose **Practice mode** from the HandDesk menu bar and try a gesture.
2. Press **C** with the preview focused or choose **Calibrate reach**. Trace the
   corners of your comfortable reach with your index finger for 30 seconds.
   You can also start with `--calibrate`. Calibration is saved to the active config.
3. Turn off practice mode and try moving and dwell-clicking in TextEdit.
4. Open **Switch apps** from the menu bar, point across the app row, and hold a
   selection for one second. **Precision mode** starts at the current cursor
   position and reduces how far the cursor moves per hand movement.

Use **Gesture settings** to tune sensitivity, smoothing, dwell time and gesture
toggles. Use **Hide preview** to keep tracking with the preview out of the way,
or **Disable tracking** in the preview to pause indefinitely or on a timer.

## Run tests

The tests use simulated hand landmarks and the Python standard library. They do
not require a camera, the model, or macOS permissions.

```bash
python3.12 -B -m unittest discover -s tests -v
```

`gestures.py` recognises poses and returns action intents. `actions.py` sends
macOS input, `desktop_ui.py` manages the native menu, and `tracking.py` runs
the hand-landmark model. See [LICENSE](LICENSE) for the MIT licence.
