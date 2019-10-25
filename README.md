# Invgate ServiceDesk to Rundeck API adapter.

Simple Flask app that allows to integrate [Invgate's ServiceDesk](https://www.invgate.com/service-desk/) ticketing system with [Rundeck](https://www.rundeck.com/).



## Run the app
~~~~
docker run -d --restart unless-stopped -p 5000:5000 \
                -e VERIFY_CERT=False \
                -e SD_HTTP_USER=sdrundeck \
                -e SD_HTTP_PASS=123456 \
                -e RD_API_VERSION=XX \
                -e RD_URL=http://rundeckserver.local \
                -e RD_API_TOKEN=12345 \
                namendez/invgatesd2rundeck
~~~~

Requests are authenticated using basic auth, using the user and pass provided to SD_HTTP_USER and SD_HTTP_PASS.

## Usage
### Launch a job
#### Request
~~~~
curl -X POST \
  http://localhost:5000/sdtorundeck \
  -H 'Authorization: Basic XXXX' \
  -H 'Content-Type: multipart/form-data' \
  -F sd-jobid=cd170d0b-d998-4437-a8a3-b44ffeb79df9 \
  -F sd-waittimeout=10 \
  -F sd-returnlog=true \
  -F 'testparam=hello world'
~~~~

#### Response
~~~~
{
    "permalink": "http://rundeck.local:4440/project/fakeproject/execution/show/64452",
    "log_output": "Received parameter: hello world",
    "status": "succeeded"
}
~~~~

### Getting values from an option
This is used to get the list of values from an option. For instance, if you have an option named "testoption" with the allowed values "foo, bar, baz", you could get these to dynamically populate any list within a process in Servicedesk.


#### Request
~~~~
curl -X POST \
  http://localhost:5000/rundecktosd \
  -H 'Authorization: Basic XXXX' \
  -H 'Content-Type: multipart/form-data' \
  -F sd-jobid=373c17b3-a544-4a50-9d3b-35343dea96ab \
  -F testoptions=
  -F testoptions2=
~~~~

#### Response
~~~~
{
    "testoption2": [
        "hello",
        "world"
    ],
    "testoptions": [
        "bar",
        "baz",
        "foo"
    ]
}
~~~~

## Dockerhub

Link to [Dockerhub](https://hub.docker.com/r/namendez/invgatesd2rundeck) repo.