import os
import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image

import upscaler

# Setup basic CustomTkinter configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class UpscalerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AI Image Upscaler - Clear & Crisp")
        self.geometry("600x600")
        self.resizable(False, False)
        
        self.input_file = None
        self.output_file = None
        
        self.setup_ui()
        self.check_engine()
        
    def setup_ui(self):
        # Title Label
        self.title_label = ctk.CTkLabel(self, text="AI Image Upscaler", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 5))
        
        self.subtitle_label = ctk.CTkLabel(self, text="Get that 'Remastered' 4x crisp look using Real-ESRGAN", font=ctk.CTkFont(size=14), text_color="gray")
        self.subtitle_label.pack(pady=(0, 20))
        
        # Main Frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # File Selection
        self.select_btn = ctk.CTkButton(self.main_frame, text="Select Image to Upscale", command=self.select_image)
        self.select_btn.pack(pady=(30, 10))
        
        self.file_label = ctk.CTkLabel(self.main_frame, text="No file selected", text_color="gray")
        self.file_label.pack(pady=(0, 20))
        
        # Settings Frame
        self.settings_frame = ctk.CTkFrame(self.main_frame)
        self.settings_frame.pack(pady=10, padx=20, fill="x")

        # Model Option
        self.model_var = ctk.StringVar(value="Fast (Best for general)")
        self.model_label = ctk.CTkLabel(self.settings_frame, text="Quality/Speed:")
        self.model_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.model_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.model_var, values=["Fast (Best for general)", "Ultra Quality (Slower)", "Anime/Art"])
        self.model_menu.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        # Scale Option
        self.scale_var = ctk.StringVar(value="4x")
        self.scale_label = ctk.CTkLabel(self.settings_frame, text="Upscale Size:")
        self.scale_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.scale_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.scale_var, values=["2x", "3x", "4x"])
        self.scale_menu.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Format Option
        self.format_var = ctk.StringVar(value="JPG (Smaller File)")
        self.format_label = ctk.CTkLabel(self.settings_frame, text="Output Format:")
        self.format_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.format_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.format_var, values=["JPG (Smaller File)", "PNG (Lossless)", "WEBP"])
        self.format_menu.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        
        self.settings_frame.columnconfigure(1, weight=1)
        
        # Progress and Status
        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(20, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # Upscale Button
        self.upscale_btn = ctk.CTkButton(self, text="Upscale Image", command=self.start_upscaling, height=40, font=ctk.CTkFont(size=16, weight="bold"))
        self.upscale_btn.pack(pady=20)
        self.upscale_btn.configure(state="disabled")

    def check_engine(self):
        if not upscaler.is_engine_installed():
            self.status_label.configure(text="Downloading AI Engine (one-time setup)...")
            self.select_btn.configure(state="disabled")
            self.upscale_btn.configure(state="disabled")
            
            def update_progress(val):
                if isinstance(val, str):
                    self.status_label.configure(text=val)
                else:
                    self.progress_bar.set(val)
                    self.status_label.configure(text=f"Downloading: {int(val * 100)}%")
                    
            def finish_download():
                self.status_label.configure(text="Ready")
                self.progress_bar.set(0)
                self.select_btn.configure(state="normal")
                
            def run_download():
                upscaler.download_engine(update_progress)
                self.after(0, finish_download)
                
            threading.Thread(target=run_download, daemon=True).start()

    def select_image(self):
        filetypes = (
            ('Image files', '*.jpg *.jpeg *.png *.webp'),
            ('All files', '*.*')
        )
        filename = filedialog.askopenfilename(title='Select an image', filetypes=filetypes)
        if filename:
            self.input_file = filename
            self.file_label.configure(text=os.path.basename(filename))
            self.upscale_btn.configure(state="normal")

    def start_upscaling(self):
        if not self.input_file:
            return
            
        self.upscale_btn.configure(state="disabled")
        self.select_btn.configure(state="disabled")
        self.status_label.configure(text="Initializing AI Engine...")
        self.progress_bar.set(0)
        
        # Parse settings
        model_map = {
            "Fast (Best for general)": "realesr-animevideov3",
            "Ultra Quality (Slower)": "realesrgan-x4plus",
            "Anime/Art": "realesrgan-x4plus-anime"
        }
        format_map = {
            "JPG (Smaller File)": "jpg",
            "PNG (Lossless)": "png",
            "WEBP": "webp"
        }
        
        model_val = model_map.get(self.model_var.get(), "realesr-animevideov3")
        scale_val = self.scale_var.get().replace("x", "")
        format_val = format_map.get(self.format_var.get(), "jpg")
        
        # Default output file
        base, ext = os.path.splitext(self.input_file)
        self.output_file = f"{base}_upscaled.{format_val}"
        
        def on_progress(val):
            self.after(0, lambda: self.progress_bar.set(val))
            self.after(0, lambda: self.status_label.configure(text=f"Upscaling: {int(val * 100)}%"))
            
        def on_complete():
            self.after(0, lambda: self.status_label.configure(text=f"Finished! Saved as *_upscaled.{format_val}"))
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self.upscale_btn.configure(state="normal"))
            self.after(0, lambda: self.select_btn.configure(state="normal"))
            
        def on_error(err):
            self.after(0, lambda: self.status_label.configure(text=f"Error: {err}", text_color="red"))
            self.after(0, lambda: self.upscale_btn.configure(state="normal"))
            self.after(0, lambda: self.select_btn.configure(state="normal"))

        upscaler.upscale_image(
            self.input_file, 
            self.output_file, 
            model_name=model_val, 
            scale=scale_val, 
            out_format=format_val, 
            progress_callback=on_progress, 
            completion_callback=on_complete, 
            error_callback=on_error
        )

if __name__ == "__main__":
    app = UpscalerApp()
    app.mainloop()
