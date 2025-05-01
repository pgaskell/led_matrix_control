import importlib
import time
import os
import threading
from wall import Wall
from param_slider_ui import run_param_ui

# Config
MATRIX_WIDTH = 24
MATRIX_HEIGHT = 24
FPS = 30

# --- Dynamic pattern loader ---
def load_patterns():
    patterns = {}
    pattern_dir = "patterns"
    for fname in os.listdir(pattern_dir):
        if fname.endswith(".py") and not fname.startswith("_"):
            modname = fname[:-3]
            module = importlib.import_module(f"patterns.{modname}")
            if hasattr(module, "Pattern"):
                patterns[modname] = module
    return patterns

# Load all patterns
all_patterns = load_patterns()
pattern_names = sorted(all_patterns.keys())
print("Available patterns:", pattern_names)

# Select pattern
selected_name = pattern_names[1]
module = all_patterns[selected_name]

# Load parameters
params = module.PARAMS.copy()

# --- Launch parameter UI in a separate thread ---
slider_thread = threading.Thread(target=run_param_ui, args=(params,))
slider_thread.daemon = True
slider_thread.start()

# Instantiate pattern with live-adjusted params
current_pattern = module.Pattern(MATRIX_WIDTH, MATRIX_HEIGHT, params=params)

# Initialize wall (auto-selects real or simulator)
wall = Wall(width=MATRIX_WIDTH, height=MATRIX_HEIGHT)

# Main loop
try:
    while True:
        frame = current_pattern.render()
        wall.show(frame)
        time.sleep(1.0 / FPS)
except KeyboardInterrupt:
    wall.clear()
    print("Exiting...")
