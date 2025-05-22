import { createDataStreamResponse } from "ai";
import { NextRequest } from 'next/server';
import type { MessageAnnotation } from "@llamaindex/chat-ui";

export const runtime = 'edge';

export async function POST(req: NextRequest) {
  try {
    const { messages } = await req.json();
    
    // Use the new createDataStreamResponse function to handle streaming
    return createDataStreamResponse({
      status: 200,
      statusText: 'OK',
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
      },
      async execute(dataStream) {
        try {
            const deploymentName = process.env.NEXT_PUBLIC_LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME || "default";
            const response = await fetch(
                `http://localhost:4501/deployments/${deploymentName}/tasks/create`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        service_id: null, // Using default service
                        input: JSON.stringify({ messages: messages }),
                    }),
                },
            );
        
            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}`);
            }
        
            const { task_id } = await response.json();
            
            // get event stream from task, look for events with 'delta'
            const eventStream = await fetch(
                `http://localhost:4501/deployments/${deploymentName}/tasks/${task_id}/events`,
                {
                    method: "GET",
                    headers: {
                        Accept: "text/event-stream",
                    },
                },
            );
            
            if (!eventStream.ok) {
                throw new Error(`Events stream request failed with status ${eventStream.status}`);
            }
            
            if (!eventStream.body) {
                throw new Error("Event stream body is null");
            }
            
            const reader = eventStream.body.getReader();
            const decoder = new TextDecoder();
            
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    // Split by lines in case multiple events arrive in one chunk
                    const lines = chunk.split('\n').filter(line => line.trim());
                    
                    for (const line of lines) {
                        try {
                            const event = JSON.parse(line);
                            if (event?.delta) {
                                dataStream.write(`0:${JSON.stringify(event.delta)}\n`);
                            }
                        } catch (e) {
                            console.error('Error parsing event JSON:', e, 'Line:', line);
                        }
                    }
                }
            } finally {
                dataStream.write('d:{"finishReason":"stop"}\n');
                reader.releaseLock();
            }
        } catch (error: unknown) {
            console.error('Error streaming response:', error);
            if (error instanceof Error) {
            dataStream.writeData({ error: error.message });
            } else {
            dataStream.writeData({ error: String(error) });
            }
        }
      },
      onError: (error: unknown) => {
        if (error instanceof Error) {
          return `Error processing chat request: ${error.message}`;
        }
        return `Error processing chat request: ${String(error)}`;
      },
    });
  } catch (error) {
    console.error('Error in chat endpoint:', error);
    return new Response('Error processing chat request', { status: 500 });
  }
} 