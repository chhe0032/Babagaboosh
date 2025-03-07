import time
from pynput import keyboard
from pydub import AudioSegment
from rich import print
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
from whisper_speech_to_text import SpeechToTextManager
from openai_chat import LocalAiManager
from eleven_labs import ElevenLabsManager
from obs_websockets import OBSWebsocketsManager
from audio_player import AudioManager
import sys
import os
import PyPDF2
import threading
import glob
import uuid

# Initialize Flask app
app = Flask(__name__)

# Initialize Managers
elevenlabs_manager = ElevenLabsManager()
obswebsockets_manager = OBSWebsocketsManager()
speechtotext_manager = SpeechToTextManager()
openai_manager = LocalAiManager()
audio_manager = AudioManager()

chat_messages = []

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/get_system_messages', methods=['GET'])
def get_system_messages():
    """Retrieve all available system message files from the specified folder."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        system_messages_dir = os.path.join(base_dir, "system_messages") 
        
        # Check if the directory exists
        if not os.path.isdir(system_messages_dir):
            print(f"System messages directory not found: {system_messages_dir}")
            return jsonify({"system_messages": [], "error": "System messages directory not found"}), 200
        
        # Get all .txt and .pdf files in the directory
        txt_files = [f for f in os.listdir(system_messages_dir) if f.endswith('.txt')]
        pdf_files = [f for f in os.listdir(system_messages_dir) if f.endswith('.pdf')]
        
        # Process txt files
        available_files = []
        for filename in txt_files:
            available_files.append(filename)
        
        # Process pdf files
        for pdf_filename in pdf_files:
            txt_filename = pdf_filename.replace(".pdf", ".txt")
            if txt_filename not in available_files:
                available_files.append(txt_filename)  
        
 
        available_files.sort()
        
        
        return jsonify({"system_messages": available_files}), 200
    except Exception as e:
        print(f"Error fetching system message files: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/update_system_message', methods=['POST'])
def update_system_message():
    data = request.get_json()
    selected_file = data.get('file')

    if not selected_file:
        return jsonify({"error": "No file selected"}), 400

    # Get the path to the system messages folder
    base_dir = os.path.dirname(os.path.abspath(__file__))
    system_messages_dir = os.path.join(base_dir, "system_messages")  # Change to your folder name
    
    # Create the full path to the selected file
    txt_file_path = os.path.join(system_messages_dir, selected_file)
    pdf_file_path = os.path.join(system_messages_dir, selected_file.replace(".txt", ".pdf"))

    # Read the selected system message file
    system_message = read_system_message(txt_file_path, pdf_file_path)

    if not system_message:
        return jsonify({"error": f"Failed to read system message file: {selected_file}"}), 400

    # Update the chat history with the new system message
    openai_manager.chat_history = [system_message]  # Replace the entire chat history
    
    print(f"System message updated successfully with: {selected_file}")

    return jsonify({"message": "System message updated successfully"}), 200

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory("/tmp", filename, mimetype="audio/mpeg") 

@app.route('/chat_history', methods=['GET'])
def get_chat_history():
    if openai_manager:
        return jsonify(openai_manager.chat_history)
    else:
        return jsonify({"error": "OpenAI manager not initialized"}), 500

@app.route('/process_input', methods=['POST'])
def process_input():
    # Get the user prompt from the request
    data = request.get_json()
    user_prompt = data.get('prompt', '').strip()
    use_browser_audio = data.get('use_browser_audio', 'false').lower() == 'true'

    # If there's no prompt, return an error
    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400

    try:
        # Get the AI response from the LLM
        openai_result = openai_manager.chat_with_history(user_prompt)
        ai_response = openai_result

        # Get the audio file path from ElevenLabsManager
        audio_file_path_from_tts = elevenlabs_manager.text_to_audio(ai_response, ELEVENLABS_VOICE, True)
        
        # Use the file path directly (do not convert to bytes)
        audio_filename = f"response_{uuid.uuid4()}.mp3"
        audio_path = os.path.join("/tmp", audio_filename)
        
        # Copy the generated file to /tmp so that it can be served to the browser
        with open(audio_file_path_from_tts, "rb") as src, open(audio_path, "wb") as dst:
            dst.write(src.read())
        
        with open(BACKUP_FILE, "w") as file:
            file.write(str(openai_manager.chat_history))
            
        # Update OBS visibility before playback
        obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", True)

        if not use_browser_audio:
            print("Playing audio locally...")
            # Local playback using AudioManager
            audio_manager.play_audio(audio_path, True, True, True)
        
        # Reset OBS visibility after playback
        obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", False)
        
        # Prepare the response data with the audio URL for browser playback
        response_data = {
            "response": ai_response,
            "audio_url": f"/audio/{audio_filename}"
        }
        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/process_audio', methods=['POST'])
def process_audio():
    try:
        # Check if an audio file was uploaded
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        use_browser_audio = request.form.get('use_browser_audio', 'false').lower() == 'true'
        
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({"error": "No valid audio file provided"}), 400
        
        received_audio_path = "/tmp/received_audio.webm"
        audio_file.save(received_audio_path)
        print(f"Received audio file: {audio_file.filename}")

        try:
            # Convert WebM to WAV (ensure ffmpeg is installed)
            wav_path = "/tmp/converted_audio.wav"
            audio = AudioSegment.from_file(received_audio_path)
            audio.export(wav_path, format="wav")
        except Exception as e:
            print(f"Error converting audio: {e}")
            return jsonify({"error": f"Failed to convert audio: {e}"}), 400

        # Now process the audio file (transcription)
        transcription = speechtotext_manager.speechtotext_from_file(wav_path)
        
        if not transcription:
            print("Transcription failed.")
            return jsonify({"error": "Failed to transcribe audio"}), 400

        print(f"Transcription: {transcription}")

        # Generate a unique filename for the response audio
        audio_filename = f"response_{uuid.uuid4()}.mp3"
        response_audio_path = os.path.join("/tmp", audio_filename)

        # Process the transcribed text
        openai_result = openai_manager.chat_with_history(transcription)
        ai_response = openai_result  # The text response from the LLM

        # Convert the LLM response to speech
        audio_file_path_from_tts = elevenlabs_manager.text_to_audio(ai_response, ELEVENLABS_VOICE, True)

        if not audio_file_path_from_tts:
            return jsonify({"error": "Failed to generate speech audio"}), 500

        # Copy the generated file to /tmp so that it can be served to the browser
        with open(audio_file_path_from_tts, "rb") as src, open(response_audio_path, "wb") as dst:
            dst.write(src.read())

        with open(BACKUP_FILE, "w") as backup_file:
            backup_file.write(str(openai_manager.chat_history))

        # Update OBS visibility
        obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", True)

        if not use_browser_audio:
            print("Playing audio locally...")
            # Local playback
            audio_manager.play_audio(response_audio_path, True, True, True)
        
        # Reset OBS visibility
        obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", False)

        # Return the response including the audio URL
        response_data = {
            "transcribed_text": transcription,
            "response": ai_response,
            "audio_url": f"/audio/{audio_filename}"
        }

        # Clean up temporary input files
        os.remove(received_audio_path)
        os.remove(wav_path)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error in processing audio: {e}")
        return jsonify({"error": str(e)}), 500


#################TWITCH#########################

app.route('/receive_message', methods=['POST'])
def receive_message():
    data = request.json
    if 'message' in data:
        chat_messages.append(data['message'])
        return jsonify({"status": "success", "received": data['message']})
    return jsonify({"status": "error", "message": "No message received"}), 400

@app.route('/messages', methods=['GET'])
def get_messages():
    return jsonify(chat_messages)

###############################################

#TEST PLAYING AUDIO
@app.route('/play_audio', methods=['GET'])
def play_audio():
    try:
        audio_file_path = "/home/iti/LLM_Agent/Agent01/Babagaboosh/TestAudio_Speech.wav"

        # Ensure request is correct
        if request.method != 'GET':
            return jsonify({"error": "Invalid request method"}), 405
        
        return send_file(audio_file_path, mimetype="audio/wav")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Function to run the Flask app in a separate thread
def run_flask_app():
    app.run(host="0.0.0.0", port=5000)

# --- Main Code ---
def main():
    global elevenlabs_manager, obswebsockets_manager, speechtotext_manager, openai_manager, audio_manager

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


# Initialize the chat history with the default system message
FIRST_SYSTEM_MESSAGE = read_system_message("system_message.txt", "system_message.pdf")
if FIRST_SYSTEM_MESSAGE:
    openai_manager.chat_history = [FIRST_SYSTEM_MESSAGE]
else:
    print("Error: Could not load system message. Using default.")
    FIRST_SYSTEM_MESSAGE = {"role": "system", "content": "Default system message."}
    openai_manager.chat_history = [FIRST_SYSTEM_MESSAGE]

# Global flags
listening_mode = None
stop_recording = False

def on_press(key):
    global listening_mode
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
            audio_manager.play_audio(elevenlabs_output, True, True, True)
            obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", False)
            print("[green]Finished processing dialogue. Listening for next input.")

        if stop_recording:
            stop_recording = True  # Reset the flag
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

# Start the Flask app in a separate thread
flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True  # Allow the program to exit even if Flask is running
flask_thread.start()


# Function to clean up old audio files
def cleanup_old_audio_files(directory="/tmp", max_age_seconds=3600):
    """Delete audio files older than `max_age_seconds`."""
    current_time = time.time()
    for filepath in glob.glob(os.path.join(directory, "*.mp3")):
        file_age = current_time - os.path.getmtime(filepath)
        if file_age > max_age_seconds:
            os.remove(filepath)
            print(f"Deleted old audio file: {filepath}")

if __name__ == "__main__":
    main()
    cleanup_old_audio_files()

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


