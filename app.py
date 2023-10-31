from flask import Flask, render_template, request, jsonify, logging
from requests_toolbelt.multipart.encoder import MultipartEncoder
from logging.config import dictConfig
from datetime import datetime
import uuid, os, socket, requests, argparse

template_dir = os.path.abspath('templates')
static_dir = os.path.abspath('static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

#Get local IP address to bind server to
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually establish a connection; it just retrieves the preferred interface's IP address.
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

# Provides the ability to set a custom port as an argument when starting the app. Defaults to 5000
def get_args():
    parser = argparse.ArgumentParser(description="Start the service on a specific port.")
    parser.add_argument('-p', '--port', type=int, default=5000, help="Port to start the service on. Defaults to 5000.")
    args = parser.parse_args()
    return args

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})

print_jobs = []  # List to hold print jobs data

@app.route('/')
def index():
    return render_template('index.html') # Your HTML form for submitting print jobs

@app.route('/submit', methods=['POST']) # Route to submit post request to Vasion API Print service
def submit_job():
    # Handling the file
    file = request.files.get('file')
    if file:
        file_content = file.read()
        filename = file.filename
    else:
        return jsonify({"status": "error", "message": "No file provided."}), 400

   # Generate a unique job ID per job
    job_id = str(uuid.uuid4())

    # Extract data from the HTML form
    data = {
        "queue": request.form.get('queue'),
        "filename": filename,
        "jobID": job_id,
        "deviceName": socket.gethostname(),
        "duplex": request.form.get('duplex') == 'true',
        "color": request.form.get('color') == 'true',
        "copies": int(request.form.get('copies')),
        "paperSource": request.form.get('paperSource'),
        "username": request.form.get('username'),
        "statusURL": request.form.get('statusURL')
    }

    #Assign the URL defined in the form for where to send the print job requests to
    api_url = request.form.get('apiUrl')

    files = {
        'file': (filename, file_content)
    }

    # Store initial job details for reporting
    new_job = {
        "jobID": job_id,
        "filename": filename,
        "queue": request.form.get('queue'),
        "status": "submitted",  # Initial status
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    print_jobs.append(new_job)

    # Send POST request to the Vasion API to submit print job
    response = requests.post(api_url, data=data, files=files, verify=False)

    app.logger.debug("API response content: %s", response.text)

    # Handle the response based on status codes. This is just acknowledging the receipt of the file to be printed 
    # not if it was actually printed
    if response.status_code == 200 or response.status_code == 202:
        return jsonify({"status": "success", "message": "Print job submitted successfully."})
    elif 400 <= response.status_code < 500:
        return jsonify({"error": "Client error. Please check your request."}), response.status_code
    elif 500 <= response.status_code < 600:
        return jsonify({"error": "Server error. Please try again later."}), response.status_code
    else:
        return jsonify({"error": "Unexpected response: " + response.text}), response.status_code

#Route for receiving print job statuses back from the API Print Service. This provides the confirmation if a job was printed or not
@app.route('/print-job-status', methods=['POST'])
def update_job_status():
    global print_jobs
    
    # Extract the job status details from the request
    job_details = request.json
    jobID = job_details.get("jobID")
    status = job_details.get("status")
    # Extract other job details from the request (if needed)
    
    for job in print_jobs:
        if job["jobID"] == jobID:
            job["status"] = status  # Update only the status
            break
    
    # Ensure the print_jobs list doesn't exceed 10 entries. This is just to keep the interface clean for the demo
    while len(print_jobs) > 10:
        print_jobs.pop(0)
    
    return jsonify({"status": "success", "message": "Print job status updated successfully."})

#A simple route to update the list of print jobs at the bottom of the interface.
@app.route('/get-print-jobs', methods=['GET'])
def get_print_jobs():
    global print_jobs
    return jsonify(print_jobs)

if __name__ == '__main__':
    args = get_args()
    port = args.port

    app.run(host=get_local_ip(), port=port, debug=True)
