from controller import VnvController
import asyncio
import threading as th
import dearpygui.dearpygui as dpg
from PIL import Image
import platform
import psutil
import os


def task_thread(coro, loop):
	print("run_coroutine_threadsafe")
	future = asyncio.run_coroutine_threadsafe(coro, loop)
	loop.run_forever()

def prompt_process_selector(sender, app_data, user_data):

	def select_callback(sender, app_data, user_data):
		controller, combo = user_data
		pid = int(dpg.get_value(combo).split(":")[-1])
		controller.set_target_process(pid)
		dpg.delete_item("process_window")

	controller = user_data[0]
	try:
		user = os.getlogin().lower()
		print("Processes for user: ", os.getlogin())
		with dpg.window(label="Select Game Process", tag="process_window", pos=[0,0], min_size=[300,150], no_resize=True, on_close=lambda: dpg.remove_alias("process_window")) as window:
			process_list = sorted(psutil.process_iter(attrs=['pid', 'name', 'username']), key=lambda p: p.info['name'].lower())
			combo_list = [f"{process.name()}:{process.pid}" for process in process_list if process.info['username'].lower().contains(user)]
			with dpg.group(horizontal=True):
				dpg.add_text("Process: ")
				combo = dpg.add_combo(items=combo_list, default_value=combo_list[0], width=150)
				dpg.add_button(label="Select", callback=select_callback, user_data=[controller, combo])

	except Exception as err:
		print(err)

def prompt_about(sender, app_data, user_data):
	parent_window = user_data[0]
	try:
		with dpg.window(label="About", tag="about_window", pos=[0, 0], min_size=[350,200], on_close=lambda: dpg.remove_alias("about_window")) as window:
			dpg.add_text("Thank you for trying my application.")
			dpg.add_text("For usage check out my github repository.")
			with dpg.group(horizontal=True):
				dpg.add_text("Repo: ")
				dpg.add_input_text(label="##", default_value="https://github.com/Alacadrial/visual-novel-voicer",readonly=True)
	except Exception as err:
		print(err)

def prompt_file_selector(sender, app_data, user_data):
	label, callback, controller = user_data 
	with dpg.file_dialog(label=label, callback=callback, user_data=[controller], min_size=[350,400], max_size=[350,400], default_path="./profiles/"):
		dpg.add_file_extension(".profile")

def save_profile(sender, app_data, user_data):
	controller = user_data[0]
	controller.save_profile(app_data["file_path_name"])
	# File Name
	dpg.set_value("log_text", "Profile Save")

def load_profile(sender, app_data, user_data):
	controller = user_data[0]
	controller.load_profile(app_data["file_path_name"])
	dpg.set_value("log_text", "Profile Load")
	dpg.set_value("checkbox_auto_play", controller.auto_play)
	dpg.set_value("checkbox_translate", controller.translate)

def assign_bool(sender, app_data, user_data):
	setter_function = user_data[0]
	value = dpg.get_value(sender)
	setter_function(value)

def assign_voice(sender, app_data, user_data):
	controller = user_data[0]
	name = dpg.get_value("current_name")
	uuid = sender.split("_")[1]
	speaker_id = int(dpg.get_value(f"variant_{uuid}").split(":")[1])
	controller.assign_voice(name, speaker_id)
	dpg.set_value("log_text", f"Assigned '{name}' to [{speaker_id}]")

def assign_roi(sender, app_data, user_data):
	dpg.set_value("log_text", "Listening Mouse... Drag&Drop")
	select_roi, set_roi = user_data
	roi = select_roi()
	set_roi(roi)
	dpg.set_value("log_text", "--")

def listen_last_query_on_key_press(controller, loop):
	loop.create_task(controller.play_audio_using_query(query=controller.last_valid_query))
	dpg.set_value("log_text", f"Listening last valid query.")

def listen_sample(sender, app_data, user_data):
	controller, speakers, loop = user_data
	uuid = sender.split("_")[1]
	speaker_id = int(dpg.get_value(f"variant_{uuid}").split(":")[1])
	# normally a list that contains multiple samples, but working with the introduction sample for now.
	audio_data = speakers[uuid]["samples"][speaker_id][0] 
	loop.create_task(controller.play_audio(audio_data))
	dpg.set_value("log_text", f"Listening sample voice for [{speaker_id}]")

def listen_entry(sender, app_data, user_data):
	controller, loop = user_data
	entry_index = sender.split("_")[-1]
	name = dpg.get_value(f"history_entry_name_{entry_index}").strip()
	text = dpg.get_value(f"history_entry_text_{entry_index}").strip()
	speaker_id = controller.voice_dict[name]
	query = (speaker_id, text)
	loop.create_task(controller.play_audio_using_query(query))
	dpg.set_value("log_text", f"Listening entry for [{name}, {entry_index}]")


async def main():
	controller = VnvController()
	main_event_loop = asyncio.get_event_loop()		# Is used to create tasks to play sample voices.
	
	speakers = await controller.get_speakers()
	speaker_uuids = list(speakers.keys())

	main_window_width = 370
	main_window_height = 550

	dpg.create_context()
	dpg.create_viewport(title='VNV', width=main_window_width, height=main_window_height, resizable=False)
	
	# registery will be done in loop then when we create window we will do another loop to create components.
	texture_list = list()
	with dpg.texture_registry():
		for speaker in speakers: 
			image = Image.open(speakers[speaker]["icon"])
			image.save("icon.png")
			# Sadly there is no way to load image from buffer.
			width, height, channels, data = dpg.load_image("icon.png")
			texture_id = dpg.add_static_texture(width, height, data)
			texture_list.append(texture_id)

	# Register font that works with japanese and english.
	with dpg.font_registry():
		font_path = "./fonts/MSGOTHIC.TTF"
		with dpg.font(font_path, 13) as font1:
			dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)
			dpg.bind_font(font1)

	# Press F9 to play last valid query
	# For Windows and macOS, linux requires admin rights and when ran as root, it had trouble PCM device to play audio.
	if platform.system() in ["Windows", "Darwin"]:
		import keyboard
		keyboard.add_hotkey("f9", lambda: listen_last_query_on_key_press(controller, main_event_loop))

	#This only works when dearpygui process is focused. Therefore I have decided not to use it. Instead keyboard module is used.
	#with dpg.handler_registry():
   	#	dpg.add_key_press_handler(dpg.mvKey_F9, callback=listen_last_query_on_key_press, user_data=[controller, main_event_loop])

	# Start Screen Capture Thread
	capture_event_loop = asyncio.new_event_loop()	# Constantly running loop on another thread to capture screen.
	capture_thread = th.Thread(target=task_thread, args=(controller.screen_capture_loop(), capture_event_loop))
	capture_thread.daemon = True
	capture_thread.start()

	#Primary Window, There will be two tabs under this later.
	with dpg.window(label="Primary Window", no_resize=True, max_size=[main_window_width, 400]) as primary_window:
		primary_window_id = primary_window
		with dpg.menu_bar():
			dpg.add_menu_item(label="Attach Process", callback=prompt_process_selector, user_data=[controller])
			with dpg.menu(label="Profile"):
				dpg.add_menu_item(label="Load", callback=prompt_file_selector, user_data=["Load Profile File", load_profile, controller])
				# dpg.add_menu_item(label="Save")
				dpg.add_menu_item(label="Save As", callback=prompt_file_selector, user_data=["Save Profile File", save_profile, controller])
			dpg.add_menu_item(label="About", callback=prompt_about, user_data=[primary_window_id])

		with dpg.tab_bar():
			with dpg.tab(label="Speakers"):
				# Group Main Div For Speaker Components
				with dpg.group():
					icon_width, icon_height = 85, 85
					left_padding = 9
					split_list = [texture_list[i:i+3] for i in range(0, len(texture_list), 3)]
					index = 0
					# For each 3 texture create a Row
					for part in split_list:
						# Row
						with dpg.group(horizontal=True):
							dpg.add_spacer(width=left_padding)
							for texture_id in part:
								# Component
								with dpg.group():
									# Current Speaker's Values for GUI
									uuid = speaker_uuids[index]
									styles = speakers[uuid]["styles"]
									combo_items = [f"{name}:{_id}" for _id, name in styles]
									enabled = False if len(styles) == 1 else True

									# Icon
									dpg.add_image(texture_id, width=icon_width, height=icon_height)
									# Line where you listen to sample and select variations.
									with dpg.group(horizontal=True, horizontal_spacing=0):
										button_width = round(icon_width / 3)
										dpg.add_button(tag=f"listen_{uuid}", label="L", callback=listen_sample, user_data=[controller, speakers, main_event_loop], width=button_width)
										# if style_infos == 1 disabled combobox with already selected ID
										dpg.add_combo(tag=f"variant_{uuid}", items=combo_items, default_value=combo_items[0], enabled=enabled, no_arrow_button=True, width=icon_width-button_width)
									dpg.add_button(tag=f"assign_{uuid}", label="Assign Voice", callback=assign_voice, user_data=[controller], width=icon_width)
									index += 1
								dpg.add_spacer(width=3)

			with dpg.tab(tag="tab_history", label="History"):
				last_history_entry = 0 # Holds ID of last entry component
				history_entry_index = 0 # For uuid of a entry to access them from button press.
				# Text Capture History Will be here, updated dynamically on each render loop.
				pass

	with dpg.window(label="areaSelect", no_resize=True, no_title_bar=True, no_move=True, min_size=[main_window_width,150], pos=[0,400]):
		with dpg.group(horizontal=True):
			dpg.add_text("Current Name:   ")
			dpg.add_input_text(label="##", tag="current_name", readonly=True)
		with dpg.group(horizontal=True):
			dpg.add_text("Select Regions: ")
			dpg.add_button(tag="button_nameroi", label="Character Name", callback=assign_roi, user_data=[controller.select_roi, controller.set_name_roi], width=100, height=20)
			dpg.add_button(tag="button_textroi", label="Text", callback=assign_roi, user_data=[controller.select_roi, controller.set_text_roi], width=60, height=20)
		with dpg.group(horizontal=True):
			dpg.add_text("Autoplay Audio: ")
			dpg.add_checkbox(tag="checkbox_auto_play", callback=assign_bool, user_data=[controller.set_auto_play])
			dpg.add_text("Translate to Japanese: ")
			dpg.add_checkbox(tag="checkbox_translate", callback=assign_bool, user_data=[controller.set_translate])
		with dpg.group(horizontal=True):
			dpg.add_text("Log: ")
			dpg.add_input_text(label="##", tag="log_text", default_value="--", readonly=True)

	dpg.setup_dearpygui()
	dpg.set_primary_window(primary_window_id, True)
	dpg.show_viewport()

	# below replaces, start_dearpygui()
	while dpg.is_dearpygui_running():
	# insert here any code you would like to run in the render loop
	# you can manually stop by using stop_dearpygui()
		dpg.set_value("current_name", controller.current_name)
		
		# Show Error
		if controller.error:
			dpg.set_value("log_text", f"error: {controller.error}")
			controller.error = None

		# Insert to History Tab
		if controller.history:
			name, text = controller.history
			with dpg.group(parent="tab_history", before=last_history_entry) as grp:
				with dpg.group(horizontal=True):
					dpg.add_text(name + " "*(20-len(name)), tag=f"history_entry_name_{history_entry_index}")
					dpg.add_button(label="L", width=28, tag=f"listen_history_entry_{history_entry_index}", callback=listen_entry, user_data=[controller, main_event_loop])            
				dpg.add_text(text, tag=f"history_entry_text_{history_entry_index}")
				last_history_entry = grp
				history_entry_index += 1
			controller.history = None

		dpg.render_dearpygui_frame()
		await asyncio.sleep(0.1)

	dpg.destroy_context()

if __name__ == '__main__':
	asyncio.run(main())
