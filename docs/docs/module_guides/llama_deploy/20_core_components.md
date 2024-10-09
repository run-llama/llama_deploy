# Core Components

Llama Deploy consists of several core components acting as services in order to provide the environment where
multi-agent applications can run and communicate with each other. This sections details each and every component.

## Deployment

In Llama Deploy each workflow is wrapped in a _Service_ object, endlessly processing incoming requests in form of
_Task_ objects. Each service pulls and publishes messages to and from a _Message Queue_. An internal component called
_Control Plane_ handles ongoing tasks, manages the internal state, keeps track of which services are available, and
decides which service should handle the next step of a task using another internal component called _Orchestrator_.

A well defined set of these components is called _Deployment_.

## The API Server

The API Server is a core component of Llama Deploy that provides a self-hosted service for managing multiple
[deployments](./Core%20Components/deployment.md).
