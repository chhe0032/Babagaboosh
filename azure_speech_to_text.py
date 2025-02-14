import whisper
import pyaudio
import time
import wave
from pynput import keyboard

class SpeechToTextManager:
    whisper_model = None
    stop_listening = False  # Flag to track stop condition

    def __init__(self, model_name="base"):
        # Load the Whisper model locally
        self.whisper_model = whisper.load_model(model_name)

    def speechtotext_from_mic(self):
        # Record audio from the microphone
        print("Recording from microphone...")
        audio_data = self.record_audio_from_mic()

        # Transcribe audio
        text_result = self.transcribe_audio(audio_data)
        print(f"Recognized: {text_result}")
        return text_result

    def speechtotext_from_file(self, filename):
        # Load audio file
        print(f"Processing file: {filename}")
        audio_data = whisper.load_audio(filename)
        audio_data = whisper.pad_or_trim(audio_data)

        # Transcribe audio
        text_result = self.transcribe_audio(audio_data)
        print(f"Recognized: {text_result}")
        return text_result

    def speechtotext_from_file_continuous(self, filename):
        # Similar to the speechtotext_from_file, but handle continuous recognition
        print("Continuous file recognition...")
        audio_data = whisper.load_audio(filename)
        audio_data = whisper.pad_or_trim(audio_data)

        # Transcribe audio continuously in chunks if necessary
        final_result = self.transcribe_audio(audio_data)
        print(f"Recognized: {final_result}")
        return final_result

    def speechtotext_from_mic_continuous(self, stop_key='p'):
        print("Starting continuous speech-to-text from microphone... Press 'p' to stop.")
        self.stop_listening = False  # Reset stop condition each time this method is called
        all_results = []

        # Start listening for key presses in the background
        listener = keyboard.Listener(on_press=self.on_key_press)
        listener.start()

        # Start continuous recording and transcription in chunks
        while not self.stop_listening:
            audio_data = self.record_audio_from_mic()
            result = self.transcribe_audio(audio_data)
            print(f"Recognized: {result}")
            all_results.append(result)

        # Stop the listener after finishing the loop
        listener.stop()

        final_result = " ".join(all_results).strip()
        print(f"\nFinal result: {final_result}")
        return final_result

    def record_audio_from_mic(self, duration=5, rate=16000, channels=1, chunk_size=1024):
        # Set up the microphone
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk_size)

        print("Recording...")
        frames = []
        for _ in range(0, int(rate / chunk_size * duration)):
            data = stream.read(chunk_size)
            frames.append(data)

        print("Recording finished.")
        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save recorded audio to a temporary WAV file
        filename = "/tmp/temp_audio.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))

        return filename  # Return the path to the saved file

    def transcribe_audio(self, audio_data):
        # Convert raw audio to a format suitable for Whisper
        audio = whisper.load_audio(audio_data)
        audio = whisper.pad_or_trim(audio)

        # Generate log-Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio).to(self.whisper_model.device)

        # Detect language
        _, probs = self.whisper_model.detect_language(mel)
        print(f"Detected language: {max(probs, key=probs.get)}")

        # Decode the audio into text
        options = whisper.DecodingOptions()
        result = whisper.decode(self.whisper_model, mel, options)

        return result.text

    def on_key_press(self, key):
        try:
            if key.char == 'p':  # Stop key condition
                print("Stop key pressed, stopping...")
                self.stop_listening = True
        except AttributeError:
            # Handle special keys
            pass

# Tests
if __name__ == '__main__':
    TEST_FILE = "D:/Video Editing/Misc - Ai teaches me to pass History Exam/Audio/Misc - Ai teaches me to pass History Exam - VO 1.wav"
    
    speechtotext_manager = SpeechToTextManager()

    while True:
        # Uncomment the method you want to test
        # speechtotext_manager.speechtotext_from_mic()
        # speechtotext_manager.speechtotext_from_file(TEST_FILE)
        # pspeechtotext_manager.speechtotext_from_file_continuous(TEST_FILE)
        result = speechtotext_manager.speechtotext_from_mic_continuous()
        print(f"\n\nHERE IS THE RESULT:\n{result}")
        time.sleep(60)
