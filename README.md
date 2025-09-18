# Real-Time Hand Gesture Control of a Robotic Arm with Programmable Motion Memory

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This project presents a system for controlling a robotic arm using real-time hand gestures captured by a standard webcam. It features a "Programming by Demonstration" module, allowing an operator to intuitively teach a task to the robot, which can then be stored and replayed autonomously. This approach significantly reduces the complexity associated with traditional robot programming, making automation more accessible and flexible.

## 🎥 Demonstration

A video demonstrating the system's functionality and the "pick and place" validation test is available on YouTube.

<a href="https://www.youtube.com/watch?v=Zf2bXpjEzRs" target="_blank">
 <img src="http://img.youtube.com/vi/Zf2bXpjEzRs/hqdefault.jpg" alt="Watch the video" width="480" border="10" />
</a>

## ✨ Key Features

- **Real-Time Gesture Control:** Manipulate the robot's joints and gripper using natural hand movements captured by a single RGB camera.
- **Programming by Demonstration:** Easily record a sequence of movements by pressing a key and have the robot replay it autonomously.
- **Low-Cost and Accessible:** Requires only a standard webcam, with no need for specialized sensors or costly hardware like data gloves.
- **Intuitive Interface:** Bridges the gap between human intention and robotic execution, simplifying complex tasks.

## 🛠️ Tech Stack & Hardware

### Software
- **Language:** Python
- **Operating System:** Ubuntu 20.04.6 LTS
- **Robotics Middleware:** Robot Operating System (ROS)
- **Core Libraries:**
    - **MediaPipe (v0.10.11):** For real-time hand landmark detection.
    - **OpenCV (v4.11.0):** For image acquisition and processing.
    - **NumPy (v1.24.4):** For numerical operations and coordinate manipulation.

### Hardware
- **Robotic Arm:** Interbotix PincherX-100 (4-DOF + gripper) 
- **Camera:** A standard RGB webcam
- **Computer:** Dell OptiPlex 5070 with Intel Core i7 9th Gen and 16 GB of RAM was used for development.

## ⚙️ Installation & Setup

### Prerequisites
- A working ROS environment.
- An **Interbotix PincherX-100** robotic arm, physically connected to the system.
  - *Note: This project was developed and tested specifically with the PincherX-100. Compatibility with other arms has not been verified.*

### Installation Steps
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/your-repository.git](https://github.com/your-username/your-repository.git)
    cd your-repository
    ```

2.  **Setup ROS & Interbotix Packages:**
    This project relies on the `interbotix_ros_manipulators` package. Please follow the official installation guide to set up the arm drivers and necessary configurations:
    - [Interbotix XS-Series Arms Setup Guide](https://docs.trossenrobotics.com/interbotix_xsarms_docs/index.html)

3.  **Install Python dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
    *A `requirements.txt` file should contain:*
    ```
    opencv-python==4.11.0
    mediapipe==0.10.11
    numpy==1.24.4
    ```

## 🚀 Usage

1.  **Launch the ROS nodes:** Ensure the PincherX-100 is connected and powered on. In a terminal, launch the Interbotix driver. The command is typically:
    ```bash
    roslaunch interbotix_xsarm_control xsarm_control.launch robot_model:=px100
    ```

2.  **Navigate to the script directory:** The control script is located within the Interbotix examples folder. Open a new terminal and navigate to it:
    ```bash
    cd /path/to/your/catkin_ws/src/interbotix_ros_manipulators/interbotix_ros_xsarms/examples/python_demos
    ```
    *(Replace `/path/to/your/catkin_ws` with the actual path to your ROS workspace)*

3.  **Run the gesture control script:**
    ```bash
    python your_main_script_name.py
    ```

4.  **In-App Controls:**
    - **'R' key:** Press to start/stop **Recording** a movement sequence.
    - **'P' key:** Press to **Play/Stop** the last recorded sequence.
    - **'L' key:** Press to toggle **Loop Playback** of the recorded sequence.

## 📊 Results

The system was validated through 50 consecutive "pick and place" trials.
- **Success Rate:** Achieved a **98% success rate** (49 out of 50 successful trials).
- **Precision & Repeatability:** Demonstrated excellent consistency with a mean cycle time of **13.35 seconds** and a very low standard deviation of only **0.0126 seconds**.

## 🧑‍💻 Authors

- **Daniel Giraldi Michels**
- **Davi Giraldi Michels**
- **Lucas Alexandre Zick**
- **Dieisson Martinelli**
- **André Schneider de Oliveira**
- **Vivian Cremer Kalempa**

## 🙏 Acknowledgements

This project is supported by the National Council for Scientific and Technological Development (CNPq), the Fund for Scientific and Technological Development (FNDCT), the Ministry of Science Technology and Innovations (MCTI) of Brazil, CAPES, the Araucaria Foundation, the General Superintendence of Science, Technology and Higher Education (SETI), and NAPI Robotics.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.