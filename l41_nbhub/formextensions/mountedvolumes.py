import requests
import json
import os

class MountedVolumesExtension(object):
    def __init__(self, volume_mapping):
        """
        A list in Marathon REST API format for mounting volumes into the Docker container.
        [
            {
                "containerPath": "/foo",
                "hostPath": "/bar",
                "mode": "RW"
            }
        ]
        """
        self.volume_mapping = volume_mapping
    
    def options_form(self, context):
        html = """
            <label for=\"mounted_volumes\"/>Mounted volumes</label>
            <input type=\"text\" name=\"mounted_volumes\"/>
        """
        return html

    def options_from_form(self, options, formdata, context):
        options['mounted_volumes'] = ''.join(formdata['mounted_volumes'])
        self.volume_mapping = ast.literal_eval(options['mounted_volumes'])
        return options

    def modify_request(self, docker_container, app_container, app_request, context):
        if not self.volume_mapping:
            return
        
        app_container.volumes.extend(self.volume_mapping)
