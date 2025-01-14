# Setting up Ollama

Plenty of good instructions over at https://ollama.com that we won't repeat here. These
are specific to setting for meeting buddy.

## Create a Modelfile and add to Ollama
The default context window for ollama can be a bit small, so we create a custom 
Model to expand that.

```bash
echo "FROM mistral:v0.3\nPARAMETER num_ctx 32768" > Modelfile
```

```shell
ollama create -f Modelfile mistral:v0.3-32k
```

So your "new" model with a wider context in this example is called: `mistral:v0.3-32k`

If you run `ollama list` you'll see that it is now available.
```bash
ollama list
>NAME                     	ID          	SIZE  	MODIFIED          
>mistral:v0.3-32k:latest	865b91b833ce	4.7 GB	5 minutes ago   
```

If you are using a non-standard port or anything for Ollama, you may also need to set
this environment variable:

`export OLLAMA_API_BASE=http://localhost:11434`

Note that the above is the default.

## Contributing
If you are coding/contributing and want to try using a local model, we like Aider.

```shell
aider --model ollama/mistral:v0.3-32k --no-auto-commits --llm-history-file aider-llm-history.log
```

Many many models to choose from on ollama. Pick one that suits your coding goals and will
fit in your local GPU.

