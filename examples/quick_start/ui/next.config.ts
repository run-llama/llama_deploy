import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: process.env.LLAMA_DEPLOY_NEXTJS_BASE_PATH,
  env: {
    NEXT_PUBLIC_LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME: process.env.LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME || "default",
  },
};

export default nextConfig;
