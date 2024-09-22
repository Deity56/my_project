from flask import Flask
import signal
import sys

app = Flask(__name__)

def signal_handler(sig, frame):
    print('Shutting down gracefully...')
    # Clean up code here, close sockets, etc.
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

@app.route('/')
def index():
    return "Hello, World!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)