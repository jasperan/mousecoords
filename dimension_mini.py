"""
Automator for Antimatter Dimensions - Mini version (Galaxies and Boosts only)
"""

import pyautogui
import win32gui
from ctypes import windll
import time
from datetime import datetime
from threading import Thread, Lock

# Disable fail-safe (careful with this!)
pyautogui.FAILSAFE = False

# Global stats
class Stats:
    dimension_boosts = 0
    antimatters = 0
    max_ticks = 0
    antimatter_available = 1  # Counter for available antimatter detections
    dimension_boosts_available = 22  # Counter for available dimension boosts

# ANSI color codes
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Thread-safe printing
print_lock = Lock()
cooldowns = {}  # Store cooldown times for each position

def get_pixel_color(x, y):
    # Get DC for entire screen
    hdc = win32gui.GetDC(0)
    # Get pixel color
    color = windll.gdi32.GetPixel(hdc, x, y)
    # Release DC
    win32gui.ReleaseDC(0, hdc)
    # Convert BGR to RGB (Windows returns BGR)
    b = color & 0xFF
    g = (color >> 8) & 0xFF
    r = (color >> 16) & 0xFF
    return (r, g, b)

def print_stats():
    """Print current stats"""
    with print_lock:
        print(f"\r{Colors.BLUE}Stats:{Colors.ENDC} ", end='')
        print(f"Dimension Boosts: {Colors.GREEN}{Stats.dimension_boosts}{Colors.ENDC} | ", end='')
        print(f"Boosts Available: {Colors.GREEN if Stats.dimension_boosts_available > 0 else Colors.RED}{Stats.dimension_boosts_available}{Colors.ENDC} | ", end='')
        print(f"Antimatters: {Colors.YELLOW}{Stats.antimatters}{Colors.ENDC} | ", end='')
        print(f"Max Ticks: {Colors.BLUE}{Stats.max_ticks}{Colors.ENDC} | ", end='')
        print(f"Antimatter Available: {Colors.GREEN if Stats.antimatter_available > 0 else Colors.RED}{Stats.antimatter_available}{Colors.ENDC}", end='    \n')

def print_colored(text, r, g, b):
    # Print text with its own color as background
    timestamp = datetime.now().strftime("%H:%M:%S")
    with print_lock:
        print(f"{Colors.BLUE}[{timestamp}]{Colors.ENDC} \033[48;2;{r};{g};{b}m{text}\033[0m", end='')

def print_log(text, color=Colors.ENDC, prefix="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with print_lock:
        print(f"{Colors.BLUE}[{timestamp}]{Colors.ENDC} {color}[{prefix}]{Colors.ENDC} {text}")

def color_matches(color1, color2, tolerance=3):
    """Check if colors match within a tolerance"""
    return all(abs(a - b) <= tolerance for a, b in zip(color1, color2))

def handle_click(coord, name):
    """Handle clicking for a position"""
    current_time = time.time()
    
    if name == "Antimatter Galaxies":
        if Stats.antimatter_available <= 0:
            print_log(f"Skipping Antimatter Galaxies - no detections available until next Big Crunch", Colors.YELLOW, "SKIP")
            cooldowns[name] = current_time + 1  # Set cooldown anyway
            return
        print_log(f"Antimatter Galaxies clicked (Detections remaining: {Stats.antimatter_available - 1})", Colors.YELLOW, "CLICK")
        Stats.antimatters += 1
        cooldowns[name] = current_time + 1  # 1 second cooldown
        Stats.antimatter_available -= 1
    elif name == "Dimension Boost":
        if Stats.dimension_boosts_available <= 0:
            print_log(f"Skipping Dimension Boost - no boosts available until next Big Crunch", Colors.YELLOW, "SKIP")
            cooldowns[name] = current_time + 1  # Set cooldown anyway
            return
        print_log(f"Dimension Boost clicked (Boosts remaining: {Stats.dimension_boosts_available - 1})", Colors.YELLOW, "CLICK")
        Stats.dimension_boosts += 1
        Stats.dimension_boosts_available -= 1
        cooldowns[name] = current_time + 1  # 1 second cooldown
    elif name == "Big Crunch":
        Stats.antimatter_available = 1  # Reset antimatter detection counter
        Stats.dimension_boosts_available = 22  # Reset dimension boosts counter
        cooldowns[name] = current_time + 1  # 1 second cooldown
        print_log(f"Big Crunch clicked - Antimatter detections reset to {Stats.antimatter_available}, Dimension Boosts reset to {Stats.dimension_boosts_available}", Colors.YELLOW, "CRUNCH")
    elif name == "Max Ticks":
        Stats.max_ticks += 1
        cooldowns[name] = current_time + 1.5  # 1.5 second cooldown
        print_log(f"Max Ticks upgrade clicked", Colors.YELLOW, "UPGRADE")
    
    # Click immediately
    pyautogui.click(coord["pos"][0], coord["pos"][1])
    print_stats()
    print_log(f"Click completed at {name}", Colors.GREEN, "DONE")
    with print_lock:
        print("-"*50)

def monitor_and_click():
    TARGET_COLOR = (103, 196, 90)  # Green color for regular buttons
    CRUNCH_COLOR = (51, 127, 182)  # Blue color for Big Crunch
    COORDINATES = [
        {"pos": (2076, 908), "name": "Antimatter Galaxies", "color": TARGET_COLOR},  # Check first
        {"pos": (860, 909), "name": "Dimension Boost", "color": TARGET_COLOR},   # Check second
        {"pos": (1512, 111), "name": "Big Crunch", "color": CRUNCH_COLOR},  # Check third
        {"pos": (1546, 328), "name": "Max Ticks", "color": TARGET_COLOR}  # Check last
    ]
    active_threads = []

    print("\n" + "="*50)
    print_log(f"{Colors.BOLD}Color Monitor Started{Colors.ENDC}", Colors.GREEN, "START")
    print_log(f"Regular Target Color: RGB{TARGET_COLOR}", Colors.YELLOW, "CONFIG")
    print_log(f"Big Crunch Color: RGB{CRUNCH_COLOR}", Colors.YELLOW, "CONFIG")
    print_stats()
    print("="*50 + "\n")
    print_log("Press Ctrl+C to stop monitoring", Colors.YELLOW, "INFO")
    print("-"*50)

    while True:
        try:
            # Clean up completed threads
            active_threads = [t for t in active_threads if t.is_alive()]

            # Print all colors in one row
            print("\r", end='')  # Carriage return
            for coord in COORDINATES:
                x, y = coord["pos"]
                current_color = get_pixel_color(x, y)
                
                # Skip if in cooldown or if Antimatter with no detections available
                if (coord["name"] in cooldowns and time.time() < cooldowns[coord["name"]]) or \
                   (coord["name"] == "Antimatter Galaxies" and Stats.antimatter_available <= 0):
                    print_colored("□ ", current_color[0], current_color[1], current_color[2])
                    continue
                    
                print_colored("■ ", current_color[0], current_color[1], current_color[2])
                
                if color_matches(current_color, coord["color"]):
                    print("\n")  # New line before action logs
                    print_log(f"Target color detected at {coord['name']}!", Colors.GREEN, "MATCH")
                    
                    # Start a new thread for clicking
                    click_thread = Thread(target=handle_click, args=(coord, coord['name']))
                    click_thread.daemon = True
                    click_thread.start()
                    active_threads.append(click_thread)
                    
                    # If Antimatter Galaxies is clicked, break the loop to skip remaining checks
                    if coord["name"] == "Antimatter Galaxies" and Stats.antimatter_available > 0:
                        break
            
            # Wait before next check
            time.sleep(0.5)  # Check twice per second
            
        except KeyboardInterrupt:
            print("\n" + "="*50)
            print_log("Stopping color monitor...", Colors.RED, "STOP")
            print_stats()  # Final stats
            print("="*50 + "\n")
            break
        except Exception as e:
            print_log(f"Error: {e}", Colors.RED, "ERROR")
            time.sleep(1)

if __name__ == "__main__":
    monitor_and_click() 