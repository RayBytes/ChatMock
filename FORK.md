# Fork: geração de imagem no ChatMock

Fork de [RayBytes/ChatMock](https://github.com/RayBytes/ChatMock) (v1.40) com um
objetivo só: **fazer o ChatMock devolver imagens**.

O backend do Codex já sabia desenhar — quem não sabia receber era o ChatMock.

## O que foi descoberto

O endpoint `https://chatgpt.com/backend-api/codex/responses`, o mesmo que o
ChatMock já usava para texto, aceita o tool `image_generation` e devolve a imagem
em base64. Medido, não deduzido:

- modelo que desenha: `gpt-image-2-codex` (não dá para trocar);
- `tool_choice: {"type": "image_generation"}` funciona e força a geração;
- o consumo aparece em `tool_usage.image_gen` da resposta — ou seja, **sai da
  cota do plano ChatGPT/Codex**, não de crédito de API;
- `n` no tool é recusado (`Unknown parameter: 'tools[0].n'`): uma imagem por
  requisição;
- `size` e `quality` são aceitos mas ignorados — o echo volta sempre `"auto"`.
  A resolução é escolhida a partir do prompt: pedindo 1024x1024 veio 1254x1254,
  pedindo 1536x1024 veio 1536x1024 na mosca. Ou seja, dá para pedir — só não dá
  para garantir.

## O bug que estava por baixo

`response.completed` do backend do Codex vem com `output: []`. Sempre. Os itens
de saída só existem nos eventos `response.output_item.done`.

Como `aggregate_response_from_sse()` devolvia o objeto do evento final, **todo
`POST /v1/responses` com `stream: false` respondia com output vazio** — inclusive
para texto puro, sem imagem nenhuma. A resposta parecia bem-sucedida (`status:
completed`, `usage` preenchido) e não tinha conteúdo.

Corrigido em `chatmock/responses_api.py`: os itens são acumulados por
`output_index` e remontados no objeto final quando ele vem vazio.

## O que mudou

| Arquivo | Mudança |
|---|---|
| `chatmock/images_api.py` | **novo** — monta o payload e converte para o formato da Images API. Sem import interno de propósito: `utils.py` importa este módulo, e `model_catalog -> utils` fecharia o ciclo |
| `chatmock/responses_api.py` | remonta `output` a partir dos `output_item.done` (o bug acima); `collect_images_from_sse()`, que fica aqui porque é este o módulo que já lê SSE |
| `chatmock/routes_openai.py` | rota `/v1/images/generations`; `image_generation` liberado em `responses_tools`; imagem vira data-url no `/v1/chat/completions` |
| `chatmock/utils.py` | imagem como delta de conteúdo no chat streaming, **depois** de fechar o `<think>` — o fechamento virou o helper `_close_think_tag()`, usado nos três pontos que antes repetiam o mesmo bloco |
| `chatmock/app.py`, `chatmock/cli.py` | flag `--image-model` / env `CHATGPT_LOCAL_IMAGE_MODEL` |
| `tests/test_routes.py` | 8 testes novos |

## Uso

```bash
python chatmock.py serve --port 8000
```

### `POST /v1/images/generations`

Compatível com a Images API da OpenAI, então SDK oficial, n8n e afins falam com
ela sem adaptação:

```bash
curl http://127.0.0.1:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt":"logo minimalista de uma raposa geometrica","size":"1024x1024"}'
```

```json
{ "created": 1786806013,
  "data": [{ "b64_json": "...", "revised_prompt": "...", "size": "1254x1254" }],
  "usage": { "input_tokens": 52, "output_tokens": 915, "total_tokens": 967 } }
```

Parâmetros:

- `prompt` — obrigatório.
- `n` — de 1 a 4. Cada unidade é **uma requisição a mais** na sua cota, porque o
  backend não aceita `n` no tool.
- `size` — vira instrução em texto ("quadrada", "horizontal", "vertical" +
  os pixels pedidos), já que o backend ignora o parâmetro. Trate como pedido,
  não como garantia: a proporção costuma sair certa, a resolução exata não.
- `quality`, `output_format`, `output_compression`, `background`, `moderation` —
  repassados ao tool. Se o backend recusar algum com `unknown_parameter`, a
  requisição é refeita uma vez com o tool pelado, para o cliente receber a imagem
  em vez de um 400.
- `image` — data-url (ou lista delas) para usar como referência. Não é a
  `/v1/images/edits` multipart da OpenAI, é um atalho em JSON.
- `chat_model` — troca o modelo que orquestra só nesta chamada.
- `response_format: "url"` responde 400: a imagem vem em base64 e o ChatMock não
  hospeda arquivo — igual ao comportamento do `gpt-image-1` na API real.

### Pelo `/v1/chat/completions`

```json
{ "model": "gpt-5.4-mini",
  "messages": [{"role": "user", "content": "gere uma imagem de um cubo azul"}],
  "responses_tools": [{"type": "image_generation"}] }
```

A imagem chega embutida no `content` como `![alt](data:image/png;base64,...)`,
em streaming ou não. Serve para UIs de chat que renderizam markdown.

Com `--reasoning-compat think-tags` (o padrão), a imagem sai **depois** do
`</think>`. Sem isso ela cairia dentro do bloco de raciocínio e sumiria em
qualquer cliente que esconde o `<think>` — que é justamente o motivo do modo
existir.

## Limites conhecidos

- **Peso.** Uma imagem passa de 2,5 MB em base64. Não ligue `--verbose` nessas
  rotas: o log imprime o corpo inteiro.
- Rotas Ollama (`/api/chat`) não foram tocadas — continuam só texto.
- O modelo de imagem é escolhido pelo backend. `model` no corpo da requisição não
  troca nada; existe para não quebrar cliente que sempre manda `gpt-image-1`.

## Rebase

As mudanças em arquivos que já existiam são pequenas e localizadas — o grosso
está em `images_api.py`, que é arquivo novo. Ao subir de versão, os pontos de
atrito são `aggregate_response_from_sse()`, os dois trechos de
`response.output_item.done` (em `routes_openai.py` e `utils.py`) e o
`_close_think_tag()`, que substituiu duas cópias de um bloco que o upstream
repetia dentro de `sse_translate_chat()`.

Comentários e mensagens de erro do código estão em inglês, como o resto do
repositório — só este arquivo está em português.
