# Docker build system

This folder contains the files needed to build the base `llama_deploy` images that
can be used to simplify deployments by reducing boiler plate code.

## Image Development

Images are built with [BuildKit](https://docs.docker.com/build/buildkit/) and we use
`bake` to orchestrate the process. You can build a specific image by running:

```sh
docker buildx bake control_plane
```

By default, all the images are built if no target is passed:

```sh
docker buildx bake
```

You can override any `variable` defined in the `docker-bake.hcl` file and build custom
images, for example if you want to use a branch from the llama_deploy repo instead of
an official release, run:

```sh
LLAMA_DEPLOY_VERSION=mybranch_or_tag docker buildx bake
```

### Multi-Platform Builds

`llama_deploy` images support multiple architectures. Depending on your operating
system and Docker environment, you might not be able to build all of them locally.

This is the error you might encounter:

```
multiple platforms feature is currently not supported for docker driver. Please switch to a different driver
(eg. “docker buildx create --use”)
```

To work around this problem, one solution is to override the `platform` option and
limit local builds to the same architecture as your computer's. For example, on an Apple M1 you can limit the builds to ARM only by invoking `bake` like this:

```sh
docker buildx bake control_plane --set "*.platform=linux/arm64"
```

## Docker Compose base files

This folders also contains yaml code that can be included in your compose files to
elimninate boilerplate. For example, you can deploy the core components by just
adding this to your compose file:

```yaml
include:
  - path: path/to/llama_deploy/docker/docker-compose-simple.yml

services: ...
```
