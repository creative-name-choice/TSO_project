# Overview of UArmForROS
This repository is currently worked towards bootstrapping UArmForROS. This install is currently being emulated on a x86_64 computer in Docker. The Docker container simulates an ARM64v8 architecture running Ubuntu 16.04 LTS. I still have to test it in simulation and with the real uARM. It should port on a Jetson Nano seemlessly. Then, I will be defining the OpenAI Gym environment. This project is in an early development stage.

## Prerequisites
- Ubuntu 16.04 LTS, 18.04 LTS or 20.04 LTS

## Install Nvidia GPU dependencies.

### 1. Install Nvidia GPU drivers (here v384.130 but yours can change) and reboot.
    $ sudo ubuntu-drivers autoinstall
    $ sudo shutdown -r now

### 2. Install Cuda toolkit for Nvidia GPU.
    $ sudo apt-get install -y nvidia-cuda-toolkit

## Purge previous Docker installations.

### 1. Uninstall previous Docker versions.
    $ sudo apt-get remove -y docker docker-engine docker.io containerd runc

### 2. Uninstall Docker Engine, CLI and Containerd packages.
    $ sudo apt-get -y purge docker-ce docker-ce-cli containerd.io

### 3. Purge previous Docker configurations.
    $ sudo rm -rf /var/lib/docker

## Make sure we see latest updates before installing.
    $ sudo apt-get update

## Install Docker Engine the easy way (not recommended). Skip this.

### 1. We could install Docker Engine like this and skip the rest of the Docker Engine install.
    $ curl -fsSL https://get.docker.com | sudo sh -

## Install Docker Engine the longer way.

### 1. Prepare repository addition through HTTPS.
    $ sudo apt-get install -y apt-transport-https \
    $                         ca-certificates \
    $                         curl \
    $                         gnupg-agent \
    $                         software-properties-common

### 2. Add repository GPG key.
    $ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

### 3. Verify GPG key.
    $ sudo apt-key fingerprint 0EBFCD88

#### Chose the right architecture to install and only this one.

### 4a. Add your architecture's repository to apt (here an x86_64 is amd64).
    $ sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

### 4b. Add your architecture's repository to apt (here an ARM32 is used).
    $ sudo add-apt-repository "deb [arch=armhf] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

### 4c. Add your architecture's repository to apt (here an ARM64 is used).
    $ sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

### 5. Update package descriptors.
    $ sudo apt-get update

### 6. Install Docker Engine.
    $ sudo apt-get install -y docker-ce docker-ce-cli containerd.io

## Docker Engine post-install.

### 1. Make Docker available to current non-root user without sudo and force group permissions reload.
    $ sudo usermod -aG docker $USER
    $ newgrp docker

### 2. Make Docker load at boot-time.
    $ sudo systemctl --now enable docker

### 3. Test new Docker installation.
    $ docker run hello-world

## Install Nvidia Docker.

### 1. Get Ubuntu distribution name.
    $ export DISTRIBUTION=$(source /etc/os-release; echo $ID$VERSION_ID)

### 2. Install Docker repository for Nvidia GPU.
    $ curl -fsSL https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    $ curl -fsSL https://nvidia.github.io/nvidia-docker/$DISTRIBUTION/nvidia-docker.list \
    $     | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

### 3. Windows users only (skip this if not using WSL2).
    $ curl -fsSL https://nvidia.github.io/nvidia-container-runtime/experimental/$DISTRIBUTION/nvidia-container-runtime.list \
    $     | sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list

### 4. Install Nvidia Docker.
    $ sudo apt-get update
    $ sudo apt-get install -y nvidia-docker2
    $ sudo systemctl restart docker

### 5. Test install.
    $ docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

## LICENCE
[MIT License](https://github.com/abstractguy/gym_gazebo_kinetic/blob/kinetic/LICENSE)

## FAQ

**Q1**: I encounter `SomeError: blabla` and it still doesn't work, like below:

```bash
docker: Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Post http://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/create: dial unix /var/run/docker.sock: connect: permission denied.
```
***

A1: Make Docker available to current non-root user without sudo.
    $ sudo usermod -aG docker $USER
    $ newgrp docker
