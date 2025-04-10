import time
from pynput import keyboard
from pydub import AudioSegment
from rich import print
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
from threading import Lock
from whisper_speech_to_text import SpeechToTextManager
from openai_chat import LocalAiManager
from eleven_labs import ElevenLabsManager
from obs_websockets import OBSWebsocketsManager
from audio_player import AudioManager
from emoji import demojize
import sys
import os
import PyPDF2
import threading
import glob
import uuid
import socket
import datetime
import base64


# Initialize Flask app
app = Flask(__name__)
app.filtered_messages_lock = Lock()
app.filtered_messages_global = []

# Initialize Managers
elevenlabs_manager = ElevenLabsManager()
obswebsockets_manager = OBSWebsocketsManager()
speechtotext_manager = SpeechToTextManager()
openai_manager = LocalAiManager()
audio_manager = AudioManager()

chat_messages = []
token = 'oauth:'
nickname = 'InFernal_ger'
token = 'oauth:ox2ooxr547y73cilummzywju7mtu92'
channel = '#ClaudePlaysPokemon'


#################TWITCH#########################

def connect_to_twitch(token, nickname, channel):
    try:
        print(f"Attempting to connect to Twitch IRC as {nickname}...")
        sock = socket.socket()
        sock.connect(('irc.chat.twitch.tv', 6667))
        sock.send(f"PASS {token}\n".encode('utf-8'))
        sock.send(f"NICK {nickname}\n".encode('utf-8'))
        sock.send(f"JOIN {channel}\n".encode('utf-8'))
        print(f"Successfully connected to channel {channel}")
        return sock
    except Exception as e:
        print(f"Failed to connect to Twitch: {e}")
        raise

def process_twitch_message(message):
    print(f"Raw message received: {message}")  # Debug raw message
    
    # Skip if not a PRIVMSG (user message)
    if 'PRIVMSG' not in message:
        print("Not a PRIVMSG, skipping")
        return None, None
        
    try:
        # Extract username
        username = message.split('!', 1)[0][1:]
        # Extract message content
        message_content = message.split('PRIVMSG', 1)[1].split(':', 1)[1].strip()
        print(f"Extracted message - User: {username}, Content: {message_content}")
        return username, message_content
    except IndexError as e:
        print(f"Error parsing message: {e}")
        return None, None

def should_process_message(message, username):
    if not message or not username:
        print("Empty message or username")
        return False
        
    # Demojize the message before checking conditions
    clean_message = demojize(message)
    print(f"Checking if should process message from {username}: {clean_message}")
    
    # Ignore messages starting with ! (bot commands)
    if clean_message.startswith('!'):
        print("Ignoring bot command")
        return False
    if clean_message.__contains__('Hitler'):
        return False
    if username.lower() == 'nightbot':
        print("Ignoring Nightbot")
        return False
    if username.lower() == 'moobot':
        print("Ignoring Moobot")
        return False
    # Ignore very long messages
    if len(clean_message) > 200:
        print("Message too long")
        return False
        
    print("Message approved for processing")
    return True

def store_twitch_message(username, message):
    global collected_twitch_messages
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {username}: {demojize(message)}"  # Demojize only for log file
        
        # Always log formatted message to file
        with open("twitch_messages.txt", "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
            print(f"Stored message to file: {log_entry}")

    except Exception as e:
        print(f"Error storing message: {e}")

def listen_to_twitch(sock):
    print("Starting Twitch listener...")
    while True:
        try:
            resp = sock.recv(2048).decode('utf-8')
            
            if resp.startswith('PING'):
                sock.send(f"PONG {resp.split()[1]}\n".encode('utf-8'))
                continue
                
            if not resp.strip():
                continue
                
            for line in resp.split('\r\n'):
                if not line.strip():
                    continue
                    
                username, message = process_twitch_message(line)
                if message and username and should_process_message(message, username):
                    store_twitch_message(username, message)
                    
        except Exception as e:
            print(f"Error in Twitch listener: {e}")
            time.sleep(5)


    global collected_twitch_messages
    collected_twitch_messages = []
    return jsonify({"status": "success"})

@app.route('/twitch_messages')
def get_twitch_messages():
    try:
        with open("twitch_messages.txt", "r", encoding="utf-8") as f:
            messages = f.readlines()
        return jsonify({"messages": messages})
    except FileNotFoundError:
        return jsonify({"error": "No messages file found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear_twitch_messages')
def clear_twitch_messages():
    try:
        open("twitch_messages.txt", "w").close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/filtered_twitch_messages')
def get_filtered_twitch_messages():
    try:
        # Get query parameters
        starts_with = request.args.get('starts_with')
        username_contains = request.args.get('username_contains')
        username_starts_with = request.args.get('username_starts_with')
        message_contains = request.args.get('message_contains')
        
        with open("twitch_messages.txt", "r", encoding="utf-8") as f:
            messages = f.readlines()
        
        filtered_messages = []
        new_filtered_global = []  # Local storage before committing to global

        for message in messages:
            try:
                # Parse the message format: [timestamp] username: message
                parts = message.split('] ', 1)
                if len(parts) < 2:
                    continue
                
                username_part = parts[1].split(': ', 1)
                if len(username_part) < 2:
                    continue
                
                username = username_part[0]
                message_content = username_part[1].strip()
                
                # Apply filters
                match = True
                
                if starts_with and not message_content.startswith(starts_with):
                    match = False
                if username_contains and username_contains.lower() not in username.lower():
                    match = False
                if username_starts_with and not username.lower().startswith(username_starts_with.lower()):
                    match = False
                if message_contains and message_contains.lower() not in message_content.lower():
                    match = False
                
                if match:
                    filtered_messages.append(message.strip())  # Full message for API
                    new_filtered_global.append({
                        'content': message_content,
                        'username': username,
                        'timestamp': parts[0][1:]  # Remove leading '['
                    })
                    
            except Exception as e:
                print(f"Error processing message line: {e}")
                continue
        
        # Thread-safe update of global storage
        with app.filtered_messages_lock:
            app.filtered_messages_global = new_filtered_global
        
        return jsonify({
            "status": "success",
            "filtered_messages_count": len(filtered_messages),
            "messages": filtered_messages
        })
        
    except FileNotFoundError:
        return jsonify({"error": "No messages file found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500



###############################################

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                              'favicon.ico', mimetype='image/vnd.microsoft.icon')

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
    try:
        # Handle both JSON (old) and FormData (new) requests
        if request.content_type == 'application/json':
            data = request.get_json()
            user_prompt = data.get('prompt', '').strip()
            image_data = None
            use_browser_audio = data.get('use_browser_audio', False)
        else:
            user_prompt = request.form.get('prompt', '').strip()
            use_browser_audio = request.form.get('use_browser_audio', 'false').lower() == 'true'
            
            # Handle image upload if present
            image_data = None
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file.filename != '':
                    # Convert image to base64 for Ollama
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')

        if not user_prompt and not image_data:
            return jsonify({"error": "No prompt or image provided"}), 400

        # Thread-safe access to filtered messages
        with app.filtered_messages_lock:
            context_messages = app.filtered_messages_global.copy()
        
        # Prepare context
        context = "\n".join(
            f"{msg['username']}: {msg['content']}" 
            for msg in context_messages[-10:]
        ) if context_messages else None

        # Prepare the payload for Ollama
        ollama_payload = {
            "prompt": user_prompt,
            "context": context,
            "image": image_data  
        }

        # Get the AI response from Ollama
        ollama_response = openai_manager.chat_with_history(ollama_payload)
        
        # Rest of your audio processing remains the same
        audio_file_path_from_tts = elevenlabs_manager.text_to_audio(ollama_response, ELEVENLABS_VOICE, False)
        audio_filename = f"response_{uuid.uuid4()}.mp3"
        audio_path = os.path.join("/tmp", audio_filename)
        
        with open(audio_file_path_from_tts, "rb") as src, open(audio_path, "wb") as dst:
            dst.write(src.read())
        
        with open(BACKUP_FILE, "w") as file:
            file.write(str(openai_manager.chat_history))
            
        # OBS visibility handling
        obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", True)
        if not use_browser_audio:
            audio_manager.play_audio(audio_path, True, True, True)
        obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Madeira Flag", False)
        
        return jsonify({
            "response": ollama_response,
            "audio_url": f"/audio/{audio_filename}",
            "context_message_count": len(context_messages)
        })

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

        # Thread-safe access to filtered messages
        with app.filtered_messages_lock:
            context_messages = app.filtered_messages_global.copy()
        
        # Prepare context from filtered messages (last 10 messages)
        context = "\n".join(
            f"{msg['username']}: {msg['content']}" 
            for msg in context_messages[-10:]
        ) if context_messages else None

        # Enhance the transcription with context if available
        enhanced_transcription = transcription
        if context:
            enhanced_transcription = f"{transcription}\n\nChat Context:\n{context}"
            print(f"Enhanced transcription with {len(context_messages)} context messages")

        # Process the transcribed text (with optional context)
        openai_result = openai_manager.chat_with_history(enhanced_transcription)
        ai_response = openai_result  # The text response from the LLM

        # Generate a unique filename for the response audio
        audio_filename = f"response_{uuid.uuid4()}.mp3"
        response_audio_path = os.path.join("/tmp", audio_filename)

        # Convert the LLM response to speech
        audio_file_path_from_tts = elevenlabs_manager.text_to_audio(ai_response, ELEVENLABS_VOICE, False)

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
            "audio_url": f"/audio/{audio_filename}",
            "context_message_count": len(context_messages) if context_messages else 0
        }

        # Clean up temporary input files
        os.remove(received_audio_path)
        os.remove(wav_path)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error in processing audio: {e}")
        return jsonify({"error": str(e)}), 500

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
    print("Error: Could not load system message. Using History change character for new conversation.")
    FIRST_SYSTEM_MESSAGE = read_system_message_from_txt("ChatHistoryBackup.txt")
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

try:
        twitch_sock = connect_to_twitch(token, nickname, channel)
        twitch_thread = threading.Thread(target=listen_to_twitch, args=(twitch_sock,))
        twitch_thread.daemon = True
        twitch_thread.start()
        print("Twitch listener started in background")
except Exception as e:
        print(f"Failed to start Twitch listener: {e}")

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


