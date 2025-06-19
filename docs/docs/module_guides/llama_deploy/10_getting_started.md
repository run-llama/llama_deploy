# Getting Started with LlamaDeploy

This quick-start tutorial shows how to spin up a **fully-working LlamaDeploy service** in just a few commands using the `llamactl init` wizard.

---

## 1. Installation

```bash
pip install -U llama-deploy
```

> The command installs both the Python libraries **and** the `llamactl` CLI you will use throughout the guide.

---

## 2. Bootstrap a project with `llamactl init`

Run the interactive wizard:

```bash
$ llamactl init
Project name [llama-deploy-app]: hello-deploy
Destination directory [.]:
Workflow template:
  basic - Basic workflow with OpenAI integration (recommended)
  none  - Do not create any sample workflow code
Select workflow template [basic]:
Would you like to bundle a sample next.js UI with your deployment? [Y/n]: y
Cloning template files from repository...
Template files copied successfully to hello-deploy

Project hello-deploy created successfully!
Next steps:
  1. cd hello-deploy
  2. Edit deployment.yml to add your OpenAI API key
  3. Start the API server: python -m llama_deploy.apiserver
  4. In another terminal deploy your workflow: llamactl deploy deployment.yml
  5. Test: llamactl run --deployment hello-deploy --arg message 'Hello!'
```

Prefer a **non-interactive** run? Provide options up-front:

```bash
llamactl init \
  --name hello-deploy \
  --destination . \
  --port 8000 \
  --message-queue-type simple \
  --template basic
```

---

## 3. Explore the generated project

```
hello-deploy/
├── deployment.yml         # Declarative config for your deployment
├── src/
│   └── workflow.py        # Sample CompletionWorkflow (OpenAI-powered)
└── ui/                    # (optional) Next.js UI scaffold
```

### Key files

* **deployment.yml** – everything is **commented** for easy editing. Update:
  * `env.OPENAI_API_KEY` – set your key or reference a `.env` file.
  * `services` – add/remove workflows, tweak python deps, etc.
* **src/workflow.py** – a minimal `Workflow` using a single `@step`.
* **ui/** – a ready-made React front-end that calls your deployment.

---

## 4. Run the project locally

1. Start the API server (default port 4501):

   ```bash
   cd hello-deploy
   python -m llama_deploy.apiserver
   ```

   or with Docker:

   ```bash
   docker run -p 4501:4501 -v "$PWD":/opt/app -w /opt/app llamaindex/llama-deploy:main
   ```

2. From another terminal **deploy** the workflow:

   ```bash
   llamactl deploy deployment.yml
   ```

3. **Call** the workflow:

   ```bash
   llamactl run --deployment hello-deploy --arg message "Hello from Llama!"
   # ➜ Message received: Hello from Llama!
   ```

4. (Optional) open the UI at <http://localhost:4501/ui/hello-deploy/>.

---

## 5. Next steps & customization ideas

| What you want to do | Where to look |
|--------------------|---------------|
| Change the LLM, add tools or multiple steps | `src/workflow.py` – build with any [LlamaIndex Workflow](https://docs.llamaindex.ai/en/stable/understanding/workflows/). |
| Add more workflows/services | Duplicate the `example_workflow` block in `deployment.yml` and point to your new workflow. |
| Set secrets & environment variables | Use `env`/`env_files` inside each service. |
| Deploy to production | Containerize your deployment (for example, see the [Google Cloud Run Example](https://github.com/run-llama/llama_deploy/tree/main/examples/google_cloud_run)), then run and scale the deployment anywhere you can run Docker/K8s. |
