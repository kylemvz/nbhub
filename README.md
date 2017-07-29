# L41 NBHub

This project is a Lab41-customized version of JupyterHub. It uses a custom spawner that interfaces with Marathon. The entire hub is run from inside a Docker container and acts as a proxy for the notebook servers which are run in their own Docker containers (potentially on different machines).

## Setup (WIP)

Ensure that you have a working Marathon cluster.

Ensure that Docker is installed on the machine where you plan to run L41 NBHub.

Follow the instructions inside of restuser/ to launch the local service on the hub machine. It is a local REST service exposed on a UNIX socket that the hub queries to determine the UID/GID for a particular user. The UID/GID is passed to the user server at creation time, allowing the user server to dynamically create the user with proper UID/GID inside the container. restuser/ is a fork of [minrk/restuser](https://github.com/minrk/restuser), with the slight change to make the server query-only (user will not be crated if he or she does not already exist).

In addition to running restuser/, you must also set the environment variable RESTUSER_SOCK_PATH on the hub machine.

After cloning this repository and cd'ing inside of the cloned directory, the next step is to build the container:

`
docker build -t lab41/nbhub .
`

Run the container using your Marathon API.

jupyterhub_config.py that comes with this repository is a sample. You will need to override the values with your default configuration.

Some variables of note:

env_file (JSON file containing environment vars)
username_map_file (path to local file or URI of a dict mapping Github usernames to Linux usernames)
resource_file_name (a text file describing GPU resources available in the Marathon cluster)
status_file_name (JSON file describing current GPU resource allocations)
env_url (URL to JSON file containing additional environment variables)
path_to_image_list (path to local file or URI of a list of approved images)

