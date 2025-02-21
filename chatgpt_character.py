import time
from pynput import keyboard
from rich import print
from azure_speech_to_text import SpeechToTextManager
from openai_chat import LocalAiManager
from eleven_labs import ElevenLabsManager
from obs_websockets import OBSWebsocketsManager
from audio_player import AudioManager
import sys
import os
import PyPDF2

ELEVENLABS_VOICE = "Drew"  # Replace with your ElevenLabs voice
BACKUP_FILE = "ChatHistoryBackup.txt"

# Function to read txt or PDF
def read_system_message(txt_file_path, pdf_file_path):
    # Try reading from the text file first
    if os.path.exists(txt_file_path):
        print(f"Reading from text file: {txt_file_path}")
        return read_system_message_from_txt(txt_file_path)
    # If the text file is not found, try reading from the PDF file
    elif os.path.exists(pdf_file_path):
        print(f"Text file not found. Reading from PDF file: {pdf_file_path}")
        return read_system_message_from_pdf(pdf_file_path)
    # If neither file is found, return None
    else:
        print(f"Error: Neither '{txt_file_path}' nor '{pdf_file_path}' found.")
        return None

def read_system_message_from_txt(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            print(f"Content read from text file: {content}")  # Debug print
        return {"role": "system", "content": content}
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

def read_system_message_from_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            content = ""
            for page in reader.pages:
                content += page.extract_text()
            print(f"Content read from PDF file: {content}")  # Debug print
        return {"role": "system", "content": content}
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

# Initialize Managers
elevenlabs_manager = ElevenLabsManager()
obswebsockets_manager = OBSWebsocketsManager()
speechtotext_manager = SpeechToTextManager()
openai_manager = LocalAiManager()
audio_manager = AudioManager()

# Read the system message from a file (try .txt first, then .pdf)
FIRST_SYSTEM_MESSAGE = read_system_message("system_message.txt", "system_message.pdf")
if FIRST_SYSTEM_MESSAGE:
    openai_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)
else:
    print("Error: Could not load system message. Using default.")  # Debug print
    FIRST_SYSTEM_MESSAGE = {"role": "system", "content": "Default system message."}
    openai_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)

# Debug print to check the chat history
print("Current chat history:", openai_manager.chat_history)

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
            audio_manager.play_audio(elevenlabs_output, True, False, True)
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