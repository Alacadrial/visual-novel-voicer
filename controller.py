from voicevox import Client
import re
import asyncio
from PIL import Image
import cv2
import pyautogui
import pytesseract
import numpy as np
import simpleaudio as sa
from pynput import mouse
import time
from io import BytesIO
import base64
import pickle
from translate import Translator
import os
import platform
import psutil
import subprocess

# OS specific imports
if platform.system() == "Windows":
	import win32gui
	import win32process

class ROI:

	def __init__(self):
		self.ix, self.iy, self.ex, self.ey = -1, -1, -1 ,-1;

	def listen_mouse(self):
		with mouse.Listener(on_click=self.on_click) as listener:
			listener.join()

	# Maybe use this to draw a rectangle on screen. Not used
	def on_move(self, x, y):
		if self.ix is not None and self.iy is not None:
			self.ex = x
			self.ey = y
			print(f"ROI coordinates: ({self.ix}, {self.iy}) - ({self.ex}, {self.ey})")

	def on_click(self, x, y, button, pressed):
		if pressed:
			if button == mouse.Button.left:
				self.ix, self.iy = x, y
		else:
			if button == mouse.Button.left:
				self.ex, self.ey = x, y
				return False

	def get_roi(self):
		return (min(self.ix, self.ex), min(self.iy, self.ey), abs(self.ix-self.ex), abs(self.iy-self.ey))


class VnvController:

	def __init__(self):
		self.client = Client()
		self.translator = Translator(to_lang="ja")
		self.roi = ROI()
		self.platform = platform.system()

		self.screenshot = None
		self.text_roi = None    
		self.name_roi = None
		self.target_process = None # target process id
		
		self.last_valid_query = None  # (id, text), this will play when we press play hotkey
		self.voice_dict = dict()
		self.audio_cache = dict()

		self.history = None  # (name, text)
		self.error = "" 

		self.current_name = "Self/Narrator"
		self.auto_play = False
		self.translate = False 								
		
		self.fetching_queries = list()
		self.play_object = None
		self.audio_tasks = list()

		self.get_focused_process_id = self.process_id_grabber_function()
		self.set_tesseract_path()
		# zodiac's tesseract model is really good at detecting japanese text.
		self.lang_pack = 'eng+jpn+jpn_ver5' # later on add multi file selection and save this in profiles as well

	async def get_speakers(self):
		speaker_dict = dict()
		speakers = await self.client.fetch_speakers()
		for speaker in speakers:
			speaker_info = await self.client.fetch_speaker_info(speaker.uuid)
			if speaker_info:
				speaker_dict[speaker.uuid] = dict()
				speaker_dict[speaker.uuid]["name"] = speaker.name 
				speaker_dict[speaker.uuid]["icon"] = BytesIO(base64.b64decode(speaker_info.style_infos[0].icon))
				speaker_dict[speaker.uuid]["styles"] = [[style.id, style.name] for style in speaker.styles]
				# Contains Voice Samples For Each Variant
				speaker_dict[speaker.uuid]["samples"] = dict() 
				for style in speaker_info.style_infos:
					speaker_dict[speaker.uuid]["samples"][style.id] = [BytesIO(base64.b64decode(sample)).getvalue() for sample in style.voice_samples]
		return speaker_dict

	async def close(self):
		await self.client.close()

	def process_id_grabber_function(self):
		if self.platform == "Windows":
			import win32gui
			import win32process
			return lambda: int(win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1])
		elif self.platform == "Linux":
			return lambda: int(subprocess.check_output(['xdotool', 'getwindowfocus', 'getwindowpid']).decode().strip())
		elif self.platform == "Darwin":
			return lambda: int(subprocess.check_output(['osascript', '-e', 'tell application "System Events" to get the unix id of the process whose frontmost is true']).decode().strip())

	def set_tesseract_path(self):
		tesseract_cmd = 'tesseract'
		if platform.system() == 'Windows':
			tesseract_cmd = 'tesseract.exe'

		# Search for tesseract in the system path
		for path in os.environ["PATH"].split(os.pathsep):
			path = path.strip('"')
			executable = os.path.join(path, tesseract_cmd)
			if os.path.isfile(executable):
				# Found tesseract, set the path and exit the loop
				pytesseract.pytesseract.tesseract_cmd = executable
				break
		else:
				# tesseract not found in the system path
				print("Error: tesseract not found in the system path")
				exit(-1)

	def save_profile(self, path):
		print("Save profile called with path: ", path)
		profile = {
			"name_roi" : self.name_roi,
			"text_roi" : self.text_roi,
			"voice_dict" : self.voice_dict,
			"auto_play" : self.auto_play,
			"translate" : self.translate
		}
		with open(path, "wb") as file:
			pickle.dump(profile, file)

	def load_profile(self, path):
		print("Load profile called with path: ", path)
		with open(path, "rb") as file:
			profile = pickle.load(file)
		self.name_roi = profile["name_roi"]
		self.text_roi = profile["text_roi"]
		self.voice_dict = profile["voice_dict"]
		self.auto_play = profile["auto_play"]
		self.translate = profile["translate"]

	def assign_voice(self, name, speaker_id):
		self.voice_dict[name] = speaker_id

	def set_auto_play(self, value):
		self.auto_play = value

	def set_translate(self, value):
		self.translate = value

	def set_text_roi(self, roi):
		self.text_roi = roi

	def set_name_roi(self, roi):
		self.name_roi = roi

	def set_target_process(self, pid):
		self.target_process = pid

	def select_roi(self):
		self.roi.listen_mouse()
		return self.roi.get_roi()

	def preprocess_english(self, text):
		return re.sub(r"[^\w\s\d\.\?,!]+$", "", text).strip()

	def preprocess_japanese(self, text):
		# Remove spaces
		text = text.replace(" ", "").strip()
		# Remove non-ASCII characters except punctuation, ASCII letters, Hiragana, Katakana, and Kanji characters
		text = re.sub(r'[^\x00-\x7F\u3000-\u30FF\uFF00-\uFFEF\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FBF]', '', text)
		return text

	def get_text_from_roi(self, roi):

		if roi == None:
			return ""

		image = pyautogui.screenshot(region=roi)

		# Convert Gray
		image = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)

		# Optimization of Accuracy, really effective.
		image = cv2.GaussianBlur(image, (5, 5), 0) 

		# Perform OCR, Takes the longest in computation time.
		text = pytesseract.image_to_string(image, lang=self.lang_pack)

		# Final process of the text. Lookup table for functions if more languages are added.
		preprocess_text = self.preprocess_english if self.translate else self.preprocess_japanese
		return preprocess_text(text)	

	async def screen_capture_loop(self):
		print("Screen Capture Loop Task Started")
		previous_text = ""
		found_new_valid_query = False

		# Capture Loop
		while True:
			start = time.time()
			
			# Check focused process id to match with selected process 
			if not self.target_process:
				print("Target process is not set. Please set it for capture to work.")
				await asyncio.sleep(0.25)
				continue

			# print("Current focused proc id: ", self.get_focused_process_id())

			if self.target_process != self.get_focused_process_id():
				# print("Window is not focused, skipping Iteration.")
				await asyncio.sleep(0.1)
				continue

			name = self.get_text_from_roi(self.name_roi)
			if not name:
				name = "Self/Narrator"
			self.current_name = name

			if self.text_roi == None:
				print("Text field is not set. Please set it for capture to work.")
				await asyncio.sleep(0.1)
				continue
			text = self.get_text_from_roi(self.text_roi)
			
			if text == "":
				# print("No text could be found, therefore no query.")
				await asyncio.sleep(0.1)
				continue

			if name not in self.voice_dict:
				print("Text is found, but name is not assigned to a character therefore no query.")
				await asyncio.sleep(0.1)
				continue

			speaker = self.voice_dict[name]

			if previous_text == text:
				self.last_valid_query = (speaker, text)
				# First time seeing this valid Query. Therefore initilizing history append and maybe audio play.
				if not found_new_valid_query:
					print("--Query--")
					print(name)
					print(text)
					print("---------")
					self.history = (name, text)
					found_new_valid_query = True
					if self.auto_play:
						print("Starting audio task from auto-play.")
						asyncio.create_task(self.play_audio_using_query(self.last_valid_query))
			else:
				# Change in text, reset variables
				found_new_valid_query = False	
			
			previous_text = text
			print("Scan Iteration Took: ", time.time() - start)		
			await asyncio.sleep(0.1)
	
	async def play_audio_using_query(self, query):
		speaker_id, text = query

		if query in list(self.audio_cache.keys()):
			audio_data = self.audio_cache[query]
		else:
			passing_argument = (speaker_id, text)

			if self.translate:
				passing_argument = (speaker_id, self.translator.translate(text))

			if passing_argument in self.fetching_queries:
				print("A task is already assigned to synthesise audio from this query, returning.")
				return
			
			self.fetching_queries.append(passing_argument)
			audio_data = await self.synthesise_audio(passing_argument)
			self.fetching_queries.remove(passing_argument)
		
		self.audio_cache[query] = audio_data
		asyncio.create_task(self.play_audio(audio_data))
		
	async def synthesise_audio(self, query):
		start = time.time()
		speaker, text = query
		audio_query = await self.client.create_audio_query(text, speaker=speaker)
		audio_query.volume_scale = 2.0
		audio_data = await audio_query.synthesis(speaker=speaker)
		print("Synthesis Request Took: ", time.time() - start)
		return audio_data

	async def play_audio(self, audio_data):
		# save audio to file.
		with open("voice.wav", "wb") as f:
			f.write(audio_data)

		# interrupt already playing audio.
		if self.play_object is not None and self.play_object.is_playing():
			self.play_object.stop()

		# Play the new audio.
		self.wave_object = sa.WaveObject.from_wave_file("voice.wav")
		self.play_object = self.wave_object.play()


