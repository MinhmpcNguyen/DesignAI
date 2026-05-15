# Manual Local GLB Orientation Bundle

This folder is a standalone copy of the local GLB orientation viewer and the
`demo_inventory` sample models. It can run offline after Python is installed.

## Contents

- `manual_local_glb_orientation.py`: local web viewer for inspecting and saving
  GLB orientation sidecar files.
- `demo_inventory/`: sample `.glb` files and `.glb.orientation.json` files.
- `frontend/src/vendor/three/`: local Three.js viewer files.
- `frontend/public/assets/three/basis/`: local KTX/Basis transcoder files.
- `requirements.txt`: intentionally empty of dependencies because the Python
  script uses only the standard library.

## Requirements

- Python 3.10 or newer.
- A browser with WebGL support.

## Setup On A New Machine

From the folder that contains this README:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```bash
python manual_local_glb_orientation.py demo_inventory
```

Then open:

```text
http://127.0.0.1:8790
```

The script defaults to `demo_inventory`, so this also works:

```bash
python manual_local_glb_orientation.py
```

If port `8790` is already used:

```bash
python manual_local_glb_orientation.py demo_inventory --port 8791
```

To inspect models inside the `unused` subfolder:

```bash
python manual_local_glb_orientation.py demo_inventory/unused
```

## Save Behavior

Click `Save local orientation` in the browser to write or update:

```text
<model>.glb.orientation.json
```

The sidecar is saved next to the selected `.glb` file. The tool does not write
to a database.

## Notes

Keep the `frontend/` folder next to `manual_local_glb_orientation.py`; those
files are the local viewer assets. If a model loads but the page stays blank,
try another browser with WebGL enabled.
