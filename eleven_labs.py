from elevenlabs.client import ElevenLabs
from elevenlabs import stream, voices, play, save
import time
import os

try:
  client = ElevenLabs(
     api_key=""
  )
except TypeError:
  exit("Ooops! You forgot to set ELEVENLABS_API_KEY in your environment!")

class ElevenLabsManager:
    
    response = client.voices.get_all()
    #print(response.voices)


    # Convert text to speech, then save it to file. Returns the file path
    def text_to_audio(self, input_text, voice="Drew", save_as_wave=True, subdirectory=""):
        audio_saved = client.generate(
          text=input_text,
          voice=voice,
          model="eleven_turbo_v2"
        )
        if save_as_wave:
          file_name = f"___Msg{str(hash(input_text))}.wav"
        else:
          file_name = f"___Msg{str(hash(input_text))}.mp3"
        tts_file = os.path.join(os.path.abspath(os.curdir), subdirectory, file_name)
        save(audio_saved,tts_file)
        return tts_file

    # Convert text to speech, then play it out loud
    def text_to_audio_played(self, input_text, voice="Drew"):
        audio = client.generate(
          text=input_text,
          voice=voice,
          model="eleven_monolingual_v1"
        )
        play(audio)

    # Convert text to speech, then stream it out loud (don't need to wait for full speech to finish)
    def text_to_audio_streamed(self, input_text, voice="Drew"):
        audio_stream = client.generate(
          text=input_text,
          voice=voice,
          model="eleven_monolingual_v1",
          stream=True
        )
        stream(audio_stream)


if __name__ == '__main__':
    elevenlabs_manager = ElevenLabsManager()

    file_path = elevenlabs_manager.text_to_audio("This is my saved test audio, please make me beautiful", "Drew")
    print("Finished with all tests")

    time.sleep(30)

