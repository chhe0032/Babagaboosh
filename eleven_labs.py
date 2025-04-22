from elevenlabs.client import ElevenLabs
from elevenlabs import stream, voices, play, save
import time
import os
import re

try:
    client = ElevenLabs(
        api_key=""  # Your API key here
    )
except TypeError:
    exit("You forgot to set ELEVENLABS_API_KEY in your environment!")

class ElevenLabsManager:
    def __init__(self, default_voice="David"):
        self.client = client
        self.default_voice = default_voice
        self.available_voices = self._get_available_voices()
        
    def _get_available_voices(self):
        """Fetch and cache available voices"""
        return {v.name: v.voice_id for v in self.client.voices.get_all().voices}
    
    @staticmethod
    def clean_text(text):
        """Clean text by removing <think> tags and asterisks."""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'\*', '', text)
        return text.strip()

    def set_voice(self, voice_name):
        """Change the default voice at runtime"""
        if voice_name in self.available_voices:
            self.default_voice = voice_name
            print(f"Voice changed to: {voice_name}")
        else:
            raise ValueError(f"Voice '{voice_name}' not available. Choices are: {list(self.available_voices.keys())}")

    def _validate_voice(self, voice):
        """Ensure the voice exists or use default"""
        if voice is None:
            return self.default_voice
        if voice not in self.available_voices:
            print(f"Warning: Voice '{voice}' not found. Using default '{self.default_voice}'")
            return self.default_voice
        return voice

    def text_to_audio(self, input_text, voice=None, save_as_wave=False, subdirectory=""):
        voice = self._validate_voice(voice)
        cleaned_text = self.clean_text(input_text)
        
        audio = self.client.generate(
            text=cleaned_text,
            voice=voice,
            model="eleven_turbo_v2"
        )
        
        ext = ".wav" if save_as_wave else ".mp3"
        file_name = f"Msg_{hash(cleaned_text)}_{voice}{ext}"
        file_path = os.path.join(os.path.abspath(os.curdir), subdirectory, file_name)
        save(audio, file_path)
        return file_path

    def text_to_audio_played(self, input_text, voice=None):
        voice = self._validate_voice(voice)
        cleaned_text = self.clean_text(input_text)
        
        audio = self.client.generate(
            text=cleaned_text,
            voice=voice,
            model="eleven_turbo_v2"
        )
        play(audio)

    def text_to_audio_streamed(self, input_text, voice=None):
        voice = self._validate_voice(voice)
        cleaned_text = self.clean_text(input_text)
        
        audio_stream = self.client.generate(
            text=cleaned_text,
            voice=voice,
            model="eleven_turbo_v2",
            stream=True
        )
        stream(audio_stream)
