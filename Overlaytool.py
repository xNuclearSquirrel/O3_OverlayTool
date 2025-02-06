import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import time

# Import your custom classes
from VideoMaker import VideoMaker
from TransparentVideoMaker import TransparentVideoMaker
from OsdFileReader import OsdFileReader

class OverlayToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Overlay Tool")

        # Set scaling for high-resolution monitors
        self.root.tk.call('tk', 'scaling', 2.0)

        # Initialize variables with default paths
        self.osd_file_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.font_image_path = tk.StringVar(value='fonts/WS_BFx4_Nexus_Moonlight_2160p.png')
        self.chroma_key_hex = tk.StringVar(value='FF00FF')  # Default to magenta
        self.fps = tk.DoubleVar(value=30.0)
        self.transparent_background = tk.BooleanVar(value=False)  # Checkbox for transparency

        # Placeholder variables for VideoMaker and OsdFileReader
        self.video_maker = None
        self.osd_reader = None

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

        # Output path
        ttk.Label(input_frame, text="Output File:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.output_path, width=50).grid(row=1, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_output_path).grid(row=1, column=2, padx=5, pady=5)

        # Button to set output path same as input
        ttk.Button(input_frame, text="Same as Input", command=self.set_output_same_as_input).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        # Font image path
        ttk.Label(input_frame, text="Font Image:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.font_image_path, width=50).grid(row=3, column=1, sticky='we', padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_font_image).grid(row=3, column=2, padx=5, pady=5)

        # Transparent Background checkbox and Chroma Key
        ttk.Checkbutton(input_frame, text="Transparent Background", variable=self.transparent_background, command=self.toggle_chroma_key).grid(row=4, column=1, sticky='w', padx=5, pady=5)
        ttk.Label(input_frame, text="Chroma Key Hex:").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.chroma_key_entry = ttk.Entry(input_frame, textvariable=self.chroma_key_hex)
        self.chroma_key_entry.grid(row=5, column=1, sticky='w', padx=5, pady=5)

        # FPS
        ttk.Label(input_frame, text="FPS:").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.fps).grid(row=6, column=1, sticky='w', padx=5, pady=5)

        # Create Video button
        ttk.Button(input_frame, text="Create Video", command=self.start_creation).grid(row=7, column=1, pady=10)

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

    def toggle_chroma_key(self):
        """Enable or disable the chroma key field based on the Transparent Background checkbox."""
        if self.transparent_background.get():
            self.chroma_key_entry.config(state="disabled")
        else:
            self.chroma_key_entry.config(state="normal")
        self.update_output_extension()

    def update_output_extension(self):
        """Update the output file extension based on whether transparency is selected."""
        current_path = self.output_path.get()
        if not current_path:
            return

        new_extension = ".mov" if self.transparent_background.get() else ".mp4"
        base_name, _ = os.path.splitext(current_path)
        updated_path = base_name + new_extension
        self.output_path.set(updated_path)

    def browse_osd_file(self):
        filename = filedialog.askopenfilename(
            title="Select OSD file",
            filetypes=(("OSD files", "*.osd"), ("All files", "*.*"))
        )
        if filename:
            self.osd_file_path.set(filename)

    def browse_output_path(self):
        filename = filedialog.asksaveasfilename(
            title="Select output file",
            defaultextension=".mov",
            filetypes=(("MOV files", "*.mov"), ("All files", "*.*"))
        )
        if filename:
            self.output_path.set(filename)

    def set_output_same_as_input(self):
        input_path = self.osd_file_path.get()
        if input_path:
            output_path = os.path.splitext(input_path)[0] + '_OSD.mov'
            self.output_path.set(output_path)
            self.update_output_extension()
        else:
            messagebox.showerror("Error", "Please select an OSD file first.")

    def browse_font_image(self):
        filename = filedialog.askopenfilename(
            initialdir='fonts',
            title="Select Font Image",
            filetypes=(("PNG files", "*.png"), ("All files", "*.*"))
        )
        if filename:
            self.font_image_path.set(filename)

    def start_creation(self):
        if not self.osd_file_path.get():
            messagebox.showerror("Error", "Please select an OSD file.")
            return

        threading.Thread(target=self.create_video_process).start()

    def create_video_process(self):
        try:
            # 1) Read the OSD file
            self.osd_reader = OsdFileReader(self.osd_file_path.get())

            # 2) Initialize whichever VideoMaker is appropriate
            if self.transparent_background.get():
                self.video_maker = TransparentVideoMaker(
                    osd_reader=self.osd_reader,
                    font_image_path=self.font_image_path.get(),
                    fps=self.fps.get()
                )
            else:
                self.video_maker = VideoMaker(
                    osd_reader=self.osd_reader,
                    font_image_path=self.font_image_path.get(),
                    chroma_key_hex=self.chroma_key_hex.get(),
                    fps=self.fps.get()
                )

            # 3) Determine output path
            output_path = self.output_path.get()
            if not output_path:
                extension = ".mov" if self.transparent_background.get() else ".mp4"
                output_path = os.path.splitext(self.osd_file_path.get())[0] + '_OSD' + extension

            # 4) Progress callback to update the GUI
            start_time = time.time()

            def progress_callback(percentage, frame_num):
                # Update the progress bar
                self.progress_bar['value'] = percentage

                # Compute and display estimated remaining time + FPS every 50 frames
                if frame_num % 25 == 0 and frame_num > 0:
                    elapsed_time = time.time() - start_time
                    frames_processed = frame_num
                    frames_remaining = self.video_maker.total_frames - frames_processed

                    if frames_remaining > 0 and elapsed_time > 0:
                        # Estimate remaining time
                        estimated_remaining_time = (elapsed_time / frames_processed) * frames_remaining

                        # Convert seconds into h/m/s if needed
                        remaining_str = self.format_time(estimated_remaining_time)

                        # Calculate current FPS
                        current_fps = frames_processed / elapsed_time

                        # Update the label with both time and FPS
                        self.time_label.config(
                            text=f"Estimated time remaining: {remaining_str} - Current FPS: {current_fps:.2f}"
                        )

                self.update_progress_label(f"Processing: {int(percentage)}% complete")
                self.root.update_idletasks()

            # 5) Create the video
            self.video_maker.create_video(output_path, progress_callback=progress_callback)
            messagebox.showinfo("Success", f"Video created successfully at {output_path}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

        finally:
            self.progress_label.config(text="")
            self.progress_bar['value'] = 0
            self.time_label.config(text="")

    def update_progress_label(self, text):
        self.progress_label.config(text=text)
        self.root.update_idletasks()

    def format_time(self, total_seconds):
        if total_seconds >= 3600:
            # Hours + minutes
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        elif total_seconds >= 60:
            # Minutes + seconds
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            return f"{int(total_seconds)}s"


if __name__ == "__main__":
    root = tk.Tk()
    app = OverlayToolApp(root)
    root.mainloop()
