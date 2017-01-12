import time
import os
import json
import requests
from traitlets import Int, List, Unicode
from tornado import gen
from tornado.web import HTTPError

from jupyterhub.spawner import Spawner
from .QueryUser import query_user
from .sparkmarathon import Marathon

class MarathonSparkSpawner(Spawner):
    '''

    resource_file_name = Unicode('resources',
                         help="File describing GPU resources available",
                         config=True)
    status_file_name = Unicode('status.json',
                         help="File Describing the current state of allocations",
                         config=True)
    '''

    base_port = Int(
        10000,
        help='Base int for port calculation in get_notebook_port()',
        config=True
    )
    base_mod = Int(
        1000,
        help='Mod int for port calculation in get_notebook_port()',
        config=True
    )

    home_basepath = Unicode('/home',
                         help="Basepath for user home directories",
                         config=True)
    env_url = Unicode('',
                         help="URL containing JSON environment variables to push to notebook server",
                         config=True)
    network_mode = Unicode('HOST',
                         help="Whether to use BRIDGE or HOST netowrking",
                         config=True)
    marathon_group = Unicode('spark-notebooks',
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

    def get_notebook_port(self):
        port = (int(self._user_id_default()) % self.base_mod) + int(self.base_port)
        return port

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All traitlets configurables are configured by now
        self.marathon = Marathon(self.marathon_host)
        '''
        self.gpu_resources = GPUResourceAllocator(self.resource_file_name,
                                                    self.status_file_name)
        '''

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
            HOME='/home/%s'%self.user.name,

            # Container info
            CONTAINER_NAME=self.docker_image_name,
            NOTEBOOK_PORT=str(self.get_notebook_port()),

            # Jupyter Hub config
            JPY_USER=self.user.name,
            JPY_COOKIE_NAME=self.user.server.cookie_name,
            JPY_BASE_URL=self.user.server.base_url,
            JPY_HUB_PREFIX=self.hub.server.base_url,
            JPY_HUB_API_URL = 'http://%s:8081/hub/api'%self.hub_ip_connect,
        ))

        if len(self.env_url) > 0:
            # get content
            try:
                parsed_data = requests.get(self.env_url, verify=False).json()
            except:
                parsed_data = json.loads(open(self.env_url).read())

            for env_variable in parsed_data:
                env[env_variable] = parsed_data[env_variable]

            pyspark_submit_args = []
            for var in os.environ:
                if var.lower().startswith("l41"):
                    pyspark_submit_args.append("--conf spark.executorEnv.%s=%s" % (var, os.environ[var]))
            os.environ["PYSPARK_SUBMIT_ARGS"] = " ".join(pyspark_submit_args)
            env["PYSPARK_SUBMIT_ARGS"] = " ".join(pyspark_submit_args)
        return env

    def get_container_name(self):
        return '%s/%s-notebook'%(self.marathon_group, self.user.name)

    @gen.coroutine
    def start(self):
        print('HUB URI:', self.hub.api_url)
        container_name = self.get_container_name()
        parameters = [{'key':'workdir', 'value':os.path.join(self.home_basepath, self.user.name)}]
        cmd = "/bin/bash /srv/ganymede_nbserver/ganymede_nbserver.sh"
        self.ports = [self.get_notebook_port()]
        self.marathon.start_container(container_name,
                          self.docker_image_name,
                          cmd,
                          constraints=self.marathon_constraints,
                          env=self.get_env(),
                          parameters = parameters,
                          mem_limit=self.mem_limit,
                          volumes=self.volumes,
                          ports=self.ports,
                          network_mode=self.network_mode)

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
        #self.gpu_resources.release_resource(self.user.name)

    @gen.coroutine
    def get_ip_and_port(self):
        container_name = self.get_container_name()
        print('IP/PORT: {}'.format(self.marathon.get_ip_and_port(container_name)))
        ip, port =  self.marathon.get_ip_and_port(container_name)
        port = self.get_notebook_port()
        return ip, port

    @gen.coroutine
    def poll(self):
        name = self.get_container_name()
        container_info = self.marathon.get_container_status(name)

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
