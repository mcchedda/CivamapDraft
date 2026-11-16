# Updates environment to fix fatal errors
ISSUE: Attempting to install via the "Quickstart (Mac)" section of the `README.md` file results in compatibility errors and cannot find the `onnxruntime` package. Error:

```bash
ERROR: Cannot install -r requirements.txt (line 5) because these package versions have conflicting dependencies.

The conflict is caused by:
    fastembed 0.9.1 depends on onnxruntime>=1.24.2; python_full_version >= "3.14"
    fastembed 0.9.0 depends on onnxruntime>=1.24.2; python_version >= "3.14"
    fastembed 0.8.1 depends on onnxruntime>=1.24.2; python_version >= "3.14"
    fastembed 0.8.0 depends on onnxruntime>=1.24.2; python_version >= "3.14"
    fastembed 0.7.4 depends on onnxruntime>1.20.0; python_version >= "3.13"
    fastembed 0.7.3 depends on onnxruntime>1.20.0; python_version >= "3.13"
    fastembed 0.7.2 depends on onnxruntime>1.20.0; python_version >= "3.13"
    fastembed 0.7.1 depends on onnxruntime>1.20.0; python_version >= "3.13"
    fastembed 0.7.0 depends on onnxruntime>1.20.0; python_version >= "3.13"
    fastembed 0.6.1 depends on onnxruntime>1.20.0; python_version >= "3.13"
    fastembed 0.6.0 depends on onnxruntime>1.20.0; python_version >= "3.13"

Additionally, some packages in these conflicts have no matching distributions available for your environment:
    onnxruntime
```

SOLUTION: I opted for using `uv` for package and environment management instead of a `requirements.txt` file. This way I pin a specific version of Python for the virtual environment alongside version for each package, ensuring that the environment is reproducible. The main files were also moved inside of the `src/civamapdraft` folder to follow standard conventions.

Updated quickstart code in the `README.md` file (does not change any application functionality):
```bash
# for environment setup
uv python pin 3.14
uv sync
```

# Integration with Colby-hosted services
The `.env` file needs the following environment variables filled out with the appropriate variables:
```
QWEN_BASE_URL=<the provided litellm URL>
QWEN_MODEL=<can be qwen-3.8-27b or qwen-3.8-flash-next for the prototype>
QWEN_API_KEY=<your provided API key for local models, starts with "sk-">
QDRANT_URL=<the provided Qdrant URL>
QDRANT_API_KEY=<your provided Qdrant API key; not the same as the Qwen API key>
```

You should be able to follow the quickstart guide and have the prototype running on your laptop. From here you can refine the model prompts, source retrieval, and interface.
