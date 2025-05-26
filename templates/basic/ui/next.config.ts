import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  assetPrefix: process.env.LLAMA_DEPLOY_NEXTJS_ASSET_PREFIX || "",
  env: {
    NEXT_PUBLIC_LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME: process.env.LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME || "default",
  },
};

export default nextConfig;
