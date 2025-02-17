variable "IMAGE_NAME" {
    default = "llamaindex/llama-deploy"
}

variable "IMAGE_TAG_SUFFIX" {
    default = "local"
}

variable "LLAMA_DEPLOY_VERSION" {
    default = "main"
}

variable "LLAMA_DEPLOY_VERSION_SHA" {
    default = ""
}

variable "GIT_CLONE_OPTIONS" {
    default = "--depth=1"
}

variable "BUILD_IMAGE" {
    default = "python:3.12-slim"
}

variable "DIST_IMAGE" {
    default = "python:3.12-slim"
}

variable "APISERVER_PORT" {
    default = 4501
}

variable "PROMETHEUS_PORT" {
    default = 9000
}

variable "PROMETHEUS_ENABLED" {
    default = true
}

variable "ENTRYPOINT_SCRIPT" {
    default = "run_apiserver.py"
}

variable "RC_PATH" {
    default = "/data"
}

target "default" {
    dockerfile = "Dockerfile.base"
    tags = ["${IMAGE_NAME}:${IMAGE_TAG_SUFFIX}"]
    target = "base"
    args = {
        build_image = "${BUILD_IMAGE}"
        dist_image = "${DIST_IMAGE}"
        llama_deploy_version = "${LLAMA_DEPLOY_VERSION}"
        llama_deploy_version_sha = "${LLAMA_DEPLOY_VERSION_SHA}"
        llama_deploy_extras = "[awssqs, rabbitmq, kafka, redis]"
        git_clone_options = "${GIT_CLONE_OPTIONS}"
        apiserver_port = "${APISERVER_PORT}"
        prometheus_port = "${PROMETHEUS_PORT}"
        prometheus_enabled = "${PROMETHEUS_ENABLED}"
        entrypoint_script = "${ENTRYPOINT_SCRIPT}"
        rc_path = "${RC_PATH}"
    }
    platforms = ["linux/amd64", "linux/arm64"]
}

target "autodeploy" {
    inherits = ["default"]
    tags = ["${IMAGE_NAME}:${IMAGE_TAG_SUFFIX}-autodeploy"]
    target = "autodeploy"
    args = {
        entrypoint_script = "run_autodeploy.py",
        apiserver_port = 8080,
    }
}

group "all" {
  targets = ["default", "autodeploy"]
}
