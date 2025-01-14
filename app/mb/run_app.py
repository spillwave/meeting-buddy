# run_app.py
import subprocess
import sys
import os
import pathlib
import threading
from datetime import datetime
import traceback
import logging
import logging.handlers
from logging.handlers import RotatingFileHandler

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
    error_log = logs_dir / f'error_{timestamp}.log'
    
    # Set up root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler for error log
    error_handler = RotatingFileHandler(
        error_log, maxBytes=10000000, backupCount=5
    )
    error_handler.setFormatter(detailed_formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(detailed_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # Ensure all loggers propagate to root
    logging.getLogger('app').propagate = True
    
    return service_log, streamlit_log

def monitor_process(process, name):
    """Monitor a process and log its exit code and any errors"""
    logger = logging.getLogger(__name__)
    exit_code = process.wait()
    if exit_code != 0:
        error_output = process.stderr.read() if process.stderr else "No error output available"
        logger.error(f"{name} process exited with code {exit_code}")
        logger.error(f"{name} error output: {error_output}")
        return False
    return True

def main():
    # Change to project root directory
    os.chdir(ROOT_PATH)
    global service_process, streamlit_process
    
    # Setup logging first thing
    service_log, streamlit_log = setup_logging()
    logger = logging.getLogger(__name__)
    
    # Set environment variables for child processes to enable full logging
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    try:
        logger.info("Starting Meeting Buddy application...")
        
        # Start the transcription service with output to console
        try:
            service_env = os.environ.copy()
            service_env['PYTHONPATH'] = f"{ROOT_PATH}:{service_env.get('PYTHONPATH', '')}"
            
            service_process = subprocess.Popen(
                [sys.executable, '-u', 'app/mb/service.py'],  # -u for unbuffered output
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                env=service_env
            )
            logger.info("Service process started successfully")
        except Exception as e:
            logger.error(f"Failed to start service process: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        # Start the Streamlit app
        try:
            streamlit_env = os.environ.copy()
            streamlit_env['PYTHONPATH'] = f"{ROOT_PATH}:{streamlit_env.get('PYTHONPATH', '')}"
            
            streamlit_process = subprocess.Popen(
                ['streamlit', 'run', 'app/mb/home.py', 
                 '--server.address', '0.0.0.0',
                 '--server.runOnSave', 'false',
                 '--logger.level=debug'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                env=streamlit_env
            )
            logger.info("Streamlit process started successfully")
        except Exception as e:
            logger.error(f"Failed to start Streamlit process: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        # Create threads to handle output streaming
        def stream_output(process, prefix, logfile):
            logger = logging.getLogger(f"{__name__}.{prefix.lower()}")
            
            def _stream_pipe(pipe, is_error=False):
                for line in iter(pipe.readline, ''):
                    message = line.strip()
                    if message:
                        # Immediately print to console for real-time output
                        print(f"{prefix}: {message}", flush=True)
                        
                        # Also log through the logging system for file output
                        if is_error and ("ERROR" in message or "Exception" in message):
                            logger.error(message)
                        else:
                            logger.info(message)
                        
                        # Write to the dedicated log file
                        with open(logfile, 'a') as log:
                            log.write(f"{datetime.now().isoformat()} - {prefix}: {message}\n")
                            log.flush()
                
                pipe.close()
            
            # Create separate threads for stdout and stderr to prevent blocking
            stdout_thread = threading.Thread(target=_stream_pipe, args=(process.stdout,))
            stderr_thread = threading.Thread(target=_stream_pipe, args=(process.stderr, True))
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for both streams to complete
            stdout_thread.join()
            stderr_thread.join()
            
            # Check final process status
            exit_code = process.poll()
            if exit_code is not None and exit_code != 0:
                logger.error(f"{prefix} process exited with code {exit_code}")
        
        service_thread = threading.Thread(target=stream_output, args=(service_process, "Service", service_log))
        streamlit_thread = threading.Thread(target=stream_output, args=(streamlit_process, "Streamlit", streamlit_log))
        
        service_thread.daemon = True
        streamlit_thread.daemon = True
        
        service_thread.start()
        streamlit_thread.start()

        # Monitor both processes
        service_monitor = threading.Thread(target=monitor_process, args=(service_process, "Service"))
        streamlit_monitor = threading.Thread(target=monitor_process, args=(streamlit_process, "Streamlit"))
        
        service_monitor.daemon = True
        streamlit_monitor.daemon = True
        
        service_monitor.start()
        streamlit_monitor.start()

        # Wait for the Streamlit app to exit
        streamlit_process.wait()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("Cleaning up processes...")
        # Terminate the transcription service
        if service_process and service_process.poll() is None:
            try:
                service_process.terminate()
                service_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Service process did not terminate gracefully, forcing kill")
                service_process.kill()
            except Exception as e:
                logger.error(f"Error terminating service process: {str(e)}")

        # Terminate the Streamlit app
        if streamlit_process and streamlit_process.poll() is None:
            try:
                streamlit_process.terminate()
                streamlit_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Streamlit process did not terminate gracefully, forcing kill")
                streamlit_process.kill()
            except Exception as e:
                logger.error(f"Error terminating Streamlit process: {str(e)}")

        logger.info("Application shutdown complete")


if __name__ == '__main__':
    main()
