from flask import Flask, render_template, request, jsonify, logging
from requests_toolbelt.multipart.encoder import MultipartEncoder
from logging.config import dictConfig
from datetime import datetime
import uuid
import socket
import requests

app = Flask(__name__)

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

@app.route('/submit', methods=['POST'])
def submit_job():
    # Handling the file
    file = request.files.get('file')
    if file:
        file_content = file.read()
        filename = file.filename
    else:
        return jsonify({"status": "error", "message": "No file provided."}), 400

   # Generate a unique job ID
    job_id = str(uuid.uuid4())

    # Extract data from the form
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

    api_url = request.form.get('apiUrl')

    files = {
        'file': (filename, file_content)
    }

    # Store initial job details
    new_job = {
        "jobID": job_id,
        "filename": filename,
        "queue": request.form.get('queue'),
        "status": "submitted",  # Initial status
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    print_jobs.append(new_job)

    # Send POST request to the Vasion API
    response = requests.post(api_url, data=data, files=files, verify=False)

    app.logger.debug("API response content: %s", response.text)

    # Handle the response based on status codes
    # Handle the response based on status codes
    if response.status_code == 200 or response.status_code == 202:
        return jsonify({"status": "success", "message": "Print job submitted successfully."})
    elif 400 <= response.status_code < 500:
        return jsonify({"error": "Client error. Please check your request."}), response.status_code
    elif 500 <= response.status_code < 600:
        return jsonify({"error": "Server error. Please try again later."}), response.status_code
    else:
        return jsonify({"error": "Unexpected response: " + response.text}), response.status_code

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
    
    # Ensure the print_jobs list doesn't exceed 10 entries
    while len(print_jobs) > 10:
        print_jobs.pop(0)
    
    return jsonify({"status": "success", "message": "Print job status updated successfully."})


@app.route('/get-print-jobs', methods=['GET'])
def get_print_jobs():
    global print_jobs
    return jsonify(print_jobs)

if __name__ == '__main__':
    app.run(debug=True)
