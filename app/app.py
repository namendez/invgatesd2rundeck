from __future__ import print_function
from flask import Flask, request, jsonify,Response
from functools import wraps
import requests
import json
import os
import sys
from time import sleep
import yaml
import re

#Required env variables.
SD_HTTP_USER = os.environ['SD_HTTP_USER']
SD_HTTP_PASS = os.environ['SD_HTTP_PASS']
RD_API_VERSION = os.environ['RD_API_VERSION']
RD_URL = os.environ['RD_URL']
RD_API_TOKEN = os.environ['RD_API_TOKEN']

#Optional env variables.
RD_RUNJOB_ENDPOINT = os.getenv('RD_RUNJOB_ENDPOINT', '/api/' + str(RD_API_VERSION) + '/job/{0}/executions?format=json') #job-id
RD_GET_JOB_DEFINITION = os.getenv('RD_GET_JOB_DEFINITION', '/api/' + str(RD_API_VERSION) + '/job/{0}?format=yaml') #job-id
RD_EXEC_OUTPUT_ENDPOINT = os.getenv('RD_EXEC_OUTPUT_ENDPOINT', '/api/' + str(RD_API_VERSION) + '/execution/{0}/output?format=json') #execution id
RD_EXEC_ENDPOINT = os.getenv('RD_EXEC_ENDPOINT', '/api/' + str(RD_API_VERSION) + '/execution/{0}?format=json') #execution id
RD_ASUSER = os.getenv('RD_ASUSER', 'rundeck')

DEBUG=os.getenv('DEBUG', False)
BIND_IP=os.getenv('BIND_IP', '0.0.0.0')
BIND_PORT=os.getenv('BIND_PORT', 5000)

#Max time to wait to return the response to Servicedesk, in seconds. If the job is still running, it will return "running".
SD_JOB_WAIT_TIMEOUT = os.getenv('SD_JOB_WAIT_TIMEOUT', 10)


app = Flask(__name__) 
app.secret_key = os.urandom(50)


#------------ Auth

def check_auth(username, password):
	return (username == SD_HTTP_USER and password == SD_HTTP_PASS)

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Unauthorized', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


#------------ Misc

#Cleans HTML from SD request when using HTML text field.
def cleanhtml(raw_html):
  cleanr = re.compile('<.+?>')
  cleantext = re.sub(cleanr, '', raw_html)
  return cleantext

#---------------------------------

@app.route("/sdtorundeck", methods=['POST'])
@requires_auth
def sdtorundeck():
	"""Converts ServiceDesk requests to Rundeck API format.

	Parameters (HTTP)
	----------
	sd-jobid
		Job-id of job to launch.
	sd-waittimeout : int, optional
		Time to wait before returning the response to Servicedesk.
	sd-returnlog : boolean, optional
		If True, it will return the job log to Servicedesk (only if the job is not running after `sd-waittimeout`), in log_output field.
	*argv : optional
		Parameters to be passed to Rundeck when executing the job.

	Returns
	----------
	sd_resultado : json
		{
			status: succeeded/failed/running,
			permalink: (to the job execution),
			log_output: (if sd-returnlog was set to True)
		}

	"""
    #Return 400 if parameter sd-jobid is not present.
	if not 'sd-jobid' in request.form:
		return Response(json.dumps({"message": "missing sd-jobid"}), status=400, mimetype='application/json')

	headers = {
	    'X-Rundeck-Auth-Token': RD_API_TOKEN,
	    'Content-Type': "application/json",
	    }
	payloadrundeck = {'asUser': RD_ASUSER, 'options': {}}

	#Create payload with every parameter received, except with those starting with sd-*
	for parametro in request.form:
		if not parametro.startswith('sd-'):
			payloadrundeck['options'][parametro] = cleanhtml(request.form[parametro])


	#Start the job.
	url = RD_URL + RD_RUNJOB_ENDPOINT.format(request.form['sd-jobid'])
	response = json.loads(requests.request("POST", url, data=json.dumps(payloadrundeck), headers=headers).content.decode('utf-8'))
	exec_id = response['id']
	permalink = response['permalink']

	sd_resultado = {'permalink': permalink}
	sd_resultado['log_output'] = None

	#Poll the RD API every 1 second SD_JOB_WAIT_TIMEOUT times, to check if the job ended and the job status. SD_JOB_WAIT_TIMEOUT can be overwritten by
	#sd-waittimeout parameter.
	try:
		global SD_JOB_WAIT_TIMEOUT
		SD_JOB_WAIT_TIMEOUT = int(request.form['sd-waittimeout'])
	except KeyError:
		pass

	while SD_JOB_WAIT_TIMEOUT > 0:
		sleep(1)
		url = RD_URL + RD_EXEC_ENDPOINT.format(exec_id)
		response = json.loads(requests.request("GET", url, headers=headers).content.decode('utf-8'))
		status = response['status']
		sd_resultado['status'] = status
		if status == 'succeeded' or status == 'failed':
			break
		else:
			SD_JOB_WAIT_TIMEOUT = SD_JOB_WAIT_TIMEOUT - 1

	#If SD_JOB_WAIT_TIMEOUT > 0 the job has ended.
	if SD_JOB_WAIT_TIMEOUT > 0: 
		if 'sd-returnlog' in request.form:
			url = RD_URL + RD_EXEC_OUTPUT_ENDPOINT.format(exec_id)
			response = json.loads(requests.request("GET", url, headers=headers).content.decode('utf-8'))
			sd_resultado['log_output'] = response['entries'][0]['log']
		else:
			pass


	return Response(json.dumps(sd_resultado), status=200, mimetype='application/json')



#---------------------------------

@app.route("/rundecktosd", methods=["POST"])
@requires_auth
def rundecktosd():
	"""Given a job-id, returns the values of the options (as a list) of the job which match the parameter passed.

	Parameters (HTTP)
	----------
	sd-jobid
		Job-id of job to launch.
	*argv
		Options of the job to be returned as a list. (option1, option2, etc.)

	Returns
	----------
	sd_resultado : json
		{
			'option1': ['val1', 'val2', valN'],
			'option2': ['valX', 'valY'] 	
		}

	"""
	print(request.form)
	if not 'sd-jobid' in request.form:
		return Response(json.dumps({"mensaje": "falta el parametro sd-jobid."}), status=400, mimetype='application/json')

	headers = {
	    'X-Rundeck-Auth-Token': RD_API_TOKEN,
	    'Content-Type': "application/json",
	    }


	url = RD_URL + RD_GET_JOB_DEFINITION.format(request.form['sd-jobid'])
	response = yaml.load(requests.request("GET", url, headers=headers).content)

	sd_resultado = {}

	try:
		options = response[0]['options']
		for item in options:
			if item['name'] in request.form:
				try:
					sd_resultado[item['name']] = item['values']
				except KeyError:
					sd_resultado[item['name']] = None

	except KeyError:
		pass

	return Response(json.dumps(sd_resultado), status=200, mimetype='application/json')





if __name__ == "__main__":
    app.run(debug=DEBUG, host=BIND_IP, port=BIND_PORT)
