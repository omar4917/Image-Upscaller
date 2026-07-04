import os
import zipfile
import requests
import subprocess
import threading
import re
import sys

# Support PyInstaller frozen path
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ENGINE_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
ENGINE_DIR = os.path.join(SCRIPT_DIR, "engine")
ENGINE_EXE = os.path.join(ENGINE_DIR, "realesrgan-ncnn-vulkan.exe")

def is_engine_installed():
    return os.path.exists(ENGINE_EXE)

def download_engine(progress_callback=None):
    if not os.path.exists(ENGINE_DIR):
        os.makedirs(ENGINE_DIR)
        
    zip_path = os.path.join(ENGINE_DIR, "engine.zip")
    
    # Download the zip file
    response = requests.get(ENGINE_URL, stream=True)
    total_length = response.headers.get('content-length')
    
    if total_length is None:
        with open(zip_path, 'wb') as f:
            f.write(response.content)
    else:
        dl = 0
        total_length = int(total_length)
        with open(zip_path, 'wb') as f:
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                f.write(data)
                if progress_callback:
                    progress_callback(dl / total_length)
                    
    # Extract
    if progress_callback:
        progress_callback("Extracting...")
        
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(ENGINE_DIR)
        
    # Cleanup zip
    os.remove(zip_path)
    
def upscale_image(input_path, output_path, model_name="realesr-animevideov3", scale="4", out_format="jpg", progress_callback=None, completion_callback=None, error_callback=None):
    if not is_engine_installed():
        if error_callback:
            error_callback("Engine not installed")
        return

    def run():
        try:
            # Command to run Real-ESRGAN
            cmd = [
                ENGINE_EXE,
                "-i", input_path,
                "-o", output_path,
                "-n", model_name,
                "-s", scale,
                "-f", out_format
            ]
            
            # Use startupinfo to hide the console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            pattern = re.compile(r'(\d+\.\d+)%')
            
            for line in process.stdout:
                match = pattern.search(line)
                if match and progress_callback:
                    prog = float(match.group(1)) / 100.0
                    progress_callback(prog)
            
            process.wait()
            
            if process.returncode == 0:
                if completion_callback:
                    completion_callback()
            else:
                if error_callback:
                    error_callback(f"Process failed with code {process.returncode}")
        except Exception as e:
            if error_callback:
                error_callback(str(e))

    thread = threading.Thread(target=run)
    thread.start()
