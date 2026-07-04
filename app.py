import os
import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image

import upscaler
import interpolator
import sys

# Support PyInstaller frozen path
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup basic CustomTkinter configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ImageUpscalerFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.input_file = None
        self.output_file = None
        self.setup_ui()
        self.check_engine()
        
    def setup_ui(self):
        # Header Section
        self.title_label = ctk.CTkLabel(self, text="AI Image Upscaler", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(10, 5), anchor="w")
        
        self.subtitle_label = ctk.CTkLabel(self, text="Get that 'Remastered' 4x crisp look using Real-ESRGAN", font=ctk.CTkFont(size=13), text_color="gray")
        self.subtitle_label.pack(pady=(0, 20), anchor="w")
        
        # Main Card Frame
        self.card_frame = ctk.CTkFrame(self, fg_color=("#EAEAEA", "#1E1E22"), border_width=1, border_color=("#D1D1D1", "#2D2D33"))
        self.card_frame.pack(pady=10, fill="both", expand=True)
        
        # File Selection
        self.select_btn = ctk.CTkButton(self.card_frame, text="Select Image to Upscale", command=self.select_image)
        self.select_btn.pack(pady=(35, 10))
        
        self.file_label = ctk.CTkLabel(self.card_frame, text="No file selected", text_color="gray")
        self.file_label.pack(pady=(0, 20))
        
        # Settings Container
        self.settings_frame = ctk.CTkFrame(self.card_frame, fg_color="transparent")
        self.settings_frame.pack(pady=10, padx=40, fill="x")
        
        # Quality Option
        self.model_var = ctk.StringVar(value="Fast (Best for general)")
        self.model_label = ctk.CTkLabel(self.settings_frame, text="Quality / Speed:", font=ctk.CTkFont(weight="bold"))
        self.model_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.model_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.model_var, values=["Fast (Best for general)", "Ultra Quality (Slower)", "Anime/Art"])
        self.model_menu.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        
        # Scale Option
        self.scale_var = ctk.StringVar(value="4x")
        self.scale_label = ctk.CTkLabel(self.settings_frame, text="Upscale Size:", font=ctk.CTkFont(weight="bold"))
        self.scale_label.grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.scale_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.scale_var, values=["2x", "3x", "4x"])
        self.scale_menu.grid(row=1, column=1, padx=10, pady=8, sticky="ew")

        # Format Option
        self.format_var = ctk.StringVar(value="JPG (Smaller File)")
        self.format_label = ctk.CTkLabel(self.settings_frame, text="Output Format:", font=ctk.CTkFont(weight="bold"))
        self.format_label.grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.format_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.format_var, values=["JPG (Smaller File)", "PNG (Lossless)", "WEBP"])
        self.format_menu.grid(row=2, column=1, padx=10, pady=8, sticky="ew")
        
        self.settings_frame.columnconfigure(1, weight=1)
        
        # Progress and Status
        self.status_label = ctk.CTkLabel(self.card_frame, text="Ready", font=ctk.CTkFont(size=13))
        self.status_label.pack(pady=(25, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.card_frame, width=420)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        # Upscale Button
        self.upscale_btn = ctk.CTkButton(self, text="Upscale Image", command=self.start_upscaling, height=42, font=ctk.CTkFont(size=15, weight="bold"))
        self.upscale_btn.pack(pady=20, fill="x")
        self.upscale_btn.configure(state="disabled")

    def check_engine(self):
        if not upscaler.is_engine_installed():
            self.status_label.configure(text="Downloading AI Engine (one-time setup)...")
            self.select_btn.configure(state="disabled")
            self.upscale_btn.configure(state="disabled")
            
            def update_progress(val):
                if isinstance(val, str):
                    self.after(0, lambda: self.status_label.configure(text=val))
                else:
                    self.after(0, lambda: self.progress_bar.set(val))
                    self.after(0, lambda: self.status_label.configure(text=f"Downloading: {int(val * 100)}%"))
                    
            def finish_download():
                self.after(0, lambda: self.status_label.configure(text="Ready"))
                self.after(0, lambda: self.progress_bar.set(0))
                self.after(0, lambda: self.select_btn.configure(state="normal"))
                if self.input_file:
                    self.after(0, lambda: self.upscale_btn.configure(state="normal"))
                
            def run_download():
                try:
                    upscaler.download_engine(update_progress)
                    finish_download()
                except Exception as e:
                    self.after(0, lambda: self.status_label.configure(text=f"Download error: {e}", text_color="red"))
                    
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
            self.after(0, lambda: self.status_label.configure(text=f"Finished! Saved as *_upscaled.{format_val}", text_color="#00CC66"))
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


class VideoInterpolatorFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.input_file = None
        self.output_file = None
        self._is_processing = False
        self.setup_ui()
        self.check_engines()
        
    def setup_ui(self):
        # Header Section
        self.title_label = ctk.CTkLabel(self, text="AI Video Interpolator", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(10, 5), anchor="w")
        
        self.subtitle_label = ctk.CTkLabel(self, text="Convert 24fps/30fps videos to silky smooth 60fps+", font=ctk.CTkFont(size=13), text_color="gray")
        self.subtitle_label.pack(pady=(0, 20), anchor="w")
        
        # Main Card Frame
        self.card_frame = ctk.CTkFrame(self, fg_color=("#EAEAEA", "#1E1E22"), border_width=1, border_color=("#D1D1D1", "#2D2D33"))
        self.card_frame.pack(pady=10, fill="both", expand=True)
        
        # File Selection
        self.select_btn = ctk.CTkButton(self.card_frame, text="Select Video to Interpolate", command=self.select_video)
        self.select_btn.pack(pady=(35, 10))
        
        self.file_label = ctk.CTkLabel(self.card_frame, text="No video selected", text_color="gray")
        self.file_label.pack(pady=(0, 20))
        
        # Settings Container
        self.settings_frame = ctk.CTkFrame(self.card_frame, fg_color="transparent")
        self.settings_frame.pack(pady=5, fill="x", padx=40)
        
        # Multiplier Option
        self.scale_var = ctk.StringVar(value="2x (Standard Smoothness)")
        ctk.CTkLabel(self.settings_frame, text="Interpolation Multiplier:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.scale_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.scale_var, values=["2x (Standard Smoothness)", "3x", "4x (Ultra Smooth)"])
        self.scale_menu.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        
        # Model Option
        self.model_var = ctk.StringVar(value="rife-v4.6 (Best Quality)")
        ctk.CTkLabel(self.settings_frame, text="AI Model:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.model_menu = ctk.CTkOptionMenu(self.settings_frame, variable=self.model_var, values=["rife-v4.6 (Best Quality)", "rife-v4 (Fast)", "rife-v3.1", "rife-anime (Anime)"])
        self.model_menu.grid(row=1, column=1, padx=10, pady=8, sticky="ew")
        
        # GPU Checkbox Switch
        self.gpu_var = ctk.BooleanVar(value=True)
        self.gpu_switch = ctk.CTkSwitch(self.settings_frame, text="Use GPU (uncheck if you get Vulkan errors)", variable=self.gpu_var, font=ctk.CTkFont(size=12))
        self.gpu_switch.grid(row=2, column=0, columnspan=2, padx=10, pady=(12, 5), sticky="w")
        
        self.settings_frame.columnconfigure(1, weight=1)
        
        # Progress and Status
        self.status_label = ctk.CTkLabel(self.card_frame, text="Ready", font=ctk.CTkFont(size=13), wraplength=480)
        self.status_label.pack(pady=(25, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.card_frame, width=420)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        # Action Buttons Container
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20, fill="x")
        
        self.interpolate_btn = ctk.CTkButton(self.btn_frame, text="Convert Video", command=self.start_interpolation, height=42, font=ctk.CTkFont(size=15, weight="bold"))
        self.interpolate_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.interpolate_btn.configure(state="disabled")
        
        self.cancel_btn = ctk.CTkButton(self.btn_frame, text="Cancel", command=self.cancel_interpolation, height=42, width=120, font=ctk.CTkFont(size=14), fg_color="#CC3333", hover_color="#AA2222")
        self.cancel_btn.pack(side="right")
        self.cancel_btn.configure(state="disabled")

    def check_engines(self):
        if not interpolator.is_engine_installed():
            self.status_label.configure(text="Downloading AI Engines (one-time setup, ~150MB)...")
            self.select_btn.configure(state="disabled")
            self.interpolate_btn.configure(state="disabled")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()

            def update_progress(val):
                self.after(0, lambda: self.status_label.configure(text=val))

            def finish_download():
                self.after(0, lambda: self.progress_bar.stop())
                self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
                self.after(0, lambda: self.progress_bar.set(0))
                self.after(0, lambda: self.status_label.configure(text="Ready"))
                self.after(0, lambda: self.select_btn.configure(state="normal"))
                if self.input_file:
                    self.after(0, lambda: self.interpolate_btn.configure(state="normal"))

            def run_download():
                try:
                    interpolator.download_engine(update_progress)
                    finish_download()
                except Exception as e:
                    self.after(0, lambda: self.progress_bar.stop())
                    self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
                    self.after(0, lambda: self.status_label.configure(text=f"Download error: {e}", text_color="red"))

            threading.Thread(target=run_download, daemon=True).start()

    def select_video(self):
        filetypes = (
            ('Video files', '*.mp4 *.mkv *.avi *.mov *.webm'),
            ('All files', '*.*')
        )
        filename = filedialog.askopenfilename(title='Select a video', filetypes=filetypes)
        if filename:
            self.input_file = filename
            self.file_label.configure(text=os.path.basename(filename))
            self.interpolate_btn.configure(state="normal")

    def start_interpolation(self):
        if not self.input_file:
            return

        self._is_processing = True
        self.interpolate_btn.configure(state="disabled")
        self.select_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status_label.configure(text="Initializing AI Pipeline...", text_color="white")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        scale_val = int(self.scale_var.get()[0])
        model_name = self.model_var.get().split(" (")[0]
        use_gpu = self.gpu_var.get()

        base, ext = os.path.splitext(self.input_file)
        self.output_file = f"{base}_{scale_val}x_smooth.mp4"

        def on_progress(val):
            self.after(0, lambda: self.status_label.configure(text=val, text_color="white"))
            import re
            match = re.search(r"(\d+\.?\d*)%", val)
            if match:
                pct = float(match.group(1)) / 100.0
                self.after(0, lambda: self._set_determinate_progress(pct))

        def on_complete():
            self._is_processing = False
            self.after(0, lambda: self.progress_bar.stop())
            self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self.status_label.configure(
                text=f"Finished! Saved as {os.path.basename(self.output_file)}",
                text_color="#00CC66"
            ))
            self.after(0, lambda: self.interpolate_btn.configure(state="normal"))
            self.after(0, lambda: self.select_btn.configure(state="normal"))
            self.after(0, lambda: self.cancel_btn.configure(state="disabled"))

        def on_error(err):
            self._is_processing = False
            self.after(0, lambda: self.progress_bar.stop())
            self.after(0, lambda: self.progress_bar.set(0))
            
            try:
                log_path = os.path.join(SCRIPT_DIR, "error_log.txt")
                with open(log_path, "a", encoding="utf-8") as f:
                    import datetime
                    f.write(f"\n{'='*60}\n{datetime.datetime.now()}\n{err}\n")
            except Exception:
                pass

            short_err = err.split("\n")[0][:300] if err else "Unknown error"
            self.after(0, lambda: self.status_label.configure(text=f"Error: {short_err}", text_color="red"))
            self.after(0, lambda: self.interpolate_btn.configure(state="normal"))
            self.after(0, lambda: self.select_btn.configure(state="normal"))
            self.after(0, lambda: self.cancel_btn.configure(state="disabled"))

        interpolator.interpolate_video(
            self.input_file,
            self.output_file,
            multiplier=scale_val,
            model=model_name,
            use_gpu=use_gpu,
            progress_callback=on_progress,
            completion_callback=on_complete,
            error_callback=on_error
        )

    def _set_determinate_progress(self, value):
        try:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(value)
        except Exception:
            pass

    def cancel_interpolation(self):
        if self._is_processing:
            self.status_label.configure(
                text="Cancellation will take effect after current step finishes...",
                text_color="orange"
            )
            self.cancel_btn.configure(state="disabled")


class MediaEnhancerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AI Media Studio - Unified Enhancer")
        self.geometry("920x660")
        self.resizable(False, False)
        
        # Grid layout (1 row, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Sidebar Frame
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=("#D9D9D9", "#111113"))
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        # Sidebar Title
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="AI Media Studio", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 5))
        
        self.logo_subtitle = ctk.CTkLabel(self.sidebar_frame, text="Unified AI tools", font=ctk.CTkFont(size=11), text_color="gray")
        self.logo_subtitle.grid(row=1, column=0, padx=20, pady=(0, 25))
        
        # Sidebar Buttons
        self.btn_image = ctk.CTkButton(self.sidebar_frame, text="Image Upscaler", height=40, font=ctk.CTkFont(weight="bold"), anchor="w", command=lambda: self.select_tab("image"))
        self.btn_image.grid(row=2, column=0, padx=15, pady=8, sticky="ew")
        
        self.btn_video = ctk.CTkButton(self.sidebar_frame, text="Video Interpolator", height=40, font=ctk.CTkFont(weight="bold"), anchor="w", command=lambda: self.select_tab("video"))
        self.btn_video.grid(row=3, column=0, padx=15, pady=8, sticky="ew")
        
        # Sidebar footer info
        self.info_label = ctk.CTkLabel(self.sidebar_frame, text="System: Windows x64\nVersion: 1.0.0", font=ctk.CTkFont(size=11), text_color="gray", justify="left")
        self.info_label.grid(row=5, column=0, padx=20, pady=20, sticky="s")
        
        # Main Tab Frames
        self.upscaler_frame = ImageUpscalerFrame(self)
        self.interpolator_frame = VideoInterpolatorFrame(self)
        
        # Select default tab
        self.select_tab("image")
        
    def select_tab(self, name):
        # Reset all buttons
        self.btn_image.configure(fg_color="transparent", text_color=("#1A1A1A", "#E5E5E5"))
        self.btn_video.configure(fg_color="transparent", text_color=("#1A1A1A", "#E5E5E5"))
        
        if name == "image":
            self.btn_image.configure(fg_color=("#3B8ED0", "#1F538D"), text_color="white")
            self.interpolator_frame.grid_forget()
            self.upscaler_frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=25)
        elif name == "video":
            self.btn_video.configure(fg_color=("#3B8ED0", "#1F538D"), text_color="white")
            self.upscaler_frame.grid_forget()
            self.interpolator_frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=25)

if __name__ == "__main__":
    app = MediaEnhancerApp()
    app.mainloop()
