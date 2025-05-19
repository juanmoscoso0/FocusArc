from re import I
import time
import kivy
import getpass
import os
import random
import json
from kivy.core.audio import SoundLoader
from playsound import playsound
from kivy.config import Config
from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.screenmanager import FadeTransition, SlideTransition
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from PIL import Image as PILImage # Loads and inspects images
import numpy as np # Allows the manipulation of an image's pixels via an array

Config.set('kivy','video', 'ffpyplayer')
Window.minimum_width = 800
Window.minimum_height = 600

BASE_PATH = os.path.dirname(__file__)
SAVE_FILE = os.path.join(BASE_PATH, 'user_progress.json')
PAINTINGS_DIR = os.path.join(BASE_PATH, 'assets', 'images', 'sprites')

class PixelCanvas(Image):
    ''' This class will create the canvas to display the 20x20 basic mastery tier'''
    def __init__(self, **kwargs):
        image_path = kwargs.pop('image_path', None) 
        super().__init__(**kwargs)

        if image_path is None:
            raise ValueError('No image_path provided to PixelCanvas')

        self.source = image_path

        self.original_img = PILImage.open(image_path).convert('RGB') # Opens image with PIL and converts it to RGB mode
        self.width_px, self.height_px = self.original_img.size  # stores the width and height in pixels

        # Takes the pixel data of the image and creates an array with it using numpy
        self.pixel_data = np.array(self.original_img)

        # creates a zeroed array with the same size as pixel_data
        self.revealed_data = np.zeros_like(self.pixel_data)

        # tracks how many blacks have been revealed
        self.current_block = 0

        # Creates and stores a texture that is the same size as the image
        self.canvas_texture = Texture.create(size=(self.width_px, self.height_px))
        self.canvas_texture.mag_filter = 'nearest'

        # Assign it to the Image widget's texture property
        self.texture = self.canvas_texture

        # Visual scaling
        self.size_hint = (None, None)
        self.size = (200, 200)
        self.allow_stretch = True
        self.keep_ratio = False

        # Calls method to draw initial image on screen
        self.update_texture()

        # makes the total blocks to reveal 100, also sqrt roots the total blocks so that it can accomodate a 20x20 pixel reveal instead of just 2x2 (for bigger pictures)
        self.total_blocks = 100
        self.blocks_per_row = int(np.sqrt(self.total_blocks))
        self.block_width = self.width_px // self.blocks_per_row
        self.block_height = self.height_px // self.blocks_per_row

        # Completion callback
        self.on_complete = None

    def update_texture(self):
        ''' This method will be used to update the texture every hour'''
        flipped = np.flipud(self.revealed_data) # Flips the image back to the correct orientation
        flat = flipped.tobytes() # Converts 3D array inot flat byte array
        self.canvas_texture.blit_buffer(flat, colorfmt='rgb', bufferfmt='ubyte') # Updates with new pixel data
        self.canvas.ask_update() # Redraws texture on screen

    def reveal_next_block(self):
        ''' If self.current_block is greater than or equal to 100 blocks (4 pixels) 
        then the method will return and stop'''
        if self.current_block >= self.total_blocks: # Stops if all blocks are shown
            # Calls completion callback if defined
            if self.on_complete:
                self.on_complete()
            return
        
        bx = (self.current_block % self.blocks_per_row) * self.block_width # Converts block into (x, y) format, scans from left to right and from top to bottom
        by = (self.current_block // self.blocks_per_row) * self.block_height

        for dx in range(self.block_width):
        # Copies each 2x2 pixel block from the original image to the canvas to reveal image on screeen
            for dy in range(self.block_width): 
                x, y = bx + dx, by + dy
                
                if 0 <= x < self.width_px and 0 <= y < self.height_px:
                    self.revealed_data[y,x] = self.pixel_data[y,x]
        
        # Adds one to the current block counter and updates texture to show new 2x2 block
        self.current_block += 1
        self.update_texture()

        # Check if it was last block
        if self.current_block >= self.total_blocks and self.on_complete:
            self.on_complete()

    def restore_blocks(self, block_count):
        ''' Method used to restore blocks from previous user session '''
        for block_num in range(block_count):
            bx = (block_num % self.blocks_per_row) * self.block_width
            by = (block_num // self.blocks_per_row) * self.block_height

            for dx in range(self.block_width):
                for dy in range(self.block_height):
                    x, y = bx + dx, by + dy
                    if 0 <= x < self.width_px and 0 <= y < self.height_px:
                        self.revealed_data[y,x] = self.pixel_data[y,x]

        self.current_block = block_count
        self.update_texture()

class WindowManager(ScreenManager):
    ''' Window manager for each screen '''
    pass

class StartWindow(Screen):
    ''' First screen that pops up when app starts,
        computer_name takes the users computer name,
        turns it into a string and displays it in the 
        welcome message'''
    
    computer_name = StringProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.computer_name = getpass.getuser() # Stores profile name of user in self.computer_name (this will be changed eventually to allow the user to add their own name)

class MainMenu(Screen):
    ''' Menu to for user to choose options from '''
    pass

class TimerWindow(Screen):
    ''' Core screen, where the user sets their study time '''
    pass

class ProfileWindow(Screen):
    ''' User profile, has compeleted works, stats, name, etc '''
    def on_enter(self):
        app = App.get_running_app()
        app.calculate_stats()
        self.ids.stats_hours.text = f'Total Hours Studied:\n{app.hours_studied}'
        self.ids.stats_minutes.text = f'Total Minutes Studied:\n{app.minutes_studied}'
        self.ids.stats_seconds.text = f'Total Seconds Studied:\n{app.seconds_studied}'

class GalleryWindow(Screen):
    ''' Gallery screen, shows all the users completed works '''
    
    def update_gallery(self, completed_list):
        print("Updating gallery with:", completed_list)
        container = self.ids.paintings
        container.clear_widgets()

        for filename in completed_list:
            image_path = os.path.join(PAINTINGS_DIR, filename)
            if not os.path.exists(image_path):
                print(f"[MISSING] Image not found: {image_path}")
                continue
            
            img = Image(source=image_path, size_hint = (None, None), size=(200, 200))
            container.add_widget(img)
            print(f'Added image to gallery: {image_path}')

class StudyTimer(App):
    ''' Main app class, has all the functions that the software needs '''
    # Placeholders for stats
    hours_studied = StringProperty('null')
    minutes_studied = StringProperty('null')
    seconds_studied = StringProperty('null')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Tracks the first tick of the image generation, done to prevent first block from appearing too early
        self.first_tick = True

        # Placeholder for user_time
        self.user_time = 0

        # Total seconds user has studied, will be formatted into hours, minutes, and seconds
        self.total_seconds_studied = self.user_time 

        # Reference to timer event
        self.timer_event = None

        # Seconds per block
        self.reveal_interval = 3600

        # Seconds since last block reveal
        self.seconds_since_last_reveal = 0


    def valid_number_hours(self, instance):
        ''' Validates that the number inputted by the user in the hours TextInput is not over 24 '''
        try:
            if len(instance.text) > 2: 
                instance.text = instance.text[:2]
            if int(instance.text) > 24:
                instance.text = '24'
        except:
            pass

    def valid_number_secnmins(self, instance):
        ''' Does the same thing as the previous method, just checks that it won't go above 60 for mins/secs '''
        try:
            if len(instance.text) > 2:
                instance.text = instance.text[:2]
            if int(instance.text) > 59:
                instance.text = '59'
        except:
            pass

    def calculate_total_time(self, hours_input, minutes_input, seconds_input):
        ''' Turns the inputs into integers and calculates the total time in seconds '''
        self.session_duration = self.user_time
        self.first_tick = True
        self.reveal_interval = 3600
        
        h = int(hours_input.text) if hours_input.text.isdigit() else 0
        m = int(minutes_input.text) if minutes_input.text.isdigit() else 0
        s = int(seconds_input.text) if seconds_input.text.isdigit() else 0
        print(h, m, s)

        self.user_time = int(h) * 3600 + int(m) * 60 + int(s) # Logic for finding total seconds 
        self.first_tick = True # Prevents first block from being placed prematurely

        # Makes sure pixel_canvas exists before trying to use it
        if hasattr(self, 'pixel_canvas') and self.pixel_canvas is not None:
        # Only resets canvas if it's your first session
            if self.pixel_canvas.current_block >= self.pixel_canvas.total_blocks:
                self.pixel_canvas.current_block = 0
                self.pixel_canvas.revealed_data.fill(0)
                self.pixel_canvas.update_texture()

        # Set up completion call back
        self.pixel_canvas.on_complete = self.on_canvas_complete
        
        self.timer_event = Clock.schedule_interval(self.update_timer, 1) # Clock schedules the function update timer to run every second
        self.update_timer(0)

    def on_canvas_complete(self):
        ''' Called when all blocks are revealed '''
        print('Canvas Complete!')

        progress = self.load_progress()

        # Get the current picture's filename and adds it to the list
        current_painting = progress['current']
        if current_painting and current_painting not in progress['completed']:
            progress['completed'].append(current_painting)
            print(f'Added to completed list: {current_painting}')

        # Get new painting
        new_painting = self.get_new_painting(progress['completed'])

        if new_painting:
            # Sets new painting
            progress['current'] = new_painting
            image_path = os.path.join(PAINTINGS_DIR, new_painting)
            print(f'New painting selected {new_painting}')

            # Replace canvas with new painting
            container = self.root.get_screen('Timer').ids.pixel_canvas_container
            container.clear_widgets()
            self.pixel_canvas = PixelCanvas(image_path=image_path)
            self.pixel_canvas.on_complete = self.on_canvas_complete
            container.add_widget(self.pixel_canvas)

        else:
            progress['current'] = None
            print('All paintings completed!')
        
        # Saves progress
        self.save_progress(progress)

        # Update gallery
        self.root.get_screen('Gallery').update_gallery(progress['completed'])
        print(f"Gallery updated with: {progress['completed']}")


    def update_timer(self, dt):
        ''' If the variable user_time equals or is less than 0, print Times up! and end the method via return
        if not then display the countdown on screen and countdown -1 each second '''
        time_screen = self.root.get_screen('Timer')

        s = self.user_time % 60 # Defines seconds
        m = int(self.user_time / 60) % 60  # Defines minutes by seconds
        h = int(self.user_time / 3600) # Defines hours by seconds 
    
        print(f'{h:02}:{m:02}:{s:02}')
        
        time_screen.ids.PreTimer_Elements.opacity = 0 # Removes the setup_box group from visibility by turning its opacity to 0
        time_screen.ids.countdown_display.text = f'{h:02}  :  {m:02}  :  {s:02}' # displays the countdown on screen
        time_screen.ids.countdown_display.opacity = 1 # Sets coutndown opacity to 1 so it can be visible after setting timer

        time_screen.ids.block_countdown.opacity = 1
        time_screen.ids.pixel_canvas_container.opacity = 1 # Sets pixel canvas contrainer to be visible
        
        self.calculate_stats()

        has_pixel_canvas = hasattr(self, 'pixel_canvas') and self.pixel_canvas is not None

        # Logic for revealing blocks, stops first block from being revealed immedietly
        if self.user_time > 0:
            self.user_time -= 1
            self.total_seconds_studied += 1
            self.calculate_stats()
            
            self.seconds_since_last_reveal += 1
            
            if self.seconds_since_last_reveal >= self.reveal_interval:
                self.pixel_canvas.reveal_next_block()
                self.seconds_since_last_reveal = 0

            block_time_left = max(0, self.reveal_interval - self.seconds_since_last_reveal)
            bs = block_time_left % 60
            bm = int(block_time_left / 60) % 60
            bh = int(block_time_left / 3600) 
            time_screen.ids.block_countdown.text = f'Next block in: {bh} Hours, {bm} Minutes, {bs} Seconds'

            # Save progress in real time instead of after timer ends
            progress = self.load_progress(update_stats=False)

            if has_pixel_canvas and hasattr(self.pixel_canvas, 'source') and self.pixel_canvas.source is not None:
                progress['current'] = self.pixel_canvas.source.split(os.sep)[-1]
            else:
                progress['current'] = None

            progress['current_block'] = self.pixel_canvas.current_block if self.pixel_canvas else 0
            progress['time_toward_block'] = self.seconds_since_last_reveal
            progress['total_seconds_studied'] = self.total_seconds_studied
            self.save_progress(progress)

            return True

        print("Time's up!")
        
        if self.timer_event:
            self.timer_event.cancel()

        progress = self.load_progress(update_stats=False)

        if has_pixel_canvas and hasattr(self.pixel_canvas, 'source') and self.pixel_canvas.source is not None:
            progress['current'] = self.pixel_canvas.source.split(os.sep)[-1]
        else:
            progress['current'] = None

        progress['current_block'] = self.pixel_canvas.current_block if self.pixel_canvas else 0
        progress['time_toward_block'] = self.seconds_since_last_reveal
        progress['total_seconds_studied'] = self.total_seconds_studied
        
        self.save_progress(progress)

        time_screen.ids.countdown_display.text = f'{0:02}  :  {0:02}  :  {0:02}' # Display 00:00:00 on timer
        time_screen.ids.countdown_display.opacity = 0
        time_screen.ids.Opening_Text.opacity = 0
        time_screen.ids.block_countdown.text = ''
        time_screen.ids.block_countdown.opacity = 0
        time_screen.ids.PreTimer_Elements.opacity = 1
        time_screen.ids.hours_input.text = ''
        time_screen.ids.minute_input.text = ''
        time_screen.ids.seconds_input.text = ''

        base_path = os.path.dirname(__file__)  
        audio_path = os.path.join(base_path, 'assets', 'audio', 'church_bell.wav') # Completes the path for the church bell audio
            
        sound = SoundLoader.load(audio_path)
        if sound:
            sound.play()

        return False

    def calculate_stats(self):
        self.hours_studied = str(self.total_seconds_studied // 3600)
        remaining_seconds_hr = self.total_seconds_studied % 3600
        self.minutes_studied = str(remaining_seconds_hr // 60)
        remaining_seconds_min = remaining_seconds_hr % 60
        self.seconds_studied = str(remaining_seconds_min % 60)
        print(f'[Stats] {self.hours_studied}h {self.minutes_studied}m {self.seconds_studied}s')

        print(self.hours_studied, self.minutes_studied, self.seconds_studied)

    def load_progress(self, update_stats=True):
        ''' Loads user progress from json file, if its not corrupted and exists '''
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                    # Fills all required fields, even if info is missing
                    data.setdefault('current_block', 0)
                    data.setdefault('time_toward_block', 0)
                    data.setdefault('total_seconds_studied', 0)
                    data.setdefault('completed', [])
                    data.setdefault('current', None)
                                        
                    if update_stats:
                        self.total_seconds_studied = data['total_seconds_studied']
                        self.calculate_stats()
                    return data

            except json.JSONDecodeError: # Runs if file is corrupted
                print('Warning: Progress file is corrupted. Creating a new one')
                # If theres a save file present, but corrupted this will make a backup
                if os.path.exists(SAVE_FILE):
                    backup_file = SAVE_FILE + '.bak'
                    try:
                        os.rename(SAVE_FILE, backup_file)
                        print(f'Backed up cprrrupted file to {backup_file}')
                    except OSError:
                        print('Could not back up corrupted file')
            return {'completed': [], 'current': None, 'current_block': 0, 'time_toward_block': 0}

    def save_progress(self, progress_data):
        ''' Saves user progress to the JSON file '''
        if self.pixel_canvas:
            progress_data['current_block'] = self.pixel_canvas.current_block
    
        progress_data['time_toward_block'] = self.seconds_since_last_reveal
        progress_data['total_seconds_studied'] = self.total_seconds_studied
    
        with open(SAVE_FILE, 'w') as f:
            json.dump(progress_data, f)

    def get_new_painting(self, completed):
        ''' Adds unfinished paintings to available_paintings list and if 
        there are any in the list, it will return a random painting within that list '''
        all_files = [f for f in os.listdir(PAINTINGS_DIR) if f.lower().endswith(('.png', '.jpg'))]
        available_paintings = [f for f in all_files if f not in completed]

        if available_paintings:
            return random.choice(available_paintings)
        return None

    def reset_progress(self):
        ''' Clears all completed paintings '''
        all_files = [f for f in os.listdir(PAINTINGS_DIR) if f.lower().endswith(('.png', '.jpg'))]

        # Resets progress file
        progress = {'completed': [], 'current': None}

        # Pick random painting
        if all_files:
            progress['current'] = random.choice(all_files)

        self.save_progress(progress)
        print('Progress reset, New Current:', progress['current'])

        # Rebuilds canvas for timer screen
        if self.root:
            image_path = os.path.join(PAINTINGS_DIR, progress ['current'])
            if os.path.exists(image_path):
                self.pixel_canvas = PixelCanvas(image_path=image_path)
                self.pixel_canvas.on_complete = self.on_canvas_complete
                timer_screen = self.root.get_screen('Timer')
                timer_screen.ids.pixel_canvas_container.clear_widgets()
                timer_screen.ids.pixel_canvas_container.add_widget(self.pixel_canvas)

            self.root.get_screen('Gallery').update_gallery(progress['completed'])

    def on_stop(self):
        ''' Saves the current block the user is on so that when they reopen
        the app it starts from the same block they left off at '''
        progress = self.load_progress()
        if self.pixel_canvas:
            progress['current_block'] = self.pixel_canvas.current_block

        progress['total_seconds_studied'] = self.total_seconds_studied
        self.save_progress(progress)

        print(f"Saving block: {progress['current_block']} for image {progress['current']}")
        print(f"Saving total study time: {progress['total_seconds_studied']} seconds")

    def build(self):
        ''' compiles the app together '''
        kv = Builder.load_file('studytimer.kv') # Loads kv file studytimer.kv
        root = kv

        # Loads progress from previous sessions
        progress = self.load_progress()

        # Makes sure that required keys exist
        if 'completed' not in progress:
            progress['completed'] = []
        if 'current' not in progress:
            progress['current'] = None
        current = progress.get('current')

        # Calculates formatted stats
        self.calculate_stats()

        # Fresh start
        if not current: 
            current = self.get_new_painting(progress['completed'])
            progress['current'] = current
            if current:
                progress['current'] = current
                print(f'Selected new painting: {current}')

        self.seconds_since_last_reveal = progress.get('time_toward_block', 0)
            
        # Only proceeds with canvas if there is a current picture
        if current:
            # Defines image path
            image_path = os.path.join(PAINTINGS_DIR, current)

            if os.path.exists(image_path):
                # Builds canvas
                self.pixel_canvas = PixelCanvas(image_path=image_path)
                self.pixel_canvas.on_complete = self.on_canvas_complete

                # Restores block progress
                self.pixel_canvas.restore_blocks(progress.get('current_block', 0))

                # Add canvas to timer layout
                timer_screen = root.get_screen('Timer')
                timer_screen.ids.pixel_canvas_container.clear_widgets()
                timer_screen.ids.pixel_canvas_container.add_widget(self.pixel_canvas)

                # Making sure its visible
                timer_screen.ids.pixel_canvas_container.opacity = 1

            else:
                print(f'Warining: Image file not found: {image_path}')
                self.pixel_canvas = None
        else:
            print('No current painting selected')
            self.pixel_canvas = None

        # Updates gallery
        root.get_screen('Gallery').update_gallery(progress['completed'])
        print(f"Gallery updated with: {progress['completed']}")

        self.save_progress(progress)

        print('Current working directory:', os.getcwd())
        print('Script Location:', os.path.dirname(__file__))
        print("Saving completed:", progress['completed'])
        print("Now showing:", progress['current'])

        return root

if __name__=='__main__': # If the app is running from it's main script, then run the GUI
    StudyTimer().run()