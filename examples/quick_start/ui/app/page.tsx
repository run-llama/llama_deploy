"use client";

import Image from "next/image";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const [inputText, setInputText] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  // Get deployment name from environment variable or use "default" as fallback
  const deploymentName =
    process.env.NEXT_PUBLIC_LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME || "default";
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `/deployments/${deploymentName}/tasks/run`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            service_id: null, // Using default service
            input: JSON.stringify({ message: inputText }),
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }

      const data = await response.json();
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unknown error occurred",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen p-6 sm:p-8 font-[family-name:var(--font-geist-sans)]">
      <main className="flex-1 flex flex-col gap-8 items-center justify-center max-w-2xl mx-auto w-full">
        <button
          onClick={() => router.push("/confetti")}
          className="hover:scale-105 transition-transform duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-lg cursor-pointer"
        >
          <Image
            className="w-full max-w-lg p-6"
            src={`${process.env.NEXT_PUBLIC_BASE_PATH}/logo-dark-light.svg`}
            alt="LlamaIndex logo - Click for confetti!"
            width={180}
            height={180}
            priority
          />
        </button>

        {/* API Form */}
        <div className="w-full max-w-lg p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md">
          <h2 className="text-xl font-bold mb-4">Workflow Test</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="deployment"
                className="block text-sm font-medium mb-1"
              >
                Deployment Name
              </label>
              <div className="w-full p-2 border rounded bg-gray-100 dark:bg-gray-700">
                {deploymentName}
              </div>
            </div>
            <div>
              <label
                htmlFor="inputText"
                className="block text-sm font-medium mb-1"
              >
                Message
              </label>
              <textarea
                id="inputText"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="w-full p-2 border rounded text-black"
                rows={4}
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 px-4 bg-foreground text-background rounded-md hover:bg-[#383838] dark:hover:bg-[#ccc] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              {loading ? "Processing..." : "Run workflow"}
            </button>
          </form>

          {error && (
            <div className="mt-4 p-3 bg-red-100 text-red-700 rounded-md">
              {error}
            </div>
          )}

          {result && (
            <div className="mt-4">
              <h3 className="text-lg font-medium mb-2">Result:</h3>
              <pre className="p-3 bg-gray-100 dark:bg-gray-700 rounded-md overflow-auto text-sm max-h-64">
                {result}
              </pre>
            </div>
          )}
        </div>
      </main>

      <footer className="flex gap-6 flex-wrap items-center justify-center py-4 mt-8">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://docs.llamaindex.ai/en/stable/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src={`${process.env.NEXT_PUBLIC_BASE_PATH}/file.svg`}
            alt="File icon"
            width={16}
            height={16}
          />
          Learn
        </a>
      </footer>
    </div>
  );
}
