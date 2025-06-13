RESPONSE=$(curl -sX 'POST' \
  'http://localhost:4501/deployments/QuickStart/tasks/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "{}"
}')

echo $RESPONSE

TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')
SERVICE_ID=$(echo $RESPONSE | jq -r '.service_id')
echo $TASK_ID


curl 'http://localhost:4501/deployments/QuickStart/tasks/'$TASK_ID'/events?session_id='$SESSION_ID


RESPONSE=$(curl -sX 'POST' \
  'http://localhost:4501/deployments/QuickStart/tasks/'$TASK_ID'/events?session_id='$SESSION_ID \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "service_id": "'$SERVICE_ID'",
  "event_obj_str": "{\"__is_pydantic\": true, \"value\": {\"response\": \"hello\"}, \"qualified_name\": \"llama_index.core.workflow.events.HumanResponseEvent\"}"
}')

curl 'http://localhost:4501/deployments/QuickStart/tasks/'$TASK_ID'/results?session_id='$SESSION_ID
