class FirstFitStrategy:
    """
    A straightforward greedy approximation algorithm. For each request, attempt to place the container on the first host that can accomodate the number of requested GPUs.
    """
    def __init__(self):
        pass

    def request_resources(resources, state, username, num_gpus):
        for hostname, info in sorted(state.items()):
            possible = []
            for gpu_id, username in sorted(info.items()):
                if not username:
                    possible.append(gpu_id)
                if len(possible) == num_gpus:
                    return hostname, possible
        return None, None # cannot fulfill request
