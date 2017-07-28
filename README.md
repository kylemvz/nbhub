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

You will need to ensure that jupyterhub_config.py and the files inside of config/ match your desired configuration.


