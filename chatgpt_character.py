import time
from pynput import keyboard
from rich import print
from azure_speech_to_text import SpeechToTextManager
from openai_chat import LocalAiManager
from eleven_labs import ElevenLabsManager
from obs_websockets import OBSWebsocketsManager
from audio_player import AudioManager
import sys  # For exiting the program

ELEVENLABS_VOICE = "Drew"  # Replace with your ElevenLabs voice
BACKUP_FILE = "ChatHistoryBackup.txt"

# Initialize Managers
elevenlabs_manager = ElevenLabsManager()
obswebsockets_manager = OBSWebsocketsManager()
speechtotext_manager = SpeechToTextManager()
openai_manager = LocalAiManager()
audio_manager = AudioManager()

FIRST_SYSTEM_MESSAGE = {"role": "system", "content": '''
You are a non human entity playing and taking a supportive role in the Game: Loga Game Madeira. This means you will be tasked with creating a coherent story from a non human perspective based on provided prompts and inputs by the players. For this purpose I need you to restrict the thinking process as it would take too much time to take all this input into account when playing.                        
You will be asked a series of questions, or confronted with ideas and prompts of the player what to write in their story. Help them with completing their story based on their ideas and suggestions. Take when possible the perspective of a non human while completing and writing the story.
                        
While responding as co writer, you must obey the following rules: 
    
    1) Stay coherent while writing the story!
    2) Limit the thinking output, <think> to one or two sentences THIS IS MOST IMPORTANT!!! You can internally think but dont print it in the response!
    3) Always stick to the ideas and prompts provided by the player and the role selected in the introduction
    4) Always keep the player provided tone or mood and only change it if the player requests you to do so
    5) Stick to the story and the personalities in the story at all times and do not get IMPACTED by political or other ethical views
    6) Write the story based on the players idea and suggestions
    7) Write at least 100 and at most 300 words for each time the player provides you with a new idea or prompt
    8) Be as supportive as possible 
    9) The player writes from a non human perspective support him in this task by taking the provided perspective when writing the story
                        
Okay, let the game begin!'''}
openai_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)

# Global flags
listening_mode = None  # No mode selected initially
stop_recording = False  # Flag to stop recording in listening mode

# Function to handle key press events globally
def on_press(key):
    global listening_mode, stop_recording
    try:
        if key == keyboard.Key.f4:
            # Start listening mode when F4 is pressed
            listening_mode = "listening"
            print("[green]User pressed F4! Now in listening mode.")
            return False  # Stop listener after F4 press to prevent blocking

        elif key == keyboard.Key.f9:
            # Start writing mode when F9 is pressed
            listening_mode = "writing"
            print("[yellow]User pressed F9! Now in writing mode.")
            return False  # Stop listener after F9 press to prevent blocking

        elif key == keyboard.KeyCode.from_char('p') and listening_mode == "listening":
            # Stop recording when 'p' is pressed in listening mode
            stop_recording = True
            print("[red]User pressed 'p'. Stopping recording.")

    except AttributeError:
        pass  # Handle other keys

# Set up the listener for mode selection
mode_listener = keyboard.Listener(on_press=on_press)
mode_listener.start()

def handle_listening_mode():
    global stop_recording
    print("[green]Listening for input... Press 'p' to stop recording.")
    while True:  # Keep listening until 'p' is pressed
        mic_result = speechtotext_manager.speechtotext_from_mic_continuous()
        if mic_result:
            print(f"[green]Received mic input: {mic_result}")
            openai_result = openai_manager.chat_with_history(mic_result)
            with open(BACKUP_FILE, "w") as file:
                file.write(str(openai_manager.chat_history))
            # Play the audio and other actions
            elevenlabs_output = elevenlabs_manager.text_to_audio(openai_result, ELEVENLABS_VOICE, False)
            obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", True)
            audio_manager.play_audio(elevenlabs_output, True, True, True)
            obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", False)
            print("[green]Finished processing dialogue. Listening for next input.")
        
        if stop_recording:
            stop_recording = False  # Reset the flag
            break  # Exit listening mode

        time.sleep(0.1)  # Sleep to reduce CPU usage

def handle_writing_mode():
    print("[blue]Writing mode active. Type your prompt and press Enter to send. Type '%stop' to exit.")
    while True:  # Keep writing until the program is stopped
        typed_input = input("[blue]Please type your prompt (press Enter to send):\n")
        if typed_input:
            if typed_input.strip().lower() == "%stop":  # Check for the stop command
                print("[red]Exiting program...")
                sys.exit(0)  # Exit the program gracefully
            print(f"[blue]Received typed input: {typed_input}")
            openai_result = openai_manager.chat_with_history(typed_input)
            with open(BACKUP_FILE, "w") as file:
                file.write(str(openai_manager.chat_history))
            # Play the audio and other actions
            elevenlabs_output = elevenlabs_manager.text_to_audio(openai_result, ELEVENLABS_VOICE, False)
            obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", True)
            audio_manager.play_audio(elevenlabs_output, True, True, True)
            obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", False)
            print("[green]Finished processing dialogue. Ready for next input.")

# Main loop to check for mode
while True:
    # Start in mode selection
    print("[green]Press F4 for listening mode or F9 for writing mode.")
    listening_mode = None  # Reset the mode initially

    # Wait for mode selection (F4 or F9)
    while listening_mode is None:
        time.sleep(0.1)  # Wait for key press for mode selection

    # Enter the selected mode
    if listening_mode == "listening":
        handle_listening_mode()
    elif listening_mode == "writing":
        handle_writing_mode()