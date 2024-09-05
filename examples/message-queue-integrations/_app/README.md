# Multi Workflows App

```sh
├── README.md
├── multi_workflows_app
│   ├── __init__.py
│   ├── deployment
│   └── workflows
├── poetry.lock
└── pyproject.toml
```

The app structure demonstrates how one can organize the source code that separates
deployment logic from workflows, which aligns well with how one should think to
use `llama-index` and `llama-deploy`.

All of the workflows are contained in the `multi_workflows_app/workflows` subdirectory. There you will find that we import only classes from `llama-index`
to build out our workflows.

On the other hand, all of the logic necessary to deploy the workflows is contained
in the `multi_workflows_app/deployment` subdirectory. Here, you will notice that
most of the imports are coming from `llama-deploy`.
