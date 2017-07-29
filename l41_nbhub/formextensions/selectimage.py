import requests
import json
import os

class SelectImageExtension(object):
    def __init__(self, path_to_image_list=None):
        self.path_to_image_list = path_to_image_list
        self.image = None
    
    def get_image_list(self):
        image_list = []
        if os.path.exists(self.path_to_image_list):
            with open(self.path_to_image_list) as f:
                image_list = f.readlines()
        else:
            r = requests.get(self.path_to_image_list)
            image_list = r.text.split("\n")
        return image_list

    def options_form(self, context):
        html = "<select name=\"image\">"
        for display_name, value in self.get_image_list():
            html += "<option value=\"%s\">%s</option>" % (value, display_name)
        html += "</select>"
        return html
        
    def options_from_form(self, options, formdata, context):
        options['image'] = ''.join(formdata['image'])
        assert options['image'] in self.get_image_list()
        self.image = options['image']
        return options

    def modify_request(self, docker_container, app_container, app_request, context):
        if not self.image:
            return

        docker_container.image = self.image
