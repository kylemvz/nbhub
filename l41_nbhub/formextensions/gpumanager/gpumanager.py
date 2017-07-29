from collections import defaultdict
import json
import os

class GPUResourceAllocator:
    """
    Quick and dirty class to manage GPU allocations. Uses flat files which are read at each instance

    """
    def __init__(self, resource_filename, status_filename, assignment_strategy=None, allow_oversubscription=True):
        """
        Initialize GPUResourceAllocator
        Args:
            resource_filename: Filename of a text file of the format "hostname #gpus\n hostname #gpus"
            status_filename: A json object of the format {username:(hostname,gpuid)}

        Returns:

        """
        self.resource_filename = resource_filename
        self.status_filename = status_filename
        self.allow_oversubscription = allow_oversubscription
        if not assignment_strategy:
            assignment_strategy = FirstFitStrategy()
        self.assignment_strategy = assignment_strategy

    def get_resources(self):
        """
        Gets the available resources from the specified text file
        Returns:
            resources: A list of the available resources, tuple of (hostname, number of gpus)
        """
        self.driver_versions = {}
        resources = []
        with open(self.resource_filename) as input_file:
            for line in input_file:
                line = line.split()
                # 0=hostname, 1=number of gpus, 2=driver version
                resources.append((line[0], int(line[1])))
                if len(line) > 1:
                    self.driver_versions[line[0]] = line[2]
        return resources

    def get_driver_version(self, hostname):
        if hostname in self.driver_versions:
            return self.driver_versions[hostname]
        else:
            return None

    def get_current_allocations(self):
        """
        Get the current state of gpu allocations
        Returns:
            by_user: A dictionary of the format {username:[(hostname,gpuid)]}
            by_hostname: A dictionary of the format {hostname:{gpu_id:username}}
        """
        if not os.path.exists(self.status_filename):
            with open(self.status_filename, 'w') as fOut:
                json.dump({}, fOut, indent=4)

        # user:{[(host,id)]}
        by_user = json.load(open(self.status_filename))

        by_hostname = defaultdict(dict)
        for username, info for status.items():
            for hostname, gpu_id in info:
              by_hostname[hostname][gpu_id] = username

        return by_user, by_hostname

    def save_current_allocations(self, current_allocations):
        """
        Save the current state of gpu allocations
        Args:
            current_allocations: A dictionary of the format {username:(hostname,gpuid)}
        """
        with open(self.status_filename, 'w') as fOut:
            json.dump(current_allocations, fOut, indent=4)

    """
    # TO DELETE
    @staticmethod
    def get_lowest_available_id(current_usage, max_available):
        for i in range(max_available):
            if i not in current_usage:
                return i
        raise ValueError('Should never get here')
    """

    def get_host_id(self, desired_username, num_gpus):
        """
        Returns the hostname/id to assign a given user
        Args:
            desired_username: the username to allocate resources for

        Returns:
            (Hostname, GPU_ID): Tuple of resources to be assigned
        """
        resources = self.get_resources()
        allocations_by_user, allocations_by_host = self.get_current_allocations()

        # If we've already assigned resources
        if desired_username in allocations_by_user:
            return allocations_by_user[desired_username]

        hostname, gpu_ids = self.assignment_strategy.request_resources(resources, allocations_by_host, desired_username, num_gpus)
        if not hostname or not gpu_ids:
            raise ValueError("No resources available to fulfill request.")

        # Assign host to be used
        if desired_username not in allocations_by_user:
            allocations_by_user[desired_username] = set()
        for gpu_id in gpu_ids:
            allocations_by_user[desired_username].add((hostname, gpu_id))
        self.save_current_allocations(allocations_by_user)
        return hostname, gpu_ids

    def release_resource(self, desired_username):
        """
        Return the resources for a given user to the pool
        Args:
            desired_username: username to return resources for

        Returns:

        """
        allocations_by_user, allocations_by_host = self.get_current_allocations()
        if desired_username in allocations_by_user:
            del allocations_by_user[desired_username]

        self.save_current_allocations(allocations_by_user)

