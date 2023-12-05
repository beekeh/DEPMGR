import reflex as rx
import oyaml as yaml
import json
import os
import requests
import subprocess
from datetime import datetime
import uuid
import asyncio

class Base(rx.State):
    template_id: str = "minimal"
    cbutton_text: str = "CREATE"
    tbutton_text: str = "SHUTDOWN"
    cbutton_disabled: bool = False
    tbutton_disabled: bool = True
    clipboard_text: str = "" 
    dep_states: list = ['initial', 'deploying', 'deployed', 'failed']
    dep_state: str = dep_states[0]
    url: str = ""
    username: str = ""
    password: str = ""
    

    def initial_ui(self):
        self.dep_state = self.dep_states[0]
        self.cbutton_disabled = False
        self.tbutton_disabled = True
        self.clipboard_text = ""

    def waiting_ui(self):
        print("starting waiting_ui")
        self.dep_state = self.dep_states[1]
        self.cbutton_disabled = True
        print("finished waiting_ui")

    def deployed_ui(self):
        print("starting deployed_ui")
        self.dep_state = self.dep_states[2]
        self.cbutton_disabled = True
        self.tbutton_disabled = False
        print("finished deployed_ui")

    def shutdown_ui(self):
        print("starting shutdown_ui")
        self.dep_state = self.dep_states[0]
        self.tbutton_disabled = True
        print("finished shutdown_ui")

class CloudAPI(Base):
    running: bool = False
    _n_tasks: int = 0
    deployment_id: str = ""
    deployment_requested: bool = False
    @rx.var
    def config(self, filename='config.yaml') -> dict:
        file = os.path.dirname(os.path.abspath(__file__)) + '/config/' + filename
        with open(file) as f:
            return yaml.safe_load(f)
    
    @rx.background
    async def check_status_task(self):
        print("inside CloudAPI check_status_task")
        async with self:
            # The latest state values are always available inside the context
            if self._n_tasks > 0:
                # only allow 1 concurrent task
                return

            # State mutation is only allowed inside context block
            self._n_tasks += 1

        while True:
            async with self:
                # Check for stopping conditions inside context
                if self.dep_state == self.dep_states[1]:
                    if self.deployment_ready():
                        print("deployment ready")
                        self.dep_state = self.dep_states[2]
                        self.deployed_ui()
                        self.running = False
                    if not self.running:
                        self._n_tasks -= 1
                        return
            await asyncio.sleep(20)

    def start_deployment(self):
        print("inside CloudAPI start_deployment")
        self.dep_state = self.dep_states[1]
        self.running = True
        self.waiting_ui()
        yield
        self.deploy()
        if self.running:
            print("calling CloudAPI check_status_task")
            return CloudAPI.check_status_task

    def get_uuid(self) -> str:
        return str(uuid.uuid1())

    def get_api_key(self) -> str:
        return os.environ.get('EC_API_KEY')

    def headers(self) -> dict:
        return {'Authorization': f"ApiKey {self.get_api_key()}"}

    def template(self, template_id) -> dict:
        template_file_path = os.path.dirname(os.path.abspath(__file__)) + '/templates/' + template_id + '.json'
        with open(template_file_path) as f:
            return json.load(f)
        
    def payload(self, template_id='minimal') -> dict:
        return self.set_name(self.tag(self.template(template_id)))

    def set_name(self, payload):
        payload['name'] = self.get_uuid()
        return payload

    def get_ip(self) -> str:
        return subprocess.run(['curl', 'ifconfig.me'], capture_output=True).stdout.decode('utf-8').strip()

    def tag(self, t) -> dict:
        t['metadata'] = {'tags': []}
        t['metadata']['tags'].append({"key": "requesting_ip", "value": self.get_ip()})
        t['metadata']['tags'].append({"key": "request_timestamp", 
                                    "value": str(datetime.now().isoformat(timespec='microseconds'))})
        return t

    def api_url(self, path) -> str:
        return f"{self.config['ec_api_url']}/{path}"

    def deploy(self) -> requests.Response:
        print("inside def deploy()")
        first_response  = requests.post(self.api_url('deployments'), 
                                headers=self.headers(), 
                                json=self.payload(self.template_id))
        self.first_response = first_response
        print(self.first_response.status_code)
        print(self.first_response.json())
        status_code = first_response.status_code
        if status_code == 201 or status_code == 202:
            login_info = self.get_credentials(first_response)
            self.deployment_id = first_response.json()['id']
            print(login_info)
            print(self.deployment_id)
            print("Deployment created using API call")
            return login_info
        else:
            print("Error creating deployment using API call")
            print(first_response.status_code)
            print(first_response.json())
            return None


    def deployment_ready(self):
        print("checking status via API call...")
        self.status_response = self.get_deployment()
        if self.status_response.status_code == 200:
            if self.status_response.json()['healthy'] == True:
                print("Checking Kibana URL")
                self.url = self.get_service_url(self.status_response)
                url_resp = requests.get(self.url)
                print("Checking Kibana URL")
                print(url_resp.status_code)
                if url_resp.status_code != 200:
                    print("Kibana URL not ready yet")
                    pass
                else:
                    print("Deployment Healthy")
                    print("Kibana URL ready")
                    self.dep_state = self.dep_states[2]
                    return True
            else:
                print("Deployment not healthy yet")
                self.dep_state = self.dep_states[1]
                return False
        else:
            print("Error retrieving deployment info using API call")
            print(self.status_response.status_code)
            print(self.status_response.json())
            return False


    def check_status(self):
        if self.check_api_status():
            self.create_done_ui()
            yield


    def terminate(self) -> requests.Response:
        print("Terminating with API call...")
        terminate_response = requests.post(self.api_url(f"deployments/{self.deployment_id}/_shutdown"), 
                                headers=self.headers())
        return terminate_response
    
    async def shutdown_deploy(self):
        print("starting CloudAPI.shutdown_deploy")
        self.shutdown_ui()
        yield
        self.terminate()
        self.initial_ui()
        yield
        print("finished CloudAPI.shutdown_deploy")

    def get_deployment(self) -> requests.Response:
        return requests.get(self.api_url(f"deployments/{self.deployment_id}"), 
                                headers=self.headers())

    def healthy(self, response) -> bool:
        return response.status_code == 200 and response.json()['healthy'] == True

    def get_service_url(self, response) -> str:
        # print(response.status_code)
        if response.status_code == 200:
            return response.json()['resources']['kibana'][0]['info']['metadata']['service_url']
        else:
            return None

    def get_username(self, response) -> str:
        if response.status_code in [201, 202]:
            return response.json()['resources'][0]['credentials']['username']
        else:
            return None
    
    def get_password(self, response) -> str:
        # print(response.status_code)
        if response.status_code in [201, 202]:
            return response.json()['resources'][0]['credentials']['password']
        else:
            return None
        
    def get_credentials(self, response):
        self.username = self.get_username(response)
        self.password = self.get_password(response)
        self.url = self.get_service_url(response)