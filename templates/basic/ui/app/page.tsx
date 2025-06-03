"use client";

import Image from "next/image";
import { useState } from "react";
import { ChevronRightIcon, CheckCircleIcon, ExclamationCircleIcon } from "@heroicons/react/24/outline";

export default function Home() {
  const [inputText, setInputText] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const deploymentName =
    process.env.NEXT_PUBLIC_LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME || "default";

  const formatResponse = (data: string) => {
    try {
      const parsed = JSON.parse(data);
      if (parsed.result && typeof parsed.result === 'string') {
        return parsed.result;
      }
      return JSON.stringify(parsed, null, 2);
    } catch {
      return data;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult("");

    try {
      const response = await fetch(
        `/deployments/${deploymentName}/tasks/run`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            service_id: null,
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-900 dark:to-slate-900">
      {/* Header */}
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-12">
          <Image
            className="mx-auto mb-6"
            src={`${process.env.NEXT_PUBLIC_BASE_PATH}/logo-dark-light.svg`}
            alt="LlamaIndex logo"
            width={120}
            height={120}
            priority
          />
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
            LlamaDeploy Workflow
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-300">
            Test your deployment with interactive workflows
          </p>
        </div>

        {/* Main Content */}
        <div className="max-w-4xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-8">
            {/* Input Section */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                  <span className="text-blue-600 dark:text-blue-300 font-semibold text-sm">1</span>
                </div>
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
                  Configure & Send
                </h2>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Deployment
                  </label>
                  <div className="relative">
                    <div className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 font-mono text-sm">
                      {deploymentName}
                    </div>
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    </div>
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="inputText"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                  >
                    Your Message
                  </label>
                  <textarea
                    id="inputText"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white resize-none transition-all"
                    rows={5}
                    placeholder="Enter your message here..."
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !inputText.trim()}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-500 text-white font-semibold py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      Processing...
                    </>
                  ) : (
                    <>
                      Run Workflow
                      <ChevronRightIcon className="w-5 h-5" />
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* Output Section */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-8 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                  <span className="text-green-600 dark:text-green-300 font-semibold text-sm">2</span>
                </div>
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
                  Response
                </h2>
              </div>

              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="text-center">
                    <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-600 dark:text-gray-400">
                      Processing your request...
                    </p>
                  </div>
                </div>
              )}

              {error && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <ExclamationCircleIcon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-sm font-medium text-red-800 dark:text-red-400 mb-1">
                        Error occurred
                      </h3>
                      <p className="text-sm text-red-700 dark:text-red-300">
                        {error}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {result && !loading && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                    <CheckCircleIcon className="w-5 h-5" />
                    <span className="text-sm font-medium">Success</span>
                  </div>

                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="mb-2">
                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                        Response
                      </span>
                    </div>
                    <div className="text-gray-900 dark:text-gray-100">
                      {(() => {
                        const formattedResponse = formatResponse(result);
                        if (formattedResponse.startsWith('{') || formattedResponse.startsWith('[')) {
                          return (
                            <pre className="text-sm overflow-auto whitespace-pre-wrap font-mono">
                              {formattedResponse}
                            </pre>
                          );
                        } else {
                          return (
                            <div className="text-sm leading-relaxed">
                              {formattedResponse}
                            </div>
                          );
                        }
                      })()}
                    </div>
                  </div>
                </div>
              )}

              {!result && !loading && !error && (
                <div className="flex items-center justify-center py-12">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
                      <ChevronRightIcon className="w-8 h-8 text-gray-400" />
                    </div>
                    <p className="text-gray-500 dark:text-gray-400">
                      Send a message to see the response
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 text-center">
          <a
            className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
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
            View Documentation
          </a>
        </footer>
      </div>
    </div>
  );
}
