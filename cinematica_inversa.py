#!/usr/bin/env python3
from interbotix_xs_modules.arm import InterbotixManipulatorXS
import mediapipe as mp
import cv2
import numpy as np
import time
import math

# --- System States ---
STATE_IDLE = 0
STATE_TELEOP = 1
STATE_RECORDING = 2
STATE_PLAYING = 3

# --- Global Variables ---
current_state = STATE_IDLE
recorded_movements = []
current_play_index = 0
loop_enabled = False  # Nova variável para controle de Loop

# --- Safety & Transition Configs ---
transition_start_time = 0
TRANSITION_DURATION = 2.0    
TRANSITION_THRESHOLD_METERS = 0.06  

last_toggle_time = 0        
TOGGLE_COOLDOWN = 2.0

# --- WORKSPACE LIMITS (METERS) ---
R_X_MIN, R_X_MAX = 0.10, 0.35   
R_Y_MIN, R_Y_MAX = -0.40, 0.40  
R_Z_MIN, R_Z_MAX = 0.02, 0.35   

# --- Visual Configs ---
MIN_RADIUS = 5   
MAX_RADIUS = 30  

# --- OpenCV & MediaPipe Setup ---
video = cv2.VideoCapture(0)
width = 640
height = 480
video.set(cv2.CAP_PROP_FRAME_WIDTH, width)
video.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands
hand_detector = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

bot = InterbotixManipulatorXS("px100", "arm", "gripper")

# --- Helper Functions ---

def map_value(value, src_min, src_max, dest_min, dest_max):
    if abs(src_max - src_min) < 0.0001: return dest_min
    val = ((value - src_min) / (src_max - src_min)) * (dest_max - dest_min) + dest_min
    return max(min(val, max(dest_min, dest_max)), min(dest_min, dest_max))

def get_dist_3d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

def detect_gesture(landmarks):
    """
    Classifies hand geometry into standard HRI gestures.
    """
    wrist = landmarks[0]
    fingers = []
    # Check extension of Index, Middle, Ring, Pinky
    for i in [8, 12, 16, 20]: 
        tip = landmarks[i]; pip = landmarks[i-2]
        is_ext = math.hypot(tip.x-wrist.x, tip.y-wrist.y) > math.hypot(pip.x-wrist.x, pip.y-wrist.y)
        fingers.append(is_ext)
    
    idx, mid, rng, pnk = fingers
    
    # 1. PALM (Open Hand) -> All fingers extended
    if all(fingers): return "PALM"
    
    # 2. FIST (Closed Hand) -> No fingers extended
    if not any(fingers): return "FIST"
    
    # 3. INDEX (Pointing) -> Only Index extended
    if idx and not mid and not rng and not pnk: return "INDEX"
    
    # 4. HORNS (Gesture for Play) -> Index and Pinky extended
    if idx and pnk and not mid and not rng: return "HORNS"

    # 5. VICTORY (Gesture for Loop Toggle) -> Index and Middle extended
    if idx and mid and not rng and not pnk: return "VICTORY"
    
    return "UNKNOWN"

def get_robot_cartesian_pose():
    """Returns current robot end-effector pose (x, y, z) in meters."""
    pose = bot.arm.get_ee_pose()
    return np.array([pose[0, 3], pose[1, 3], pose[2, 3]])

# --- Main Execution ---

def main():
    global current_state, recorded_movements, current_play_index, loop_enabled
    global transition_start_time, last_toggle_time

    print("--- HRI GESTURE CONTROL SYSTEM INITIALIZED ---")
    bot.arm.go_to_home_pose(moving_time=1.0)
    bot.gripper.open(1.0)

    while True:
        success, frame = video.read()
        if not success: break
        
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hand_detector.process(rgb)
        
        gesture = "NONE"
        target_xyz = None  
        
        # --- ROBOT FEEDBACK (Black Marker) ---
        current_xyz = get_robot_cartesian_pose() 
        
        rob_px_x = int(map_value(current_xyz[1], R_Y_MAX, R_Y_MIN, 0, width))
        rob_px_y = int(map_value(current_xyz[2], R_Z_MAX, R_Z_MIN, 0, height))
        rob_radius = int(map_value(current_xyz[0], R_X_MIN, R_X_MAX, MIN_RADIUS, MAX_RADIUS))
        
        cv2.circle(frame, (rob_px_x, rob_px_y), rob_radius, (0, 0, 0), 2)
        cv2.circle(frame, (rob_px_x, rob_px_y), 2, (0, 0, 0), -1)

        if results.multi_hand_landmarks:
            for hand_lms in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)
                gesture = detect_gesture(hand_lms.landmark)
                
                wrist = hand_lms.landmark[0]
                mid_base = hand_lms.landmark[9]
                
                hand_screen_x = (wrist.x + mid_base.x) / 2 * width
                hand_screen_y = (wrist.y + mid_base.y) / 2 * height
                
                prof_raw = math.sqrt((mid_base.x-wrist.x)**2 + (mid_base.y-wrist.y)**2 + (mid_base.z-wrist.z)**2)
                
                # --- HAND TARGET (Blue Marker) ---
                hand_radius = int(map_value(prof_raw, 0.05, 0.2, MIN_RADIUS, MAX_RADIUS))
                cv2.circle(frame, (int(hand_screen_x), int(hand_screen_y)), hand_radius, (255, 0, 0), 2)

                # --- IK MAPPING ---
                t_x = map_value(prof_raw, 0.05, 0.2, R_X_MIN, R_X_MAX)
                t_y = map_value(hand_screen_x, 0, width, R_Y_MAX, R_Y_MIN)
                t_z = map_value(hand_screen_y, height, 0, R_Z_MIN, R_Z_MAX)
                
                target_xyz = np.array([t_x, t_y, t_z])

                thumb = hand_lms.landmark[4]
                idx = hand_lms.landmark[8]
                dist_pinca = math.hypot((thumb.x-idx.x)*width, (thumb.y-idx.y)*height)
                gripper_closed = dist_pinca < 30


        # --- STATE MACHINE ---
        current_time = time.time()
        
        # Display Gesture Name
        if gesture != "NONE":
            cv2.putText(frame, f"GESTURE: {gesture}", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        if current_state == STATE_IDLE:
            cv2.putText(frame, "IDLE - ALIGN MARKERS TO START", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # SHOW LOOP STATUS
            loop_color = (0, 255, 0) if loop_enabled else (0, 0, 255)
            loop_text = "ON" if loop_enabled else "OFF"
            cv2.putText(frame, f"LOOP MODE: {loop_text}", (width - 200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, loop_color, 2)

            # Toggle Loop with VICTORY gesture
            if gesture == "VICTORY" and (current_time - last_toggle_time > TOGGLE_COOLDOWN):
                loop_enabled = not loop_enabled
                last_toggle_time = current_time
                print(f">>> LOOP MODE {'ENABLED' if loop_enabled else 'DISABLED'}")

            # Transition: PALM
            if gesture == "PALM" and target_xyz is not None:
                dist_real = get_dist_3d(target_xyz, current_xyz)
                dist_cm = int(dist_real * 100)
                
                line_color = (0, 255, 0) if dist_real < TRANSITION_THRESHOLD_METERS else (0, 0, 255)
                cv2.line(frame, (int(hand_screen_x), int(hand_screen_y)), (rob_px_x, rob_px_y), line_color, 2)
                
                mid_line_x = int((hand_screen_x + rob_px_x)/2)
                mid_line_y = int((hand_screen_y + rob_px_y)/2)
                cv2.putText(frame, f"{dist_cm}cm", (mid_line_x, mid_line_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, line_color, 2)

                radius_diff = abs(hand_radius - rob_radius)
                if radius_diff > 5:
                    msg = "MOVE BACK" if hand_radius > rob_radius else "MOVE CLOSER"
                    cv2.putText(frame, msg, (mid_line_x, mid_line_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

                if dist_real < TRANSITION_THRESHOLD_METERS:
                    if transition_start_time == 0:
                        transition_start_time = current_time
                    
                    elapsed = current_time - transition_start_time
                    # Loading Bar
                    bar_w = int(map_value(elapsed, 0, TRANSITION_DURATION, 0, 100))
                    cv2.rectangle(frame, (int(hand_screen_x)-50, int(hand_screen_y)-40), 
                                         (int(hand_screen_x)-50+bar_w, int(hand_screen_y)-35), (0,255,0), -1)
                    
                    if elapsed >= TRANSITION_DURATION:
                        print(">>> TELEOP ACTIVATED")
                        current_state = STATE_TELEOP
                        last_toggle_time = current_time
                        transition_start_time = 0
                else:
                    transition_start_time = 0 

            # Transition: HORNS (Start Playback)
            if gesture == "HORNS" and (current_time - last_toggle_time > TOGGLE_COOLDOWN):
                current_state = STATE_PLAYING
                current_play_index = 0
                last_toggle_time = current_time

        elif current_state == STATE_TELEOP:
            cv2.putText(frame, "TELEOP ACTIVE", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if gesture == "FIST": current_state = STATE_IDLE
            # Transition: INDEX (Start Recording)
            elif gesture == "INDEX" and (current_time - last_toggle_time > TOGGLE_COOLDOWN):
                current_state = STATE_RECORDING
                recorded_movements = []
                last_toggle_time = current_time

            if target_xyz is not None:
                bot.arm.set_ee_pose_components(
                    x=target_xyz[0], y=target_xyz[1], z=target_xyz[2], 
                    pitch=0, moving_time=0.1, blocking=False
                )
                if gripper_closed: bot.gripper.close(delay=0)
                else: bot.gripper.open(delay=0)

        elif current_state == STATE_RECORDING:
            cv2.putText(frame, f"RECORDING: {len(recorded_movements)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.circle(frame, (30, 50), 10, (0,0,255), -1)

            # Transition: INDEX (Stop Recording)
            if gesture == "INDEX" and (current_time - last_toggle_time > TOGGLE_COOLDOWN):
                current_state = STATE_TELEOP
                last_toggle_time = current_time
            elif gesture == "FIST": current_state = STATE_IDLE

            if target_xyz is not None:
                bot.arm.set_ee_pose_components(
                    x=target_xyz[0], y=target_xyz[1], z=target_xyz[2], 
                    pitch=0, moving_time=0.1, blocking=False
                )
                if gripper_closed: bot.gripper.close(delay=0)
                else: bot.gripper.open(delay=0)
                recorded_movements.append({'pose': target_xyz, 'gripper': gripper_closed})

        elif current_state == STATE_PLAYING:
            mode_text = " (LOOP)" if loop_enabled else ""
            cv2.putText(frame, f"PLAYING {current_play_index}{mode_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            if gesture == "FIST": current_state = STATE_IDLE
            
            if len(recorded_movements) == 0:
                current_state = STATE_IDLE
            elif current_play_index == 0:
                step = recorded_movements[current_play_index]
                bot.gripper.open(0)
                bot.arm.go_to_home_pose(moving_time=1.0)

                bot.arm.set_ee_pose_components(
                    x=step['pose'][0], y=step['pose'][1], z=step['pose'][2],
                    pitch=0, moving_time=0.5, blocking=True
                )
                current_play_index += 1
            elif current_play_index < len(recorded_movements):
                step = recorded_movements[current_play_index]
                bot.arm.set_ee_pose_components(
                    x=step['pose'][0], y=step['pose'][1], z=step['pose'][2],
                    pitch=0, moving_time=0.1, blocking=False
                )
                if step['gripper']: bot.gripper.close(delay=0.1)
                else: bot.gripper.open(delay=0.1)
                current_play_index += 1
            else:
                # Fim da lista
                if loop_enabled:
                    current_play_index = 0 # Reinicia
                else:
                    current_state = STATE_IDLE
                    bot.arm.go_to_home_pose(moving_time=1.0)

        cv2.imshow('IK Control', frame)
        if cv2.waitKey(5) & 0xFF == ord('q'): break

    bot.arm.go_to_sleep_pose(moving_time=1.0)
    video.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()