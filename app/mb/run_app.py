# run_app.py
import subprocess
import sys
import os
import pathlib
import threading
from datetime import datetime

# Get the project root directory
ROOT_PATH = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_PATH))

def setup_logging():
    # Create logs directory if it doesn't exist
    logs_dir = ROOT_PATH / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Create timestamped log files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    service_log = logs_dir / f'service_{timestamp}.log'
    streamlit_log = logs_dir / f'streamlit_{timestamp}.log'
    
    return service_log, streamlit_log

def main():
    # Change to project root directory
    os.chdir(ROOT_PATH)
    global service_process, streamlit_process
    
    # Setup logging
    service_log, streamlit_log = setup_logging()
    try:
        # Start the transcription service with output to console
        service_process = subprocess.Popen(
            [sys.executable, 'app/mb/service.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )

        # Start the Streamlit app with output to console and disable buffering
        streamlit_env = os.environ.copy()
        streamlit_env['PYTHONUNBUFFERED'] = '1'
        streamlit_process = subprocess.Popen(
            ['streamlit', 'run', 'app/mb/view.py', 
             '--server.address', '0.0.0.0',
             '--server.runOnSave', 'false'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            env=streamlit_env
        )

        # Create threads to handle output streaming
        def stream_output(process, prefix, logfile):
            with open(logfile, 'a') as log:
                while True:
                    # First check stdout
                    output = process.stdout.readline()
                    if output:
                        message = f"{prefix}: {output.strip()}"
                        print(message, flush=True)
                        log.write(f"{datetime.now().isoformat()} - {message}\n")
                        log.flush()
                        continue
                    
                    # Only check stderr if no stdout data
                    error = process.stderr.readline()
                    if error:
                        if "ERROR" in error or "Exception" in error:
                            message = f"{prefix} ERROR: {error.strip()}"
                        else:
                            message = f"{prefix}: {error.strip()}"
                        print(message, flush=True)
                        log.write(f"{datetime.now().isoformat()} - {message}\n")
                        log.flush()
                    
                    # Check if process has ended
                    if not output and not error and process.poll() is not None:
                        break

        service_thread = threading.Thread(target=stream_output, args=(service_process, "Service", service_log))
        streamlit_thread = threading.Thread(target=stream_output, args=(streamlit_process, "Streamlit", streamlit_log))
        
        service_thread.daemon = True
        streamlit_thread.daemon = True
        
        service_thread.start()
        streamlit_thread.start()

        # Wait for the Streamlit app to exit
        streamlit_process.wait()
    except KeyboardInterrupt:
        print("Shutting down...", flush=True)
    finally:
        # Terminate the transcription service
        if service_process.poll() is None:
            service_process.terminate()
            try:
                service_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                service_process.kill()

        # Terminate the Streamlit app
        if streamlit_process.poll() is None:
            streamlit_process.terminate()
            try:
                streamlit_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                streamlit_process.kill()

        print("Both processes have been terminated.", flush=True)


if __name__ == '__main__':
    main()
