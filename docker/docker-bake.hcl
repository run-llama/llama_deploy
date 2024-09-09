variable "IMAGE_NAME" {
    default = "llamaindex/llama-deploy"
}

variable "IMAGE_TAG_SUFFIX" {
    default = "local"
}

variable "LLAMA_DEPLOY_VERSION" {
    default = "main"
}

variable "BUILD_IMAGE" {
    default = "python:3.12-slim"
}

variable "DIST_IMAGE" {
    default = "python:3.12-slim"
}

group "default" {
    targets = ["control_plane", "message_queue"]
}

target "base" {
    dockerfile = "Dockerfile.base"
    tags = ["${IMAGE_NAME}:base-${IMAGE_TAG_SUFFIX}"]
    args = {
        build_image = "${BUILD_IMAGE}"
        dist_image = "${DIST_IMAGE}"
        llama_deploy_version = "${LLAMA_DEPLOY_VERSION}"
        entrypoint_script = "base.py"
    }
    platforms = ["linux/amd64", "linux/arm64"]
}

target "control_plane" {
    inherits = ["base"]
    tags = ["${IMAGE_NAME}:control-plane-${IMAGE_TAG_SUFFIX}"]
    args = {
        entrypoint_script = "control_plane.py"
        exposed_port = 8000
    }
}

target "message_queue" {
    inherits = ["base"]
    tags = ["${IMAGE_NAME}:message-queue-${IMAGE_TAG_SUFFIX}"]
    args = {
        entrypoint_script = "message_queue.py"
        exposed_port = 8000
    }
}
