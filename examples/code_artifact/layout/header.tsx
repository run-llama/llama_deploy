"use client";

import { Sparkles, Star } from "lucide-react";

export default function Header() {
  return (
    <div className="flex items-center justify-between p-2 px-4">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4" />
        <h1 className="font-semibold">Artifact Workflow</h1>
      </div>
      <div className="flex items-center justify-end gap-4">
        <div className="flex items-center gap-2">
          <a
            href="https://www.llamaindex.ai/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Built by LlamaIndex
          </a>
          <img
            className="h-[24px] w-[24px] rounded-sm"
            src="/llama.png"
            alt="Llama Logo"
          />
        </div>
        <a
          href="https://github.com/run-llama/LlamaIndexTS"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:bg-accent flex items-center gap-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        >
          <Star className="size-4" />
          Star on GitHub
        </a>
      </div>
    </div>
  );
}
