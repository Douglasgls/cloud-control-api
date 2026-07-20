# Fluxo e Estrutura da Conexão WebSocket (Realtime)

Este documento explica detalhadamente a arquitetura de comunicação bidirecional em tempo real entre o **Cloud Control API** (Cloud) e os **Agents**, cobrindo o papel de cada arquivo no diretório [realtime](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime) e o ciclo de vida completo de uma conexão.

---

## 1. Estrutura de Arquivos e Responsabilidades

A pasta `app/realtime/` está estruturada da seguinte forma:

```text
app/realtime/
├── handlers/
│   ├── __init__.py
│   ├── heartbeat.py           # Processa pings periódicos (heartbeat) vindos do Agent
│   └── system.py              # Processa requisições de informações do sistema (system.info)
├── connection_manager.py      # Gerencia as conexões ativas na memória RAM
├── dispatcher.py              # Roteia mensagens recebidas para os handlers específicos
├── manager.py                 # Orquestra o ciclo de vida do WebSocket (loop principal de leitura)
├── models.py                  # Define a entidade de Conexão e seu comportamento de requisição
├── protocol.py                # Modelos de validação de dados (Pydantic) para o protocolo WS
└── websocket.py               # Ponto de entrada (Endpoint WebSocket) e autenticação JWT
```

### Detalhamento dos Arquivos

#### 1. [websocket.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/websocket.py)
* **O que faz:** Define a rota do WebSocket (`/ws/agent`).
* **Responsabilidade:** 
  * Realiza a autenticação inicial extraindo e validando o token JWT passado como query parameter.
  * Garante que o token pertence a um `agent` e extrai as informações de `environment_id` e `user_id`.
  * Registra os handlers de eventos no `Dispatcher`.
  * Passa o controle da conexão aceita para o `RealtimeManager`.
* **Onde é usado:** É incluído no arquivo principal da aplicação ([main.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/main.py)) através de `app.include_router(realtime_router)`.

#### 2. [connection_manager.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/connection_manager.py)
* **O que faz:** Mantém um dicionário na memória RAM com todas as conexões ativas (`active_connections`), indexadas pelo `environment_id`.
* **Responsabilidade:**
  * Armazenar conexões ativas ao conectar e removê-las ao desconectar.
  * Fornecer métodos auxiliares para enviar mensagens para um ambiente específico (`send`) ou transmitir para todos (`broadcast`).
* **Onde é usado:** Instanciado globalmente em [websocket.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/websocket.py) e consumido pelo `RealtimeManager`.

#### 3. [models.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/models.py)
* **O que faz:** Define o dataclass `Connection`, que agrupa o objeto `WebSocket` do FastAPI, os metadados do agente conectado e um dicionário de requisições pendentes (`pending_requests`).
* **Responsabilidade:**
  * Implementa o método assíncrono `request(message_type, payload)`. Quando a Cloud precisa pedir algo ao Agent de forma assíncrona, este método gera um `request_id` único (UUID), cria um `asyncio.Future()`, envia a mensagem em formato JSON pelo WebSocket e aguarda (`await`) que o Future seja completado quando a resposta correspondente retornar.
* **Onde é usado:** Importado em praticamente todo o fluxo de realtime para tipar as conexões e interagir com o WebSocket.

#### 4. [protocol.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/protocol.py)
* **O que faz:** Define os schemas Pydantic de serialização e validação das mensagens de acordo com o [WEBSOCKET_PROTOCOL.md](file:///home/douglas/Documents/project_tcc/cloud_control_api/WEBSOCKET_PROTOCOL.md).
* **Responsabilidade:**
  * `WebSocketMessage`: Envelope de requisição (Request).
  * `WebSocketResponse`: Envelope de resposta com sucesso (Response).
  * `WebSocketError` e `WebSocketErrorDetail`: Envelope de resposta de erro (Error).
* **Onde é usado:** Utilizado no `RealtimeManager` e no `ConnectionManager` para validar e serializar as mensagens trafegadas.

#### 5. [dispatcher.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/dispatcher.py)
* **O que faz:** Mecanismo simples de roteamento de eventos.
* **Responsabilidade:**
  * Registrar funções callback (handlers) associadas a um tipo de mensagem (`type`).
  * Despachar a mensagem recebida para o handler registrado correto.
* **Onde é usado:** Instanciado em [websocket.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/websocket.py) onde os handlers são registrados, e executado no loop do `RealtimeManager`.

#### 6. [manager.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/manager.py)
* **O que faz:** O cérebro da orquestração realtime.
* **Responsabilidade:**
  * Aceitar fisicamente a conexão WebSocket (`websocket.accept()`).
  * Atualizar o status do ambiente no banco de dados para **Online** (`is_online=True`).
  * Disparar a sincronização inicial do ambiente (`environment.sync`) em segundo plano (background task).
  * Executar o loop infinito de leitura de mensagens (`while True: await websocket.receive_text()`).
  * Diferenciar se uma mensagem recebida do Agent é uma **resposta** a um pedido que a Cloud fez (completando o `asyncio.Future` pendente correspondente) ou se é uma **requisição** iniciada pelo Agent (repassando-a para o `Dispatcher`).
  * Limpar a conexão e marcar o ambiente como **Offline** se o WebSocket fechar.
* **Onde é usado:** Instanciado em [websocket.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/websocket.py).

#### 7. [handlers/heartbeat.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/handlers/heartbeat.py)
* **O que faz:** Processa a mensagem do tipo `heartbeat` enviada pelo Agent.
* **Responsabilidade:** Atualiza o campo `last_heartbeat` na conexão e envia de volta um `heartbeat.response` para manter o canal de comunicação aberto.

#### 8. [handlers/system.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/handlers/system.py)
* **O que faz:** Processa mensagens do tipo `system.info` enviadas pelo Agent. Retorna metadados básicos de versão e status.

---

## 2. Passo a Passo do Fluxo de Comunicação

Abaixo está o ciclo de vida detalhado de uma conexão e da troca de mensagens:

### Passo 1: O Handshake e Conexão (Agent -> Cloud)
1. O **Agent** inicia uma conexão HTTP de upgrade para WebSocket na URL:
   `ws://cloud-api/ws/agent?token=<JWT_TOKEN>`
2. O FastAPI intercepta a chamada no endpoint de [websocket.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/websocket.py#L38).
3. A dependência `get_token` valida a presença do token.
4. O método `decode_access_token` valida a assinatura do JWT, verifica se o tipo de claims (`type`) é igual a `"agent"`, e extrai o `environment_id` e o `user_id`.
5. Se tudo estiver correto, chama `realtime_manager.start`.

### Passo 2: Registro e Atualização de Status
No método `start` do [manager.py](file:///home/douglas/Documents/project_tcc/cloud_control_api/app/realtime/manager.py#L48):
1. A API executa `await websocket.accept()` finalizando o aperto de mão (handshake).
2. É criado um objeto `Connection` contendo os dados do agente e a referência do socket.
3. A conexão é registrada no `ConnectionManager` através de `self.connection_manager.connect(connection)`.
4. O status do ambiente no banco de dados é atualizado para `is_online=True` e `last_ping` é definido com a hora atual.

### Passo 3: Sincronização Automática Inicial (Cloud -> Agent -> Cloud)
Imediatamente após aceitar a conexão, o `RealtimeManager` cria uma tarefa em segundo plano:
1. Executa `asyncio.create_task(self._sync_environment(connection))`.
2. O método `_sync_environment` faz uma requisição assíncrona para o Agent invocando `await connection.request("environment.sync", {})`.
3. Internamente, o método `request` em `models.py`:
   * Cria um `request_id` (UUID).
   * Associa um `asyncio.Future()` a esse ID em `pending_requests`.
   * Envia o JSON de requisição para o Agent via WebSocket:
     ```json
     {
       "request_id": "8b92b3a8-4fa7-4f67-a50d-d4e5088f117c",
       "origin": "cloud",
       "type": "environment.sync",
       "payload": {}
     }
     ```
   * Fica pausado em `await fut` esperando a resposta.
4. O **Agent** recebe o comando, monta um snapshot do ambiente local (containers rodando, status, etc) e responde:
     ```json
     {
       "request_id": "8b92b3a8-4fa7-4f67-a50d-d4e5088f117c",
       "origin": "agent",
       "success": true,
       "payload": {
         "containers": [...],
         "system_info": {...}
       }
     }
     ```
5. O loop de leitura da Cloud em `manager.py` recebe esses dados, identifica que a chave `"success"` está no payload (sinalizando que é uma resposta), busca pelo `request_id` em `pending_requests` e injeta o resultado com `future.set_result(payload)`.
6. O `await connection.request` é destravado no `_sync_environment`. Os dados do payload são validados pelo `EnvironmentSnapshotDTO` e salvos no banco através do `EnvironmentSyncService`.

### Passo 4: O Loop de Mensagens Geral
Uma vez conectada, a conexão permanece no loop infinito do `RealtimeManager`:
* Cada mensagem recebida do Agent atualiza o `last_heartbeat` da conexão na RAM e o `last_ping` no banco.
* O fluxo diverge com base na mensagem:
  * **Se for uma resposta de uma requisição iniciada pela Cloud:** Contém `"success"`. Encontra o `Future` pendente e o resolve.
  * **Se for uma requisição iniciada pelo Agent:** Não contém `"success"`. É mapeada como um `WebSocketMessage` e direcionada para o `Dispatcher`.

#### Exemplo: Envio de Heartbeat pelo Agent (Agent -> Cloud -> Agent)
1. De tempos em tempos (ex: a cada 30 segundos), o Agent envia uma mensagem de heartbeat:
   ```json
   {
     "request_id": "f516a5b2-38ef-4cde-8e50-f8fa266016e3",
     "origin": "agent",
     "type": "heartbeat",
     "payload": {}
   }
   ```
2. O loop em `manager.py` lê a mensagem, vê que **não** possui o campo `"success"`, e instancia `WebSocketMessage.model_validate(payload)`.
3. Chama `await self.dispatcher.dispatch(connection, message)`.
4. O `Dispatcher` localiza o handler registrado para o tipo `"heartbeat"`, que é a classe `HeartbeatHandler`.
5. O `HeartbeatHandler` atualiza o timestamp `connection.last_heartbeat = datetime.now(timezone.utc)`.
6. Envia de volta o envelope de resposta:
   ```json
   {
     "request_id": "f516a5b2-38ef-4cde-8e50-f8fa266016e3",
     "origin": "cloud",
     "success": true,
     "type": "heartbeat.response",
     "payload": {}
   }
   ```

### Passo 5: Desconexão (Agent / Cloud)
1. Se a conexão for cortada (ex: Agent desliga ou há falha de rede), o loop do `manager.py` captura a exceção `WebSocketDisconnect`.
2. Remove a conexão da lista ativa: `self.connection_manager.disconnect(environment_id)`.
3. Atualiza o banco de dados do ambiente para Offline: `is_online=False` e registra o `last_ping` final.
