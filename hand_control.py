#!/usr/bin/env python3
from interbotix_xs_modules.arm import InterbotixManipulatorXS
import mediapipe as mp
import cv2
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import time

# --- Estados do Programa ---
STATE_IDLE = 0      # Controle normal pela mão, não gravando nem reproduzindo
STATE_RECORDING = 1 # Gravando os movimentos da mão/robô
STATE_PLAYING = 2   # Reproduzindo os movimentos gravados

# --- Variáveis Globais de Controle ---
current_state = STATE_IDLE
recorded_movements = []  # Lista para armazenar os movimentos gravados [{joints: [], gripper_closed: bool}]
current_play_index = 0   # Índice para saber qual movimento reproduzir durante o playback
loop_playback = False    # Controla se a reprodução deve ser em loop

# --- Configurações da Câmera e MediaPipe ---
video = cv2.VideoCapture(0)
width = 640
height = 480
video.set(cv2.CAP_PROP_FRAME_WIDTH, width)
video.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands
hand = mp_hands.Hands(max_num_hands=1)

base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1)
detector = vision.HandLandmarker.create_from_options(options)

# Definições dos pontos dos dedos (landmarks)
thumb_points = [1, 2, 3, 4]
index_points = [5, 6, 7, 8]
middle_points = [9, 10, 11, 12]
ring_points = [13, 14, 15, 16]
pinky_points = [17, 18, 19, 20]

# Inicialização do Robô
bot = InterbotixManipulatorXS("px100", "arm", "gripper")

def map_hand_to_robot(value, max, min, targMax, targMin):
    """
    Mapeia um valor de uma faixa de origem para uma faixa de destino.
    Nota: A ordem original dos seus argumentos era (value, max, min, targMax, targMin).
    Renomeei para clareza: src_max, src_min, dest_max, dest_min.
    A fórmula original foi mantida, assumindo que 'max' era src_max e 'min' era src_min.
    """
    if max == min:
        return targMin
    return ((value - min) / (max - min)) * (targMax - targMin) + (targMin)


def main():
    global current_state, recorded_movements, current_play_index, loop_playback

    if not video.isOpened():
        print("ERRO: Impossível abrir a câmera.")
        return
    else:
        print("Indo para a posição inicial (Home)...")
        bot.arm.go_to_home_pose(moving_time=1.5) # Aumentar tempo para garantir que chegue
        bot.gripper.open(0) # Abrir a garra inicialmente

        last_known_frame = np.zeros((height, width, 3), dtype=np.uint8) # Para exibir durante a reprodução

        print("\n--- Controles ---")
        print(" 'R': Iniciar/Parar Gravação de Movimentos")
        print(" 'P': Iniciar/Parar Reprodução dos Movimentos Gravados")
        print(" 'L': Ativar/Desativar Loop da Reprodução")
        print(" 'Q': Sair do Programa")
        print("-----------------\n")

        while True:
            success, frame = video.read()
            key = cv2.waitKey(15) & 0xFF # Aumentado para melhor responsividade das teclas

            if key == ord('q'):
                print("Saindo...")
                bot.arm.go_to_sleep_pose(moving_time=1.5)
                break
            elif key == ord('r'):
                if current_state == STATE_IDLE:
                    current_state = STATE_RECORDING
                    recorded_movements = []  # Limpa gravações anteriores ao iniciar uma nova
                    current_play_index = 0
                    print("--- INICIANDO GRAVAÇÃO DE MOVIMENTOS ---")
                elif current_state == STATE_RECORDING:
                    current_state = STATE_IDLE
                    if len(recorded_movements) > 0:
                        print(f"--- GRAVAÇÃO FINALIZADA: {len(recorded_movements)} movimentos gravados. ---")
                    else:
                        print("--- GRAVAÇÃO FINALIZADA: Nenhum movimento foi gravado. ---")
                elif current_state == STATE_PLAYING:
                    print("AVISO: Pare a reprodução ('P') antes de iniciar uma nova gravação.")


            elif key == ord('p'):
                if current_state != STATE_PLAYING: # Se não estiver reproduzindo
                    if len(recorded_movements) > 0:
                        if current_state == STATE_RECORDING: # Para a gravação se estiver gravando
                            current_state = STATE_IDLE # Volta para IDLE primeiro
                            print(f"--- GRAVAÇÃO INTERROMPIDA. {len(recorded_movements)} movimentos gravados. ---")
                        
                        current_state = STATE_PLAYING
                        current_play_index = 0 # Começa do início
                        print("--- INICIANDO REPRODUÇÃO DE MOVIMENTOS ---")
                    else:
                        print("AVISO: Nenhum movimento gravado para reproduzir. Grave movimentos primeiro ('R').")
                elif current_state == STATE_PLAYING: # Se já estiver reproduzindo, para
                    current_state = STATE_IDLE
                    print("--- REPRODUÇÃO PARADA PELO USUÁRIO ---")
            
            elif key == ord('l'):
                if len(recorded_movements) > 0: # Só faz sentido se tiver algo gravado
                    loop_playback = not loop_playback
                    print(f"--- REPRODUÇÃO EM LOOP: {'ATIVADO' if loop_playback else 'DESATIVADO'} ---")
                else:
                    print("AVISO: Grave movimentos ('R') antes de ativar o loop de reprodução.")

            display_frame_source = None

            # --- 2. Lógica Principal baseada no Estado Atual ---
            if current_state == STATE_PLAYING:
                if len(recorded_movements) > 0:
                    if current_play_index == 0:
                        movement_to_play = recorded_movements[current_play_index]
                        
                        bot.gripper.open(0) # Abrir a garra inicialmente
                        bot.arm.go_to_home_pose(1)

                        bot.arm.set_joint_positions(
                            movement_to_play['joints'], 
                            moving_time=1.5, # Tempo de movimento para cada passo da reprodução
                            blocking=True    
                        )
                        current_play_index += 1

                    elif current_play_index < len(recorded_movements):
                        movement_to_play = recorded_movements[current_play_index]
                        
                        # Feedback no console sobre o movimento sendo reproduzido
                        # print(f"Reproduzindo passo {current_play_index + 1}/{len(recorded_movements)}: Joints={movement_to_play['joints']}, GripperClosed={movement_to_play['gripper_closed']}")

                        # Envia posições das juntas para o robô
                        # Usar blocking=True para garantir que um movimento termine antes do próximo
                        # Ajuste moving_time para controlar a velocidade da reprodução
                        bot.arm.set_joint_positions(
                            movement_to_play['joints'], 
                            moving_time=0.5, # Tempo de movimento para cada passo da reprodução
                            blocking=False  
                        )
                        
                        # Controla a garra
                        if movement_to_play['gripper_closed']:
                            bot.gripper.close(0) # Tempo pequeno para ação da garra
                        else:
                            bot.gripper.open(0)
                        
                        current_play_index += 1
                        # time.sleep(0.1) # Pausa opcional se blocking=False ou para dar um respiro
                    
                    elif loop_playback: # Chegou ao fim da lista e o loop está ativo
                        current_play_index = 0 # Reinicia do primeiro movimento
                        print("Reiniciando reprodução em loop...")
                    else: # Terminou a reprodução (sem loop)
                        current_state = STATE_IDLE
                        print("--- FIM DA REPRODUÇÃO ---")
                else: # Não deveria acontecer se a lógica da tecla 'p' estiver correta
                    current_state = STATE_IDLE
                    print("AVISO: Tentativa de reprodução sem movimentos gravados. Voltando para Ocioso.")
                
                # Durante a reprodução, usamos o último frame conhecido para exibição
                if last_known_frame is not None:
                    display_frame_source = last_known_frame.copy()
                else: # Caso nenhum frame tenha sido capturado ainda (improvável aqui)
                    display_frame_source = np.zeros((height, width, 3), dtype=np.uint8)

            # Se NÃO estiver reproduzindo (está Ocioso ou Gravando)
            elif current_state == STATE_IDLE or current_state == STATE_RECORDING:
                if success:
                    RGB_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=RGB_frame)
                    result = hand.process(RGB_frame)
                    if result.multi_hand_landmarks:
                        thumb = []
                        index = []
                        middle = []
                        ring = []
                        pinky = []
                        for hand_landmark in result.multi_hand_landmarks:
                            for i in thumb_points:
                                x = int(hand_landmark.landmark[i].x * width)
                                y = int(hand_landmark.landmark[i].y * height)
                                z = int(hand_landmark.landmark[i].z * 1000)
                                thumb.append([x, y, z])
                            for i in index_points:
                                x = int(hand_landmark.landmark[i].x * width)
                                y = int(hand_landmark.landmark[i].y * height)
                                z = int(hand_landmark.landmark[i].z * 1000)
                                index.append([x, y, z])
                            for i in middle_points:
                                x = int(hand_landmark.landmark[i].x * width)
                                y = int(hand_landmark.landmark[i].y * height)
                                z = int(hand_landmark.landmark[i].z * 2000)
                                middle.append([x, y, z])
                            for i in ring_points:
                                x = int(hand_landmark.landmark[i].x * width)
                                y = int(hand_landmark.landmark[i].y * height)
                                z = int(hand_landmark.landmark[i].z * 1000)
                                ring.append([x, y, z])
                            for i in pinky_points:
                                x = int(hand_landmark.landmark[i].x * width)
                                y = int(hand_landmark.landmark[i].y * height)
                                z = int(hand_landmark.landmark[i].z * 1000)
                                pinky.append([x, y, z])
                            wrist = np.array([
                                    int(hand_landmark.landmark[0].x * width),
                                    int(hand_landmark.landmark[0].y * height),
                                    int(hand_landmark.landmark[0].z * 1000)
                                ])
                            
                            
                            centerX = int((wrist[0] + middle[0][0]) / 2)
                            centerY = int((wrist[1] + middle[0][1]) / 2)

                            prof = np.linalg.norm(middle[0] - wrist) # Distância do pulso com o começo do dedo do meio para calcular profundidade
                            raio = map_hand_to_robot(prof, 150, 60, 15, 1)
                            if raio > 1:
                                cv2.circle(frame, (centerX, centerY), int(raio), (0, 0, 255), 3) # Centro da mão que controla o robô
                            else:
                                cv2.circle(frame, (centerX, centerY), 1, (0, 0, 255), 3) # Centro da mão que controla o robô


                            joints = bot.arm.get_joint_commands()
                            jointX = int(map_hand_to_robot(joints[0], -3, 3, 0, width))
                            jointY = int(map_hand_to_robot(joints[2], 1.6, -2.1, height, 0))

                            jointProf = map_hand_to_robot(joints[1], 1.8, -1.9, 15, 1)
                            cv2.circle(frame, (jointX, jointY), int(jointProf), (0, 0, 0), 3)

                            # mp_drawing.draw_landmarks(frame, hand_landmark, mp_hands.HAND_CONNECTIONS)
                            if pinky[3][1] < pinky[0][1] or ring[3][1] < ring[0][1] or middle[3][1] < middle[0][1]:
                                p1 = np.array(thumb[3][:2])
                                p2 = np.array(index[3][:2])
                                distancia_dedos = np.linalg.norm(p1 - p2)
                                cv2.line(frame, p1, p2, (0, 0, 0), 3) # Linha da pinça

                                

                                waist =  map_hand_to_robot(centerX, 0, width, -3.14, 3.14)
                                shoulder = map_hand_to_robot(prof, 170, 60, 1.8, -1.9)
                                elbow = map_hand_to_robot(centerY, height, 0, 1.6, -2.1)
                                wrist_angle = map_hand_to_robot(middle[0][2], -150, 100, 2.10, -1.7) 

                                current_joint_positions = [waist, shoulder, elbow, 0.0]
                                joint_positions = [waist,
                                                    shoulder,
                                                    elbow,
                                                    0
                                                    ]
                                bot.arm.set_joint_positions(current_joint_positions, 0.3 , blocking=False)

                                gripper_is_closed_cmd = (distancia_dedos < 35) # Ajuste o limiar da distância se necessário
                                if gripper_is_closed_cmd:
                                    cv2.circle(frame, (p1[0], p1[1]), 3, (0, 0, 255), 3)
                                    cv2.circle(frame, (p2[0], p2[1]), 3, (0, 0, 255), 3)
                                    bot.gripper.close(0) # Tempo de movimento para a garra
                                else:
                                    bot.gripper.open(0)
                                

                                if current_state == STATE_RECORDING:
                                    recorded_movements.append({
                                        'joints': list(current_joint_positions),  # Salva uma cópia da lista de juntas
                                        'gripper_closed': gripper_is_closed_cmd
                                    })
                        


                    
            cv2.imshow("capture image", cv2.flip(frame, 1))
            # bot.arm.go_to_home_pose()
            # bot.arm.go_to_home_pose()
            # bot.arm.go_to_sleep_pose()

if __name__=='__main__':
    main()
