class NvidiaGpuExtension(object):
    def __init__(self, gpu_manager):
        self.gpu_manager = gpu_manager
        self.hostname = None
        self.gpu_ids = None
        self.driver_version = None

    def options_form(self, context):
        return """
            <select name="num_gpus">
                <option value="0">0</option>
                <option value="1">1</option>
                <option value="2">2</option>
            </select>
        """

    def options_from_form(self, options, formdata, context):
        options['num_gpus'] = ''.join(formdata['num_gpus'])
        hostname, gpu_ids = self.gpu_manager.get_host_id(context.user.name, int(options['num_gpus']))
        driver_version = self.gpu_manager.get_driver_version(hostname)
        self.hostname = hostname
        self.gpu_ids = gpu_ids
        self.driver_version = driver_version
        return options

    def modify_request(self, docker_container, app_container, app_request, context):
        if not self.hostname or self.gpu_ids or self.driver_version:
            return

        constraint = [[
            ["hostname", "LIKE", self.hostname]
        ]]
        parameters = [
            {"key": "device", "value": "/dev/nvidiactl"},
            {"key": "device", "value": "/dev/nvidia-uvm"},
            {"key": "volume-driver", "value": "nvidia-docker"},
            {"key": "volume", "value": "nvidia_driver_{}:/usr/local/nvidia:ro".format(self.driver_version)} 
        ]
        for gpu_id in self.gpu_ids:
            parameters.append(
                {"key": "device", "value": "/dev/nvidia%d" % gpu_id}
            )

        app_request.constraints.extend(constraints)
        docker_container.parameters.extend(parameters)
