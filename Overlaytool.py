import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
from VideoMaker import VideoMaker
from TransparentVideoMaker import TransparentVideoMaker  # Import the new TransparentVideoMaker class
import time
from OsdFileReader import OsdFileReader
from VideoMerger import VideoMerger
from proglog import TqdmProgressBarLogger

class OverlayToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Overlay Tool")

        # Set scaling for high-resolution monitors
        self.root.tk.call('tk', 'scaling', 2.0)

        # Initialize variables with default paths
        self.osd_file_path = tk.StringVar()
        self.output_path = tk.StringVar()        
        self.input_path = tk.StringVar()
        self.final_path = tk.StringVar()
        self.hex_grid_csv_path = tk.StringVar(value='maps/standard.csv')
        self.font_image_path = tk.StringVar(value='fonts/WS_BFx4_Nexus_Moonlight_2160p.png')
        self.chroma_key_hex = tk.StringVar(value='FF00FF')  # Default to magenta
        self.fps = tk.DoubleVar(value=30.0)
        self.transparent_background = tk.BooleanVar(value=True)  # Checkbox for transparency

        # Initialize placeholder variables for VideoMaker and OsdFileReader
        self.video_maker = None
        self.osd_reader = None
        self.video_merger= None

        # Build the GUI
        self.create_widgets()

    def create_widgets(self):
        # Input Settings
        input_frame = ttk.LabelFrame(self.root, text="Input Settings")
        input_frame.pack(padx=10, pady=10, fill='x')

        # OSD file input
        ttk.Label(input_frame, text="OSD File:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.osd_file_path, width=50).grid(row=0, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_osd_file).grid(row=0, column=2, padx=5, pady=5)

        # Input path
        ttk.Label(input_frame, text="Input MOV File:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.input_path, width=50).grid(row=1, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_input_path).grid(row=1, column=2, padx=5, pady=5)
        # Final Output path
        ttk.Label(input_frame, text="Output Merged File:").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.final_path, width=50).grid(row=2, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_final_path).grid(row=2, column=2, padx=5, pady=5)

        # Button to set output path same as input
        #ttk.Button(input_frame, text="Same as Input", command=self.set_output_same_as_input).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        # Hex grid CSV path
        ttk.Label(input_frame, text="Hex Grid CSV:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.hex_grid_csv_path, width=50).grid(row=3, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_hex_grid_csv).grid(row=3, column=2, padx=5, pady=5)

        # Font image path
        ttk.Label(input_frame, text="Font Image:").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.font_image_path, width=50).grid(row=4, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_font_image).grid(row=4, column=2, padx=5, pady=5)

        # Transparent Background checkbox and Chroma Key
        #ttk.Checkbutton(input_frame, text="Transparent Background", variable=self.transparent_background, command=self.toggle_chroma_key).grid(row=5, column=1, sticky='w', padx=5, pady=5)
        #ttk.Label(input_frame, text="Chroma Key Hex:").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        #self.chroma_key_entry = ttk.Entry(input_frame, textvariable=self.chroma_key_hex)
        #self.chroma_key_entry.grid(row=6, column=1, sticky='w', padx=5, pady=5)

        # FPS
        ttk.Label(input_frame, text="FPS:").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.fps).grid(row=7, column=1, sticky='w', padx=5, pady=5)

        # Create button
        ttk.Button(input_frame, text="Create Video", command=self.start_creation).grid(row=8, column=1, pady=10)

        # Progress bar and label
        self.progress_label = ttk.Label(self.root, text="")
        self.progress_label.pack()
        self.progress_bar = ttk.Progressbar(self.root, orient='horizontal', length=400, mode='determinate')
        self.progress_bar.pack(pady=5)

        # Estimated time label
        self.time_label = ttk.Label(self.root, text="Estimated time remaining: calculating...")
        self.time_label.pack()

        # Configure column weights
        input_frame.columnconfigure(1, weight=1)

    # Toggle chroma key based on Transparent Background checkbox
    def toggle_chroma_key(self):
        if self.transparent_background.get():
            self.chroma_key_entry.config(state="disabled")
        else:
            self.chroma_key_entry.config(state="normal")
        self.update_output_extension()

    def update_output_extension(self):
        """Update the output file extension based on the transparent background checkbox."""
        current_path = self.output_path.get()
        if not current_path:
            return

        # Determine the new file extension
        new_extension = ".mov" if self.transparent_background.get() else ".mp4"

        # Split the current path and replace the extension
        base_name, _ = os.path.splitext(current_path)
        updated_path = base_name + new_extension

        # Update the output path
        self.output_path.set(updated_path)

    # Button methods
    def browse_osd_file(self):
        filename = filedialog.askopenfilename(title="Select OSD file", filetypes=(("OSD files", "*.osd"), ("All files", "*.*")))
        if filename:
            self.osd_file_path.set(filename)

    def browse_output_path(self):
        filename = filedialog.asksaveasfilename(title="Select output file", defaultextension=".mov",
                                                filetypes=(("MOV files", "*.mov"), ("All files", "*.*")))
        if filename:
            self.output_path.set(filename)

    def browse_final_path(self):
        filename = filedialog.asksaveasfilename(title="Select final file", defaultextension=".mov",
                                                filetypes=(("MOV files", "*.mov"), ("All files", "*.*")))
        if filename:
            self.final_path.set(filename)


    def browse_input_path(self):
        filename = filedialog.askopenfilename(title="Select MOV file", filetypes=(("MOV files", "*.mov"), ("All files", "*.*")))
        if filename:
            self.input_path.set(filename)

    def set_output_same_as_input(self):
        input_path = self.osd_file_path.get()
        if input_path:
            output_path = os.path.splitext(input_path)[0] + '_OSD.mov'  # Append "_OSD" to avoid overwriting
            self.output_path.set(output_path)
            self.update_output_extension()
        else:
            messagebox.showerror("Error", "Please select an OSD file first.")


    def browse_hex_grid_csv(self):
        filename = filedialog.askopenfilename(initialdir='maps', title="Select Hex Grid CSV",
                                              filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        if filename:
            self.hex_grid_csv_path.set(filename)

    def browse_font_image(self):
        filename = filedialog.askopenfilename(initialdir='fonts', title="Select Font Image",
                                              filetypes=(("PNG files", "*.png"), ("All files", "*.*")))
        if filename:
            self.font_image_path.set(filename)

    def start_creation(self):
        if not self.osd_file_path.get():
            messagebox.showerror("Error", "Please select an OSD file.")
            return

        print("Starting video creation...")  # Debugging statement
        threading.Thread(target=self.create_video_process).start()

    def create_video_process(self):
        try:
            print("Initializing OSD Reader...")
            self.osd_reader = OsdFileReader(self.osd_file_path.get())
            print("OSD Reader initialized successfully.")

            print("Initializing VideoMaker...")
            if self.transparent_background.get():
                # Use TransparentVideoMaker for videos with an alpha channel
                self.video_maker = TransparentVideoMaker(
                    osd_reader=self.osd_reader,
                    hex_grid_path=self.hex_grid_csv_path.get(),
                    font_image_path=self.font_image_path.get(),
                    fps=self.fps.get()
                )
            else:
                # Use standard VideoMaker with chroma key
                self.video_maker = VideoMaker(
                    osd_reader=self.osd_reader,
                    hex_grid_path=self.hex_grid_csv_path.get(),
                    font_image_path=self.font_image_path.get(),
                    chroma_key_hex=self.chroma_key_hex.get(),
                    fps=self.fps.get()
                )
            print("VideoMaker initialized successfully.")

            #output_path = self.output_path.get()
            #if not output_path:
            extension = ".mov" if self.transparent_background.get() else ".mp4"
            output_path = os.path.splitext(self.final_path.get())[0] + '_OSD' + extension  # Default to _OSD.mov or _OSD.mp4

            def update_progress(percentage, remaining_time=None):
                self.progress_bar['value'] = percentage
                if remaining_time is not None:
                    self.time_label.config(text=f"Estimated time remaining: {remaining_time:.2f} seconds")
                self.update_progress_label(f"Processing: {int(percentage)}% complete")
                self.root.update_idletasks()

            print("Starting video creation process...")
            start_time = time.time()

            def progress_callback(percentage, frame_num):
                # Update the progress bar
                update_progress(percentage)

                # Calculate remaining time every 100 frames
                if frame_num % 50 == 0 and frame_num > 0:
                    elapsed_time = time.time() - start_time
                    frames_processed = frame_num
                    frames_remaining = self.video_maker.total_frames - frames_processed
                    if frames_remaining > 0:
                        estimated_remaining_time = (elapsed_time / frames_processed) * frames_remaining
                        update_progress(percentage, estimated_remaining_time)
                        print(
                            f"Processed {frame_num} frames; estimated remaining time: {estimated_remaining_time:.2f} seconds")

            self.video_maker.create_video(output_path, progress_callback=progress_callback)
            print("Video creation process completed.")  
            
            print("Starting video merging process...")
            start_time = time.time()
            class MyBarLogger(TqdmProgressBarLogger):
                def callback(self, **changes):
                    try:
                        index = self.state['bars']['frame_index']['index']
                        total = self.state['bars']['frame_index']['total']
                        update_progress(index / total * 100)
                        if index % 10 == 0 and index > 0:
                            elapsed_time = time.time() - start_time
                            frames_processed = index
                            frames_remaining = total - frames_processed
                            if frames_remaining > 0:
                                estimated_remaining_time = (elapsed_time / frames_processed) * frames_remaining
                                update_progress(index / total * 100, estimated_remaining_time)
                    except KeyError as e:
                        print(f"{self.state}")

            my_logger = MyBarLogger()
            self.video_merger = VideoMerger()
            
            final_path = self.final_path.get()
            input_path = self.input_path.get()
            self.video_merger.merge_overlay(input_path,output_path,final_path, progress_callback=my_logger)
            messagebox.showinfo("Success", f"Video created successfully at {final_path}")
            os.remove(output_path)

        except Exception as e:
            print(f"Error occurred: {e}")
            messagebox.showerror("Error", str(e))

        finally:
            self.progress_label.config(text="")
            self.progress_bar['value'] = 0
            self.time_label.config(text="")

    def update_progress_bar(self, value):
        self.progress_bar['value'] = value
        self.root.update_idletasks()

    def update_progress_label(self, text):
        self.progress_label.config(text=text)
        self.root.update_idletasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = OverlayToolApp(root)
    root.mainloop()
