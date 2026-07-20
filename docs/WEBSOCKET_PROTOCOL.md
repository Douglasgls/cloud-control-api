# Cloud Control WebSocket Protocol

Este documento define o protocolo oficial de comunicação WebSocket entre o
Cloud Control e os Agents. Todas as funcionalidades futuras — containers,
host, Tailscale, jobs, componentes e métricas — devem utilizar estes
envelopes, convenções e códigos de erro.

## Participantes

Existem apenas duas origens válidas:

- `cloud`: mensagem enviada pelo Cloud Control.
- `agent`: resposta ou erro enviado pelo Agent.

O campo `origin` deve sempre corresponder ao emissor da mensagem. O Cloud não
envia mensagens com `origin: "agent"`, e o Agent não envia respostas com
`origin: "cloud"`.

## Envelope padrão

Cada mensagem deve respeitar exatamente um dos envelopes a seguir. Campos não
documentados não devem ser adicionados ao envelope.

### Request

O Cloud solicita uma ação ao Agent.

```json
{
  "request_id": "uuid",
  "origin": "cloud",
  "type": "system.info",
  "payload": {}
}
```

| Campo | Significado |
| --- | --- |
| `request_id` | UUID gerado pelo Cloud para correlacionar a resposta ou o erro com a solicitação. |
| `origin` | Sempre `cloud` em uma request. |
| `type` | Nome da operação solicitada, seguindo a convenção de tipos. |
| `payload` | Objeto JSON com os dados específicos da operação; use `{}` quando não houver dados. |

### Response

O Agent informa que uma request foi processada com sucesso.

```json
{
  "request_id": "uuid",
  "origin": "agent",
  "success": true,
  "payload": {}
}
```

| Campo | Significado |
| --- | --- |
| `request_id` | Mesmo UUID recebido na request correspondente. |
| `origin` | Sempre `agent` em uma response. |
| `success` | Sempre `true` em uma response. |
| `payload` | Objeto JSON com o resultado da operação; use `{}` quando não houver resultado. |

### Error

O Agent informa que uma request não pôde ser concluída.

```json
{
  "request_id": "uuid",
  "origin": "agent",
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

| Campo | Significado |
| --- | --- |
| `request_id` | Mesmo UUID recebido na request correspondente. |
| `origin` | Sempre `agent` em um erro. |
| `success` | Sempre `false` em um erro. |
| `error.code` | Código estável e legível por máquina definido na seção de códigos de erro. |
| `error.message` | Descrição legível por pessoas, apropriada para logs e diagnóstico. |

## Convenção de tipos

Os tipos de operação devem seguir o formato `<domínio>.<ação>`, usando letras
minúsculas e pontos para separar domínio e ação. Todo novo tipo deve obedecer
a essa convenção.

Exemplos:

- `system.info`
- `system.ping`
- `tailscale.status`
- `container.list`
- `container.info`
- `container.start`
- `container.stop`
- `component.install`
- `job.subscribe`

`heartbeat` é reservado para o sinal de manutenção da conexão e permanece
como exceção de compatibilidade ao formato domínio/ação. Novas operações de
negócio não devem criar outras exceções; devem usar `<domínio>.<ação>`.

## Dispatcher e Handlers

O `Dispatcher` é responsável exclusivamente por localizar e executar o
`Handler` registrado para o campo `type`. Ele não deve conter regras de
negócio nem grandes blocos de `if`/`else`.

```text
system.info
    ↓
SystemHandler

heartbeat
    ↓
HeartbeatHandler

tailscale.status
    ↓
TailscaleHandler
```

Cada `Handler` conhece apenas o seu próprio domínio. Um Handler valida o
payload específico da sua operação, delega regras de negócio a Services e
retorna um envelope `Response` ou `Error` pelo `ConnectionManager`.

A separação de responsabilidades deve permanecer:

```text
ConnectionManager → Dispatcher → Handler → DTO → Service → Repository
```

- `ConnectionManager`: mantém conexões e envia envelopes serializados.
- `Dispatcher`: encontra o Handler registrado para o tipo solicitado.
- `Handler`: coordena a operação de um domínio, sem acessar persistência diretamente.
- `DTO`: valida e representa o payload de entrada e saída.
- `Service`: implementa regras de negócio.
- `Repository`: acessa os dados persistidos.

## Códigos de erro

Handlers devem reutilizar os códigos a seguir, em vez de criar variações para
o mesmo problema:

| Código | Quando usar |
| --- | --- |
| `INVALID_REQUEST` | Envelope ou payload inválido, ausente ou incompatível com o DTO. |
| `UNAUTHORIZED` | Token, origem ou permissão não autorizada. |
| `NOT_FOUND` | Recurso solicitado não existe. |
| `INTERNAL_ERROR` | Falha inesperada durante o processamento; não exponha detalhes sensíveis. |
| `HANDLER_NOT_FOUND` | Não existe Handler registrado para o tipo solicitado. |
| `TIMEOUT` | A operação excedeu o tempo limite definido. |

Quando for necessário um novo código, ele deve representar uma categoria nova
e reutilizável, ser escrito em `UPPER_SNAKE_CASE` e ser adicionado a este
documento antes de ser usado por um Handler.
