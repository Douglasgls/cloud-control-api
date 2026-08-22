# Guia de Integração Frontend — Cloud Control API

Este documento destina-se aos desenvolvedores frontend. Ele descreve a arquitetura geral do sistema, o funcionamento dos fluxos de comunicação e todas as rotas (HTTP e WebSocket) disponíveis na **Cloud Control API**, com exemplos detalhados de payload e respostas.

---

## 1. Visão Geral da Arquitetura (Como funciona por cima)

A **Cloud Control API** atua como o orquestrador central de ambientes remotos (como clusters Proxmox, servidores locais, etc.). 

O ecossistema é composto por 3 atores principais:

```mermaid
sequenceDiagram
    autonumber
    actor Frontend as Frontend (Web/Mobile)
    participant Cloud as Cloud Control API (Central)
    participant Agent as Agent / API Local (Proxmox/Server)
    actor Client as Cliente / App Desktop

    Note over Frontend, Cloud: 1. Autenticação e Gestão
    Frontend->>Cloud: POST /api/auth/login
    Cloud-->>Frontend: JWT de Usuário
    Frontend->>Cloud: POST /api/environments (Criar Ambiente)
    Cloud-->>Frontend: Dados do Ambiente + environment_token (Chave de instalação)

    Note over Agent, Cloud: 2. Autenticação do Agent e WebSocket Realtime
    Agent->>Cloud: POST /api/agent/auth (Usando environment_token)
    Cloud-->>Agent: JWT de Agent (Curta duração)
    Agent->>Cloud: Conecta WebSocket em /api/ws/agent?token=JWT
    Cloud<->>Agent: Canal bi-direcional (Heartbeat, Eventos, Comandos)

    Note over Client, Cloud: 3. Conexão de Cliente a Container Publicado
    Client->>Cloud: POST /api/client/connect (access_token do container)
    Cloud-->>Client: Instalações Tailscale/Headscale + preauth_key + connection_id
    Client->>Client: Executa handshake de rede (tailscale up)
    Client->>Cloud: POST /api/client/confirm (connection_id)
    Cloud-->>Client: Conexão Confirmada (CONNECTED)
```

### O papel de cada componente:
1. **Frontend (Usuário)**: Autentica o usuário humano, cria ambientes e visualiza o status e containers disponíveis.
2. **Agent / API Local**: Aplicação que roda dentro do ambiente do usuário. Autentica-se na Cloud usando um `environment_token` permanente para obter um JWT temporário de Agent, conectando-se via **WebSocket** para trocar comandos e métricas em tempo real.
3. **Client / App de Conexão**: Cliente final que deseja se conectar com segurança a um container publicado via rede privada Headscale/Tailscale.

---

## 2. Autenticação e Cabeçalhos (Headers)

A API utiliza tokens **JWT (JSON Web Token)** no padrão HTTP Bearer para rotas protegidas.

### Header de Autenticação
```http
Authorization: Bearer <access_token>
```

### Tipos de Tokens no Sistema
| Tipo de Token | Onde é obtido | Uso |
| --- | --- | --- |
| **JWT de Usuário** (`type: "user"`) | `POST /api/auth/login` | Usado pelo Frontend nas rotas autenticadas (ex: `/api/environments`). |
| **Token do Ambiente** (`environment_token`) | `POST /api/environments` | Chave permanente para instalação/registro do Agent no servidor local. Exibida **uma única vez** na criação. |
| **JWT de Agent** (`type: "agent"`) | `POST /api/agent/auth` | Obtido pelo Agent trocando o `environment_token`. Usado para conectar no WebSocket (`/api/ws/agent`). |
| **Token de Acesso ao Container** | Gerado no gerenciamento de containers | Chave utilizada pelo cliente final em `POST /api/client/connect`. |

---

## 3. Catálogo das Rotas HTTP

### 3.1. Healthcheck

#### `GET /api/health` ou `GET /health`
Verifica se a API está online e respondendo.

- **Autenticação**: Nenhuma
- **Status HTTP de Sucesso**: `200 OK`
- **Response**:
```json
{
  "status": "ok"
}
```

---

### 3.2. Autenticação de Usuários (`/api/auth`)

#### `POST /api/auth/register`
Cadastra um novo usuário no sistema.

- **Autenticação**: Nenhuma
- **Status HTTP de Sucesso**: `201 Created`
- **Request Body**:
```json
{
  "name": "Nome do Usuário",
  "email": "usuario@exemplo.com",
  "password": "senhaSegura123"
}
```
- **Response (`UserResponseDTO`)**:
```json
{
  "id": 1,
  "name": "Nome do Usuário",
  "email": "usuario@exemplo.com"
}
```

---

#### `POST /api/auth/login`
Autentica o usuário e retorna o token de acesso (JWT).

- **Autenticação**: Nenhuma
- **Status HTTP de Sucesso**: `200 OK`
- **Request Body**:
```json
{
  "email": "usuario@exemplo.com",
  "password": "senhaSegura123"
}
```
- **Response (`LoginResponseDTO`)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "Nome do Usuário",
    "email": "usuario@exemplo.com"
  }
}
```

---

### 3.3. Gerenciamento de Ambientes (`/api/environments`)

#### `POST /api/environments`
Cria um novo ambiente e gera seu token de instalação único.

> [!IMPORTANT]
> O campo `environment_token` é exibido **somente nesta resposta**. O Frontend deve instruir o usuário a guardar esse token para configurar a API Local/Agent.

- **Autenticação**: Requer `Authorization: Bearer <user_access_token>`
- **Status HTTP de Sucesso**: `201 Created`
- **Request Body**:
```json
{
  "name": "Meu Ambiente Proxmox",
  "description": "Servidor local de desenvolvimento"
}
```
- **Response (`EnvironmentResponseDTO`)**:
```json
{
  "environment_id": "env_abc123xyz",
  "name": "Meu Ambiente Proxmox",
  "description": "Servidor local de desenvolvimento",
  "status_online": false,
  "last_ping": null,
  "environment_token": "env_token_sec_987654321..."
}
```

---

### 3.4. Autenticação de Agent (`/api/agent`)

#### `POST /api/agent/auth`
Troca o `environment_token` permanente por um JWT de Agent com tempo de expiração curto.

- **Autenticação**: Nenhuma (o token vai no corpo da requisição)
- **Status HTTP de Sucesso**: `200 OK`
- **Request Body**:
```json
{
  "environment_token": "env_token_sec_987654321..."
}
```
- **Response (`AgentAuthenticationResponseDTO`)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 3.5. Conexão de Clientes Finais (`/api/client`)

#### `POST /api/client/connect`
Valida o token de acesso do cliente, verifica se o ambiente, nó e container estão online e se o Headscale/Tailscale está pronto. Se aprovado, retorna os parâmetros de conexão.

- **Autenticação**: Nenhuma (passa o token no corpo)
- **Status HTTP de Sucesso**: `200 OK` (quando autorizado)
- **Request Body**:
```json
{
  "access_token": "container_access_token_raw_string"
}
```
- **Response Autorizada (`ClientConnectionResponseDTO`)**:
```json
{
  "authorized": true,
  "code": null,
  "message": null,
  "connection": {
    "connection_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "login_server": "https://headscale.dominio.com",
    "preauth_key": "authkey_987654321",
    "hostname": "container-app-node",
    "tailscale_ip": "100.64.0.15",
    "tailscale_ipv6": "fd7a:115c:a1e0::15",
    "expires_at": "2026-08-21T12:00:00Z"
  }
}
```

- **Response Não Autorizada (Status HTTP varia conforme erro)**:
  - `401 Unauthorized`: Token não encontrado, expirado ou revogado.
  - `403 Forbidden`: Ambiente, nó ou container offline, ou Tailscale não instalado/parado.
  - `404 Not Found`: Ambiente, nó ou container não encontrado.
```json
{
  "authorized": false,
  "code": "ENVIRONMENT_OFFLINE",
  "message": "O ambiente correspondente encontra-se offline.",
  "connection": {}
}
```

---

#### `POST /api/client/confirm`
Confirma que o cliente conseguiu realizar o handshake de rede e transiciona o estado da conexão para `CONNECTED`.

- **Autenticação**: Nenhuma
- **Status HTTP de Sucesso**: `200 OK` (quando confirmado com sucesso)
- **Request Body**:
```json
{
  "connection_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
- **Response (`ClientConnectionConfirmResponseDTO`)**:
```json
{
  "success": true,
  "connection_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "CONNECTED",
  "connected_at": "2026-08-21T10:30:00Z",
  "code": null,
  "message": null
}
```

---

## 4. Comunicação Realtime (WebSocket)

A comunicação em tempo real é usada primariamente para manter a sincronização viva entre a API Central e os Agents nos ambientes.

### Endpoint WebSocket
```http
WS /api/ws/agent?token=<agent_jwt>
```

### Formato das Mensagens (Envelope Padrão)

Todas as mensagens enviadas e recebidas usam uma estrutura de envelope rigorosamente tipada.

#### Request (Enviada pelo Cloud para o Agent)
```json
{
  "request_id": "d0e12345-6789-4abc-9def-123456789abc",
  "origin": "cloud",
  "type": "system.info",
  "payload": {}
}
```

#### Response (Resposta do Agent para o Cloud em caso de sucesso)
```json
{
  "request_id": "d0e12345-6789-4abc-9def-123456789abc",
  "origin": "agent",
  "success": true,
  "payload": {
    "hostname": "proxmox-node-01",
    "uptime": 123456
  }
}
```

#### Error (Resposta do Agent em caso de falha)
```json
{
  "request_id": "d0e12345-6789-4abc-9def-123456789abc",
  "origin": "agent",
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Payload inválido ou ausente."
  }
}
```

### Principais Tipos de Operação (`type`)
- `heartbeat`: Manutenção de conectividade e verificação de disponibilidade (sinal de ping/pong).
- `system.info`: Consulta de informações do sistema host.
- `event.publish`: Publicação de eventos internos.
- `environment.changed`: Notificação de alterações de estado no ambiente.

---

## 5. Códigos de Erro de Validação (`ValidationCode`)

Abaixo estão os códigos estáveis retornados em rotas de conexão de clientes (`POST /client/connect` e `POST /client/confirm`):

| Código Enum | Status HTTP | Descrição / Motivo |
| --- | --- | --- |
| `TOKEN_NOT_FOUND` | `401 Unauthorized` | O access_token fornecido não existe. |
| `TOKEN_REVOKED` | `401 Unauthorized` | O token foi revogado pelo administrador. |
| `TOKEN_EXPIRED` | `401 Unauthorized` | O token de acesso expirou. |
| `ENVIRONMENT_NOT_FOUND` | `404 Not Found` | O ambiente associado não foi encontrado. |
| `ENVIRONMENT_OFFLINE` | `403 Forbidden` | O ambiente do container está offline. |
| `CONTAINER_NOT_FOUND` | `404 Not Found` | O container publicado não foi encontrado. |
| `CONTAINER_OFFLINE` | `403 Forbidden` | O container encontra-se desligado/offline. |
| `NODE_NOT_FOUND` | `404 Not Found` | O nó do cluster associado não foi encontrado. |
| `NODE_OFFLINE` | `403 Forbidden` | O nó Proxmox/Host está offline. |
| `TAILSCALE_NOT_INSTALLED` | `403 Forbidden` | Tailscale/Headscale não está instalado no nó. |
| `TAILSCALE_SERVICE_STOPPED` | `403 Forbidden` | O serviço do Tailscale está parado no nó. |
| `CONNECTION_NOT_FOUND` | `404 Not Found` | ID de conexão não encontrado no handshake. |
| `CONNECTION_EXPIRED` | `400 Bad Request` | A janela de tempo para confirmação da conexão expirou. |

---

## 6. Exemplos de Código para o Frontend (TypeScript)

### 6.1. Cliente HTTP Base

```typescript
const API_BASE_URL = 'http://localhost:8000'; // Ajuste conforme seu ambiente

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || data.message || 'Erro na requisição');
  }

  return data as T;
}
```

### 6.2. Autenticação e Criação de Ambiente

```typescript
interface LoginResponse {
  access_token: string;
  token_type: string;
  user: { id: number; name: string; email: string };
}

interface EnvironmentResponse {
  environment_id: string;
  name: string;
  description: string | null;
  status_online: boolean;
  environment_token: string;
}

// 1. Fazer Login
async function login(email: string, password: string): Promise<string> {
  const res = await apiFetch<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  
  // Armazene o res.access_token com segurança (ex: estado global / storage)
  return res.access_token;
}

// 2. Criar Ambiente (requer token de usuário)
async function createEnvironment(
  userToken: string,
  name: string,
  description?: string
): Promise<EnvironmentResponse> {
  return await apiFetch<EnvironmentResponse>(
    '/api/environments',
    {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    },
    userToken
  );
}
```
