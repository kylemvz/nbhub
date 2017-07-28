import time
import os
import json
import requests
from traitlets import Dict, Int, List, Unicode
from tornado import gen
from tornado.web import HTTPError
import sys
import ast

from jupyterhub.spawner import Spawner
from .QueryUser import query_user
from .marathon import Marathon
from .GPUResourceAllocator import GPUResourceAllocator


class MarathonSpawner(Spawner):
    resource_file_name = Unicode('resources',
                         help="File describing GPU resources available",
                         config=True)
    status_file_name = Unicode('status.json',
                         help="File Describing the current state of allocations",
                         config=True)
    home_basepath = Unicode('/home',
                         help="Basepath for user home directories",
                         config=True)
    work_dir = Unicode('/home',
        help="Working directory to pass to Marathon.",
        config=True)
    env_url = Unicode('',
                         help="URL containing JSON environment variables to push to notebook server",
                         config=True)
    network_mode = Unicode('BRIDGE',
                         help="Whether to use BRIDGE or HOST netowrking",
                         config=True)
    marathon_group = Unicode('notebooks',
                             help="Marathon group name (folder) prefix for container names",
                             config=True)
    mem_limit = Int(
        4096,
        help='Memory limit in MB',
        config=True)
    volumes = List(
        [],
        help='Volumes to mount as Read-write. If a single string is entered then it is mounted in same path.'
             'If a tuple is specified then first item is hostPath and the 2nd is the containerPath',
        config=True)
    ports = List(
        [8888],
        help='Ports to expose externally',
        config=True)
    marathon_constraints = List([],
                                help='Constraints to be passed through to Marathon',
                                config=True)
    hub_ip_connect = Unicode(u'',
                             help="Public IP address of the hub",
                             config=True)
    marathon_host = Unicode(u'',
                            help="Hostname of Marathon server",
                            config=True)
    docker_image_name = Unicode(u'',
                                help="Name of the docker image",
                                config=True)
    cmd = Unicode(u'',
                         help="Command for container",
                         config=True)

    num_gpus = Int(
        0,
        help='Number of GPUs to mount onto the machine')

    path_to_image_list = Unicode(u'',
        help='Path to image list (local path or URL)',
        config=True
    )
    runtime_constraints = List([],
        help='Constraints specified at runtime that will be appended to self.marathon_constraints'
    )
    runtime_vols = List([],
        help='Volumes specified at runtime that will be appended to self.volumes'
    )
    runtime_envs = Dict({},
        help='Environment variables specified at runtime (overrides vars with the same name)'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All traitlets configurables are configured by now
        self.marathon = Marathon(self.marathon_host)
        self.gpu_resources = GPUResourceAllocator(self.resource_file_name,
                                                  self.status_file_name)

    def _expand_user_vars(self, string):
        """
        Expand user related variables in a given string

        Currently expands:
          {USERNAME} -> Name of the user
          {USERID} -> UserID
        """
        return string.format(
            USERNAME=self.user.name,
            USERID=self._user_id_default()
        )

    def get_state(self):
        state = super().get_state()
        state['container_name'] = self.get_container_name()
        return state

    def load_state(self, state):
        if 'container_name' in state:
            pass
     
    def get_env(self):
        env = super().get_env()
        
        env.update(dict(
            # User Info
            USER=self.user.name,
            USER_ID=str(self._user_id_default()),
            HOME='%s/%s/'%(self.home_basepath, self.user.name),

            # Container info
            CONTAINER_NAME=self.docker_image_name,
            NOTEBOOK_PORT=str(self.ports[0]),

            # Jupyter Hub config
            JPY_USER=self.user.name,
            JPY_COOKIE_NAME=self.user.server.cookie_name,
            JPY_BASE_URL=self.user.server.base_url,
            JPY_HUB_PREFIX=self.hub.server.base_url,
            JPY_HUB_API_URL = 'http://%s/hub/api'%self.hub_ip_connect,
        ))
        
        if len(self.env_url) > 0:
            # get content
            try:
                parsed_data = requests.get(self.env_url, verify=False).json()
            except:
                parsed_data = json.loads(open(self.env_url).read())

            for env_variable in parsed_data:
                env[env_variable] = parsed_data[env_variable]

        env.update(self.runtime_envs)
        return env

    def get_container_name(self):
        return '/%s/%s-notebook'%(self.marathon_group, self.user.name)

    def _mount_nvidia(self, constraints, parameters, num_gpus):
        # do nothing if no GPUs are requested
        if num_gpus == 0:
            pass
        hostname, gpu_ids = self.gpu_resources.get_host_id(self.user.name, num_gpus)
        driver_version = self.gpu_resources.get_driver_version(hostname)
        constraints = [
            ["hostname", "LIKE", hostname]
        ]
        parameters.extend([
            {"key": "device", "value": "/dev/nvidiactl"},
            {"key": "device", "value": "/dev/nvidia-uvm"},
            {"key": "volume-driver", "value": "nvidia-docker"},
            {"key": "volume", "value": "nvidia_driver_{}:/usr/local/nvidia:ro".format(driver_version)}
        ])
        for gpu_id in gpu_ids:
            parameters.append(
                {"key": "device", "value": "/dev/nvidia%d" % gpu_id}
            )

    @gen.coroutine
    def start(self):
        print('HUB URI:', self.hub.api_url)
        container_name = self.get_container_name()
        constraints = self.marathon_constraints
        parameters = []

        if self.num_gpus > 0:
            self._mount_nvidia(constraints, parameters, self.num_gpus)
        
        parameters.append(
            {"key": "workdir", "value": "%s/%s" % (self.work_dir, self.user.name)}
        )

        volumes = self.volumes + self.runtime_vols
        constraints = constraints + self.runtime_constraints

        #print(constraints, file=sys.stderr, flush=True)
        #print(parameters, file=sys.stderr, flush=True)
        #print(volumes, file=sys.stderr, flush=True)
        r = self.marathon.start_container(container_name,
                          self.docker_image_name,
                          self.cmd, #cmd,
                          constraints=constraints,
                          env=self.get_env(),
                          parameters = parameters,
                          mem_limit=self.mem_limit,
                          volumes=volumes,
                          ports=self.ports,
                          network_mode=self.network_mode)
        #print(r.text, file=sys.stderr, flush=True)

        for i in range(self.start_timeout):
            is_up = yield self.poll()
            if is_up is None:
                time.sleep(1)
                ip, port = self.marathon.get_ip_and_port(container_name)
                self.user.server.ip=ip
                self.user.server.port = port
                print('IP/PORT', ip, port)
                return (ip, port)
            time.sleep(1)

        return None

    @gen.coroutine
    def stop(self):
        container_name = self.get_container_name()
        self.marathon.stop_container(container_name)
        self.gpu_resources.release_resource(self.user.name)

    @gen.coroutine
    def get_ip_and_port(self):
        container_name = self.get_container_name()
        print('IP/PORT: {}'.format(self.marathon.get_ip_and_port(container_name)))
        return self.marathon.get_ip_and_port(container_name)

    @gen.coroutine
    def poll(self):
        container_info = self.marathon.get_container_status(self.get_container_name())
        print(container_info, file=sys.stderr, flush=True)

        if container_info is None:
            return ""

        if 'tasks' in container_info and len(container_info['tasks']) == 1:
            return None
        else:
            print('Container Not Found')
            return ""

    def _user_id_default(self):
        """
        Query the REST user client running on a local socket.
        """
        response = query_user(self.user.name)
        if "uid" not in response:
            raise HTTPError(403)
        return response['uid']

    def get_image_list(self):
        image_list = []
        #print(self.path_to_image_list, file=sys.stderr, flush=True)
        if os.path.exists(self.path_to_image_list):
            with open(self.path_to_image_list) as f:
                image_list = f.readlines()
        else:
            r = requests.get(self.path_to_image_list)
            image_list = r.text.split("\n")
        image_list = [line.strip().split(",") for line in image_list]
        #print(image_list, file=sys.stderr, flush=True)
        return image_list

    def get_image_form(self):
        html = "<select name=\"image\">"
        for display_name, value in self.get_image_list():
            html += "<option value=\"%s\">%s</option>" % (value, display_name)
        html += "</select>"
        return html

    def _options_form_default(self):
        defaults = {
            "constraints": "[['hostname','LIKE','localhost']]",
            "image_form": self.get_image_form(),
            "vols": "['/same/host/and/container/path', ('/host/path', '/container/path')]",
            "cmd": "",
            "runtime_envs": "KEY1=VAL1\nKEY2=VAL2"
        }

        html = """
        <label for="constraints">Marathon constraints:</label>
        <input type="text" name="constraints" placeholder="{constraints}"/>

        <label for="image">Docker image:</label>
        {image_form}

        <label for="num_gpus">Num GPUs:</label>
        <select name="num_gpus">
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2">2</option>
        </select>

        <label for="vols">Mounted volumes:</label>
        <input type="text" name="vols" placeholder="{vols}"/>

        <label for="runtime_envs">Environment variables (overwrites other env vars):</label>
        <textarea name="runtime_envs" placeholder="{runtime_envs}"></textarea>
        """.format(**defaults)
        return html

    def options_from_form(self, formdata):
        options = {}
        options['constraints'] = ''.join(formdata['constraints'])
        if options['constraints']:
            self.runtime_constraints = ast.literal_eval(options['constraints'])

        options['image'] = ''.join(formdata['image'])
        valid_images = [image_name for display_name, image_name in self.get_image_list()]
        if options['image'] not in valid_images:
            raise Exception("Invalid image specified.")
        if options['image']:
            self.docker_image_name = options['image']

        options['num_gpus'] = ''.join(formdata['num_gpus'])
        if options['num_gpus']:
            self.num_gpus = int(''.join(formdata['num_gpus']))

        options['volumes'] = ''.join(formdata['vols'])
        if options['volumes']:
            self.runtime_volumes = ast.literal_eval(options['volumes'])

        options['runtime_envs'] = ''.join(formdata['runtime_envs'])
        runtime_envs = {}
        for line in options['runtime_envs'].split("\n"):
            try:
                eq_idx = line.index("=")
                runtime_envs[line[:eq_idx]] = line[eq_idx+1:]
            except ValueError:
                continue
        if runtime_envs:
            self.runtime_envs = runtime_envs

        return options

