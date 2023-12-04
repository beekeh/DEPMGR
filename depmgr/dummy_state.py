import reflex as rx
from time import sleep
import oyaml as yaml
import json
import os
import requests
import subprocess
from datetime import datetime
import uuid
from time import sleep
import asyncio
from random import choice as randchoice

class Base(rx.State):
    template_id: str = "minimal"
    cbutton_text: str = "CREATE"
    tbutton_text: str = "SHUTDOWN"
    cbutton_disabled: bool = False
    tbutton_disabled: bool = True
    clipboard_text: str = "" 
    dep_states: list = ['initial', 'deploying', 'deployed', 'failed']
    dep_state: str = dep_states[0]
    

    def initial_ui(self):
        self.dep_state = self.dep_states[0]
        self.cbutton_disabled = False
        self.tbutton_disabled = True
        self.clipboard_text = ""

    async def waiting_ui(self):
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


class Dummy(Base):
    login_info: dict = { 
    "username": "elastic", 
    "password": "changeme", 
    "url": "http://localhost:5601" 
    }
    deployment_requested: bool = False

    running: bool = False
    _n_tasks: int = 0

    @rx.var
    def url(self) -> str:
        return self.login_info["url"]

    @rx.var
    def username(self) -> str:
        return self.login_info["username"]
    
    @rx.var
    def password(self) -> str:
        return self.login_info["password"]
    
    @rx.background
    async def check_status_task(self):
        print("inside Dummy check_status_task")
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
                    p = os.path.dirname(__file__) + '/test/deployed'
                    print(p)
                    if os.path.exists(p):
                        print("file exists")
                        print("deployed")
                        self.dep_state = self.dep_states[2]
                        self.deployed_ui()
                        self.running = False
                    if not self.running:
                        self._n_tasks -= 1
                        return
            await asyncio.sleep(3)

    def start_deployment(self):
        print("inside Dummy start_deployment")
        self.dep_state = self.dep_states[1]
        self.running = True
        self.waiting_ui()
        yield
        self.deploy()
        if self.running:
            print("starting task")
            return Dummy.check_status_task

    async def shutdown_deploy(self):
        print("starting shutdown_deploy")
        self.shutdown_ui()
        yield
        self.terminate()
        self.initial_ui()
        yield
        print("finished shutdown_deploy")

    async def deploy(self):
        print("Dummy Deploy Requesting...")
        sleep(1)
        print("Dummy Deploy Requested")

    def terminate(self):
        print("Dummy Terminating...")
        self.dep_state = self.dep_states[0]