# visual-novel-voicer

The goal behind the creation of this project is to have voice support for visual novels that do not inherently have them. Although the program can do what it is designed to do, this is just a food for thought which still needs to be improved. Which is why I have made this project public so people can create their own variations and better this one.<br>

# requirements

This program requires voicevox engine to be running, you can learn how to setup docker container for that online.<br>
Docker Image for VoiceVox Engine: https://hub.docker.com/r/voicevox/voicevox_engine<br>

Packages used in the program are also provided which you install either globally or in a venv by.<br>
`pip install -r requirements.txt`<br>

When installing packages on Windows, you may encounter "Microsoft Visual C++ 14.0 or greater is required" error because some of the packages used are old and needs to be built again.<br>
To be able to do that, follow the top answer here: https://stackoverflow.com/questions/64261546/how-to-solve-error-microsoft-visual-c-14-0-or-greater-is-required-when-inst<br>

Tesseract OCR engine<br>  
Make sure to have at least "eng" and "jpn" trained data installed with it.<br>
For Linux: `sudo apt install tesseract-ocr -y`<br>
For Windows: https://digi.bib.uni-mannheim.de/tesseract/<br>
For People who want to play in Japanese text I recommend downloading "jpn_ver5.traineddata" and placing it into traineddata folder in OCR engine: https://github.com/zodiac3539/jpn_vert<br>

Finally make sure to have Tesseract OCR Engine's path set as a path variable!!!

# usage

1. Run the docker container for Voicevox engine on port 50021.<br>
2. Open up your game, and the application, define regions of text field and character name field.<br>
3. After regions are defined, screen capture will start and those regions will be captured and turn into text.<br>
4. You can listen sample voices of the trained models by pressing "L" button under them, you can also change variations of their voice using the dropdown next to it.<br>
5. You can assign a character name to a voice, by "Assign Voice" button in the Speakers tab. "Current Name" textbox points to the current character name on the screen which will be assigned on your button press. This makes it so that whenever we want to synthesise audio from a text that is assigned to that character, we will hear that assigned voice.<br>
6. There are two checkboxes, one is for autoplay, as the name suggests, when turned on, whenever the text change is registered and a new query is formed, it immediately synthesises it for that character's voice and plays the audio.<br>
7. Other is for when you are playing the game in English language. Since we need Japanese text to pass to voicevox engine we need to translate it before doing so. This checkbox does just that.<br>
8. Once you configured the program to your liking for that specific game you can save those settings on top left corner under "Profile" header button. You can load these back whenever you want later on.<br>

- You can use the "History" tab to see previous captures, and play voice for them using the button next to it.<br>
- Lastly on Windows and macOS you can use "F9" key to play audio for the last valid query.<br>

# credits

[@VOICEVOX](https://github.com/VOICEVOX) for trained AI models, [@tuna2134](https://github.com/tuna2134) for voicevox-engine wrapper, [@zodiac3539](https://github.com/zodiac3539) for Tesseract OCR trained data.
