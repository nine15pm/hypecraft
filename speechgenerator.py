import requests
import torch
from TTS.api import TTS

# Get device
# List available 🐸TTS models
XTTS_MODEL = 'tts_models/multilingual/multi-dataset/xtts_v2'

def generateSpeech(text:str, save_path:str, ref_audio_path:str, lang:str='en', split_sentences:bool=True):
    #check if GPU available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    #init TTS
    tts = TTS(XTTS_MODEL).to(device)
    print(TTS().list_models())
    
    #run inference
    tts.tts_to_file(text=text, speaker_wav=ref_audio_path, language=lang, file_path=save_path, split_sentences=split_sentences)

test_text = '''Big changes are coming to the Formula 1 grid, with Haas signing 19-year-old Oliver Bearman to replace Nico Hulkenberg next season, and rumors swirling that Liam Lawson could replace Daniel Ricardo at McLaren as early as the end of July.'''
file_path = 'audio_output/test2.wav'
ref_audio = 'voice_ref_clips/formula1_en_br1.wav'
ref_audio_list = [
    'voice_ref_clips/formula1_en_br1.wav',
    'voice_ref_clips/formula1_en_br2.wav',
    'voice_ref_clips/formula1_en_br3.wav',
    'voice_ref_clips/formula1_en_br4.wav',
]
#generateSpeech(text=test_text, save_path=file_path, ref_audio_path=ref_audio_list, split_sentences=False)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(device)
tts = TTS('tts_models/en/multi-dataset/tortoise-v2').to(device)
tts.tts_to_file(text=test_text, voice_dir='voice_ref_clips', speaker='formulaenbr', file_path=file_path)