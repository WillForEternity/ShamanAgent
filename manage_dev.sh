#!/bin/bash

# Script to manage ShamanAgent development servers

PROJECT_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAURI_APP_DIR="$PROJECT_ROOT_DIR/tauri_app"
PYTHON_VENV_PATH="$PROJECT_ROOT_DIR/.venv/bin"

BACKEND_PID_FILE="$PROJECT_ROOT_DIR/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT_DIR/.frontend.pid"
FRONTEND_LOG_FILE="$PROJECT_ROOT_DIR/frontend_dev.log"
BACKEND_LOG_FILE="$PROJECT_ROOT_DIR/backend_dev.log"

# Function to kill a process by PID file
kill_process_from_pid_file() {
    local pid_file="$1"
    local process_name="$2"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null; then
            echo "Stopping $process_name (PID: $pid)..."
            kill "$pid" # Try graceful kill first
            sleep 2
            if ps -p "$pid" > /dev/null; then
                echo "$process_name (PID: $pid) did not stop gracefully, forcing kill..."
                kill -9 "$pid"
            fi
            rm "$pid_file"
            echo "$process_name stopped."
        else
            echo "$process_name (PID: $pid from $pid_file) not running or PID file stale."
            rm "$pid_file"
        fi
    else
        echo "PID file $pid_file not found. $process_name might not be running (or wasn't started by this script)."
    fi
}

# Function to kill backend specifically (also tries port)
kill_backend() {
    echo "Attempting to stop backend server..."
    kill_process_from_pid_file "$BACKEND_PID_FILE" "Backend Uvicorn server"

    echo "Checking if backend is running on port 8000 (fallback)..."
    local backend_pid_on_port=$(lsof -ti :8000)
    if [ -n "$backend_pid_on_port" ]; then
        echo "Found backend process on port 8000 (PID: $backend_pid_on_port). Stopping it..."
        kill "$backend_pid_on_port"
        sleep 1
        if ps -p "$backend_pid_on_port" > /dev/null; then # Check if still running
           kill -9 "$backend_pid_on_port"
        fi
        echo "Backend process on port 8000 stopped."
    else
        echo "No backend process found listening on port 8000."
    fi
}

# Function to kill frontend (Tauri dev process and its children)
kill_frontend() {
    echo "Attempting to stop frontend Tauri dev server..."
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local tauri_dev_pid=$(cat "$FRONTEND_PID_FILE")
        if ps -p "$tauri_dev_pid" > /dev/null; then
            echo "Stopping Tauri dev server (PID: $tauri_dev_pid) and its children..."
            pkill -P "$tauri_dev_pid" # Kills children of tauri_dev_pid
            sleep 1
            kill "$tauri_dev_pid"    # Kills tauri_dev_pid itself
            sleep 2
            if ps -p "$tauri_dev_pid" > /dev/null; then
                echo "Tauri dev server (PID: $tauri_dev_pid) did not stop gracefully, forcing kill..."
                kill -9 "$tauri_dev_pid"
            fi
            rm "$FRONTEND_PID_FILE"
            echo "Tauri dev server stopped."
        else
            echo "Tauri dev server (PID: $tauri_dev_pid from $FRONTEND_PID_FILE) not running or PID file stale."
            rm "$FRONTEND_PID_FILE"
        fi
    else
        echo "PID file $FRONTEND_PID_FILE not found. Tauri dev server might not be running (or wasn't started by this script)."
    fi
}

start_backend() {
    if [ -f "$BACKEND_PID_FILE" ] && ps -p $(cat "$BACKEND_PID_FILE") > /dev/null; then
        echo "Backend Uvicorn server already running (PID: $(cat "$BACKEND_PID_FILE"))."
        return 0
    fi
    echo "Starting Backend Uvicorn server..."
    if [ ! -f "$PYTHON_VENV_PATH/uvicorn" ]; then
        echo "Error: Uvicorn not found in $PYTHON_VENV_PATH. Make sure the virtual environment is set up and 'uvicorn' is installed."
        return 1
    fi
    cd "$PROJECT_ROOT_DIR"
    nohup "$PYTHON_VENV_PATH/uvicorn" vision_bridge:app --port 8000 > "$BACKEND_LOG_FILE" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    echo "Backend Uvicorn server starting (PID: $(cat "$BACKEND_PID_FILE")). Log: $BACKEND_LOG_FILE"
    sleep 3 # Give it a moment to start
    if ! ps -p $(cat "$BACKEND_PID_FILE") > /dev/null; then
        echo "Error: Backend Uvicorn server failed to start. Check $BACKEND_LOG_FILE"
        rm "$BACKEND_PID_FILE"
        return 1
    fi
    if ! lsof -i:8000 -sTCP:LISTEN -P -n > /dev/null; then # Check if listening
        echo "Warning: Backend started (PID $(cat "$BACKEND_PID_FILE")) but NOT detected on port 8000 after 3 seconds. Check $BACKEND_LOG_FILE"
    else
        echo "Backend confirmed listening on port 8000."
    fi
    return 0
}

start_frontend() {
    if [ -f "$FRONTEND_PID_FILE" ] && ps -p $(cat "$FRONTEND_PID_FILE") > /dev/null; then
        echo "Tauri dev server already running (PID: $(cat "$FRONTEND_PID_FILE"))."
        return 0
    fi
    echo "Starting Tauri dev server..."
    cd "$TAURI_APP_DIR"
    nohup cargo tauri dev > "$FRONTEND_LOG_FILE" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    echo "Tauri dev server process starting (PID: $(cat "$FRONTEND_PID_FILE")). Log: $FRONTEND_LOG_FILE"
    echo "Note: The app window should appear. For live console output, run 'cargo tauri dev' manually in a separate terminal."
    return 0
}

stop_all() {
    echo "Stopping all services..."
    kill_frontend
    kill_backend
    echo "All services stop sequence completed."
}

start_all() {
    echo "Starting all services..."
    start_backend
    backend_status=$?
    if [ $backend_status -ne 0 ]; then
        echo "Backend failed to start. Aborting frontend start."
        return 1
    fi
    start_frontend
    frontend_status=$?
    if [ $frontend_status -ne 0 ]; then
        echo "Frontend failed to start."
        return 1
    fi
    echo "All services start sequence completed."
}

restart_all() {
    echo "Restarting all services..."
    stop_all
    echo "Waiting a few seconds before restarting..."
    sleep 3
    start_all
}

status_all() {
    echo "--- Service Status ---"
    # Backend
    local backend_running_on_port=false
    local backend_pid_on_port=$(lsof -ti :8000)
    if [ -n "$backend_pid_on_port" ]; then
        backend_running_on_port=true
    fi

    if [ -f "$BACKEND_PID_FILE" ]; then
        local b_pid=$(cat "$BACKEND_PID_FILE")
        if ps -p "$b_pid" > /dev/null; then
            echo "Backend Uvicorn server (PID file): RUNNING (PID: $b_pid)"
            if $backend_running_on_port && [[ "$backend_pid_on_port" == *"$b_pid"* ]]; then
                 echo "  -> Listening on port 8000."
            else
                 echo "  -> WARNING: Running (PID $b_pid) but NOT detected on port 8000, or port used by different PID ($backend_pid_on_port)."
            fi
        else
            echo "Backend Uvicorn server (PID file): STOPPED (Stale PID file: $BACKEND_PID_FILE)"
            if $backend_running_on_port; then
                echo "  -> However, a process (PID: $backend_pid_on_port) IS listening on port 8000."
            fi
        fi
    elif $backend_running_on_port; then
        echo "Backend Uvicorn server (Port check): RUNNING (PID: $backend_pid_on_port on port 8000)" 
        echo "  (Not started by this script's 'start' command, or .backend.pid is missing)"
    else
        echo "Backend Uvicorn server: STOPPED"
    fi

    # Frontend
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local f_pid=$(cat "$FRONTEND_PID_FILE")
        if ps -p "$f_pid" > /dev/null; then
            echo "Tauri dev server (PID file): RUNNING (PID: $f_pid)"
        else
            echo "Tauri dev server (PID file): STOPPED (Stale PID file: $FRONTEND_PID_FILE)"
        fi
    else
        echo "Tauri dev server: UNKNOWN (If running, it wasn't started by this script's 'start' command, or .frontend.pid is missing)"
    fi
    echo "----------------------"
}

# Main script logic
case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        status_all
        ;;
    start_backend)
        start_backend
        ;;
    stop_backend)
        kill_backend
        ;;
    start_frontend)
        start_frontend
        ;;
    stop_frontend)
        kill_frontend
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|start_backend|stop_backend|start_frontend|stop_frontend}"
        exit 1
        ;;
esac

exit $?
