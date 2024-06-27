register:
	set -a && source multi-agent-app/.env.docker
	export MESSAGE_QUEUE_HOST="0.0.0.0"
	python multi-agent-app/multi_agent_app/comms/control_plane.py
	python multi-agent-app/multi_agent_app/agents/secret_agent.py
	python multi-agent-app/multi_agent_app/agents/funny_agent.py
	python multi-agent-app/multi_agent_app/additional_services/human_consumer.py
