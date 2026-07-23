# Documento de Arquitetura Atual — Cloud Control API

Este documento serve como uma fotografia detalhada do estado atual da Cloud Control API, servindo de base para decisões arquiteturais e refatorações futuras.

---

## 1. Visão Geral do Sistema

A **Cloud Control API** é o painel de controle e orquestração central de uma infraestrutura baseada em Tailscale/Headscale para acesso seguro a ambientes contendo containers publicados. 

### Módulos Existentes
O projeto está estruturado em pacotes Python com responsabilidades bem definidas:
*   `app/api`: Rotas HTTP públicas expostas pelo framework FastAPI.
*   `app/auth`: Utilitários e funções auxiliares de segurança, criptografia de senhas (bcrypt) e geração/decodificação de tokens JWT.
*   `app/controllers`: Controladores HTTP que recebem as requisições FastAPI e delegam para os serviços de negócios.
*   `app/core`: Configurações globais da aplicação carregadas através de variáveis de ambiente via `pydantic-settings`.
*   `app/db`: Configuração do banco de dados, pool de conexões com PostgreSQL usando SQLAlchemy e definições de sessão.
*   `app/dto` / `app/dtos`: Objetos de Transferência de Dados (DTOs) usados na camada de API HTTP e WebSocket.
*   `app/models`: Modelos ORM do SQLAlchemy representando as tabelas do banco de dados.
*   `app/realtime`: Gerenciamento do ciclo de vida das conexões WebSocket de agentes externos, incluindo despacho e tratamento de mensagens em tempo real.
*   `app/repositories`: Camada de acesso a dados (Repository Pattern) que abstrai as consultas SQLAlchemy.
*   `app/services`: Camada de regras de negócio, dividida em serviços locais do domínio da Cloud e serviços específicos de integração com o Headscale.
*   `app/utils`: Funções e utilitários auxiliares genéricos.

### Fluxo de Comunicação Agent → Cloud → Banco
```
[Agent]
   │  (1) Autentica enviando o Token do Ambiente (Permanente)
   ▼
[Cloud / HTTP API] ──(2) Verifica Token ──► [Banco de Dados]
   │
   │  (3) Retorna JWT de Sessão de Curta Duração
   ▼
[Agent]
   │  (4) Estabelece conexão WebSocket usando JWT
   ▼
[Cloud / WebSocket]
   │
   │  (5) Envia solicitação de sincronização ("environment.sync")
   ▼
[Agent]
   │  (6) Coleta estado local (containers, nodes, tokens) e envia Snapshot
   ▼
[Cloud / WebSocket]
   │
   │  (7) Processa Snapshot e atualiza tabelas
   ▼
[Banco de Dados]
```

### Integrações Implementadas
*   **WebSocket**: Conexão persistente bidirecional entre os Agents (rodando nos hosts de containers) e a Cloud para sincronização de estado e eventos.
*   **JWT**: Tokens criptográficos de curta duração gerados para autenticar as conexões WebSocket dos Agents e chamadas HTTP de usuários.
*   **Headscale REST API**: Camada de integração com a API oficial do Headscale via chamadas HTTP REST (`httpx.Client`), encapsulada em DTOs, exceções próprias, mappers e serviços modulares.

---

## 2. Modelo de Dados Atual

O banco de dados é gerenciado via SQLAlchemy ORM e possui os seguintes modelos e tabelas estruturadas:

### Tabela: `users`
*   **Finalidade**: Representa os usuários administradores/proprietários da plataforma.
*   **Campos**:
    *   `id` (`Integer`): Chave Primária, autoincremento.
    *   `name` (`String(255)`): Nome completo do usuário.
    *   `email` (`String(255)`): E-mail do usuário (Único, Indexado).
    *   `password_hash` (`String(255)`): Hash bcrypt da senha de acesso.
    *   `created_at` (`DateTime`): Data de criação do registro (TimestampMixin).
    *   `updated_at` (`DateTime`): Data da última atualização (TimestampMixin).
*   **Relacionamentos**:
    *   `environments` (1:N com `Environment`, cascata: `all, delete-orphan`).
    *   `audit_logs` (1:N com `AuditLog`).

### Tabela: `environments`
*   **Finalidade**: Representa os ambientes gerenciados pelos agentes (hosts físicos/virtuais rodando containers).
*   **Campos**:
    *   `id` (`String(36)`): Chave Primária, UUID gerado automaticamente.
    *   `user_id` (`Integer`): FK para `users.id` (`ondelete="CASCADE"`).
    *   `name` (`String(255)`): Nome do ambiente.
    *   `description` (`Text`): Detalhes textuais opcionais.
    *   `environment_token_hash` (`String(255)`): Hash do token permanente de autenticação do agente (Único).
    *   `status_online` (`Boolean`): Indica se o agente está online.
    *   `last_ping` (`DateTime`): Data/hora do último heartbeat recebido.
    *   `created_at` (`DateTime`): Data de criação do registro.
    *   `updated_at` (`DateTime`): Data de atualização.
*   **Relacionamentos**:
    *   `user` (N:1 com `User`).
    *   `published_containers` (1:N com `PublishedContainer`, cascata: `all, delete-orphan`).

### Tabela: `published_containers`
*   **Finalidade**: Representa os containers implantados no host do agente que foram marcados/publicados para acesso externo.
*   **Campos**:
    *   `id` (`Integer`): Chave Primária, autoincremento.
    *   `environment_id` (`String`): FK para `environments.id` (`ondelete="CASCADE"`).
    *   `api_local_container_id` (`String`): ID interno do container no Agent (ex: VMID ou ID docker).
    *   `container_number` (`Integer`): Número sequencial de identificação (ex: VMID).
    *   `name` (`String(255)`): Nome de exibição do container.
    *   `status` (`String(50)`): Estado de execução do container (ex: `running`, `stopped`).
    *   `created_at` (`DateTime`): Data de criação.
    *   `updated_at` (`DateTime`): Data de atualização.
*   **Restrições e Índices**:
    *   `uq_published_containers_env_local_id`: Constraint única composta sobre (`environment_id`, `api_local_container_id`).
*   **Relacionamentos**:
    *   `environment` (N:1 com `Environment`).
    *   `published_node` (1:1 com `PublishedNode`, cascata: `all, delete-orphan`).
    *   `access_tokens` (1:N com `AccessToken`, cascata: `all, delete-orphan`).
    *   `connections` (1:N com `Connection`, cascata: `all, delete-orphan`).

### Tabela: `published_nodes`
*   **Finalidade**: Armazena as informações do cliente VPN (Tailscale) instalado dentro do container publicado.
*   **Campos**:
    *   `id` (`Integer`): Chave Primária, autoincremento.
    *   `published_container_id` (`Integer`): FK para `published_containers.id` (`ondelete="CASCADE"`, Único).
    *   `installed` (`Boolean`): Indica se o binário do Tailscale está presente no container.
    *   `service_running` (`Boolean`): Indica se o daemon do Tailscale (`tailscaled`) está rodando.
    *   `version` (`String(50)`): Versão instalada do Tailscale.
    *   `machine_id` (`String(255)`): ID da máquina gerado no controle do Headscale.
    *   `node_key` (`String(255)`): Chave criptográfica pública da máquina.
    *   `tailscale_ip` (`String(45)`): IP interno atribuído na rede VPN (CGNAT 100.64.0.0/10).
    *   `online` (`Boolean`): Indica se o nó VPN está conectado ativamente na rede.
    *   `last_sync` (`DateTime`): Data/hora da última sincronização bem sucedida de estado do nó.
    *   `created_at` (`DateTime`): Data de criação.
    *   `updated_at` (`DateTime`): Data de atualização.
*   **Relacionamentos**:
    *   `published_container` (1:1 com `PublishedContainer`).

### Tabela: `access_tokens`
*   **Finalidade**: Tokens criados na Cloud para conceder acesso de clientes externos a containers específicos.
*   **Campos**:
    *   `id` (`Integer`): Chave Primária, autoincremento.
    *   `published_container_id` (`Integer`): FK para `published_containers.id` (`ondelete="CASCADE"`).
    *   `api_local_token_id` (`String(255)`): ID do token importado ou mapeado na API do agente.
    *   `token_hash` (`String(255)`): Hash SHA-256 do token de acesso do cliente.
    *   `description` (`Text`): Descrição do propósito do token.
    *   `expires_at` (`DateTime`): Data de validade do token.
    *   `active` (`Boolean`): Flag de ativação/revogação.
    *   `revoked_at` (`DateTime`): Registro de data/hora de revogação.
    *   `created_at` (`DateTime`): Data de criação.
    *   `updated_at` (`DateTime`): Data de atualização.
*   **Relacionamentos**:
    *   `published_container` (N:1 com `PublishedContainer`).
    *   `connections` (1:N com `Connection`, cascata: `all, delete-orphan` em alterações futuras, atualmente `ondelete="RESTRICT"` na FK).

### Tabela: `connections`
*   **Finalidade**: Registra as sessões de conexão ativas ou históricas iniciadas por clientes para containers individuais usando tokens.
*   **Campos**:
    *   `id` (`Integer`): Chave Primária, autoincremento.
    *   `published_container_id` (`Integer`): FK para `published_containers.id` (`ondelete="CASCADE"`).
    *   `access_token_id` (`Integer`): FK para `access_tokens.id` (`ondelete="RESTRICT"`).
    *   `started_at` (`DateTime`): Data/hora de início da conexão de tunelamento.
    *   `created_at` (`DateTime`): Data de criação.
    *   `updated_at` (`DateTime`): Data de atualização.
*   **Relacionamentos**:
    *   `published_container` (N:1 com `PublishedContainer`).
    *   `access_token` (N:1 com `AccessToken`).

### Tabela: `audit_logs`
*   **Finalidade**: Registra ações críticas tomadas por usuários para auditoria de segurança.
*   **Campos**:
    *   `id` (`Integer`): Chave Primária, autoincremento.
    *   `user_id` (`Integer`): FK para `users.id` (`ondelete="SET NULL"`, Nulo permitido).
    *   `action` (`String(100)`): Ação efetuada (ex: `LOGIN`, `CREATE_ENV`).
    *   `resource_type` (`String(100)`): Tipo do recurso afetado.
    *   `resource_id` (`String(255)`): Identificador único do recurso afetado.
    *   `details` (`JSON`): Estrutura livre contendo metadados extras.
    *   `ip_address` (`String(45)`): IP do usuário que realizou a ação.
    *   `created_at` (`DateTime`): Data de criação.
    *   `updated_at` (`DateTime`): Data de atualização.
*   **Relacionamentos**:
    *   `user` (N:1 com `User`).

---

## 4. Fluxos Já Implementados

### Fluxo A: Registro e Conexão do Agent
1.  O Agent envia o token permanente (`environment_token`) configurado via `POST /agent/auth`.
2.  A Cloud calcula o hash do token, valida no banco a existência do correspondente `Environment` e retorna um **JWT de curta duração** contendo os payloads `environment_id` e `user_id`.
3.  O Agent se conecta ao endpoint WebSocket `/ws/agent?token=<JWT>`.
4.  A Cloud decodifica o JWT no aperto de mão, associa o WebSocket na memória (`RealtimeManager` e `ConnectionManager`) e define o estado do ambiente no banco como `status_online = True`.

### Fluxo B: Sincronização do Ambiente (Environment Sync)
1.  Imediatamente após a conexão WebSocket do Agent, a Cloud dispara de forma assíncrona um comando `"environment.sync"` ao Agent.
2.  O Agent recebe a mensagem, monta um snapshot do seu estado atual contendo a lista de contêineres, metadados do Tailscale instalados neles e tokens de acesso, retornando este snapshot em formato JSON.
3.  O `RealtimeManager` captura a resposta, valida o payload estruturado via `EnvironmentSnapshotDTO` e passa os dados para o `EnvironmentSyncService`.
4.  O `EnvironmentSyncService` executa um bloco transacional aninhado no banco de dados (`db.begin_nested()`) coordenando os seguintes passos:
    *   **Containers**: Cria contêineres inexistentes ou atualiza aqueles com alterações de nome, VMID ou status de execução via `PublishedContainerSyncService`.
    *   **Tailscale Nodes**: Cria/atualiza o status da instalação, serviço rodando, machine_id, node_key, IP atribuído e status online via `PublishedNodeSyncService`.
    *   **Access Tokens**: Sincroniza hashes de tokens permitidos e datas de expiração e revogação via `AccessTokenSyncService`.

### Fluxo C: Autorização e Publicação de Container
1.  Um cliente externo solicita conexão enviando o token de acesso (`access_token`) via `POST /client/connect`.
2.  O `ClientConnectionResolver` resolve o hash SHA-256 do token, obtendo a árvore de entidades associadas: `AccessToken` → `PublishedContainer` → `Environment` e `PublishedNode`.
3.  O `ContainerAccessAuthorizationService` executa sequencialmente **11 validações** estruturadas na memória sobre essa árvore de entidades (validando existência do token, status do container, status da VPN no nó, etc.).
4.  Se todas as validações forem aprovadas, o serviço de auditoria `ConnectionAuditService` registra a autorização, e o `ConnectionResponseBuilder` monta as instruções de acesso do cliente (`ConnectionInstructionsDTO`).

---

## 5. Serviços Existentes

### `AccessTokenResolver`
*   **Responsabilidade**: Hash de tokens brutos em SHA-256 e resolução da entidade correspondente no banco.
*   **Quem chama**: `ClientConnectionResolver`.
*   **Quem utiliza**: Camada de autenticação/autorização de túneis de conexão de clientes.

### `AccessTokenSyncService`
*   **Responsabilidade**: Sincronização estruturada da lista de tokens enviada pelo Agent com o banco.
*   **Quem chama**: `PublishedContainerSyncService`.
*   **Quem utiliza**: Fluxo de sincronização em tempo real do WebSocket.

### `AgentAuthenticationService`
*   **Responsabilidade**: Autentica o Agent validando seu token permanente e retornando um JWT curto de acesso.
*   **Quem chama**: `/agent/auth` (HTTP controller em `app/api/endpoints/agent.py` ou similar).
*   **Quem utiliza**: Agents no momento do boot.

### `AuthenticationService`
*   **Responsabilidade**: Autentica usuários administradores locais por e-mail/senha e emite JWTs de acesso.
*   **Quem chama**: Rotas HTTP de login.
*   **Quem utiliza**: Usuários finais acessando a API/Painel Administrativo.

### `ClientConnectionResolver`
*   **Responsabilidade**: Carregar na memória de forma centralizada todas as dependências do banco necessárias para validar a conexão.
*   **Quem chama**: `ClientConnectionService`.
*   **Quem utiliza**: Fluxo de autorização HTTP de clientes.

### `ClientConnectionService`
*   **Responsabilidade**: Coordenador geral do fluxo de conexões externas. Orquestra a resolução das entidades, a execução das validações de acesso, auditoria e geração da resposta.
*   **Quem chama**: `/client/connect` (HTTP controller).
*   **Quem utiliza**: Clientes VPN externos tentando se autenticar e conectar.

### `ConnectionAuditService`
*   **Responsabilidade**: Gravar logs detalhados e estruturados sobre tentativas bem-sucedidas ou negadas de conexão.
*   **Quem chama**: `ClientConnectionService`.
*   **Quem utiliza**: Logs de auditoria do sistema.

### `ConnectionResponseBuilder`
*   **Responsabilidade**: Montar os metadados de resposta formatada com instruções de conexão para o cliente (endereço do servidor, chaves, hostname).
*   **Quem chama**: `ClientConnectionService`.
*   **Quem utiliza**: Clientes finais tentando conectar.

### `ContainerAccessAuthorizationService`
*   **Responsabilidade**: Conter as regras puras de validação (11 validações estritas) sobre o contexto de conexão carregado.
*   **Quem chama**: `ClientConnectionService`.
*   **Quem utiliza**: Motor de autorização de rede do sistema.

### `EnvironmentService`
*   **Responsabilidade**: Criar novos ambientes, gerar tokens aleatórios cryptográficos associados e salvar hashes no banco de dados. Atualizar status de ping e online.
*   **Quem chama**: Controladores administrativos de ambientes, `RealtimeManager` (ao iniciar/finalizar WS).
*   **Quem utiliza**: Fluxos administrativos e monitoramento online do WebSocket.

### `EnvironmentSyncService`
*   **Responsabilidade**: Abrir transações para sincronização de snapshot e repassar dados para o sincronizador de containers.
*   **Quem chama**: `RealtimeManager` (WebSocket).
*   **Quem utiliza**: Agentes atualizando a Cloud.

### `PublishedContainerSyncService`
*   **Responsabilidade**: Sincronizar o estado dos containers ativos no host, disparando cascata de sincronização para os nós VPN e tokens.
*   **Quem chama**: `EnvironmentSyncService`.
*   **Quem utiliza**: Sincronização em tempo real do WebSocket.

### `PublishedNodeSyncService`
*   **Responsabilidade**: Criar ou atualizar informações sobre as instalações internas do Tailscale em cada container.
*   **Quem chama**: `PublishedContainerSyncService`.
*   **Quem utiliza**: Sincronização em tempo real do WebSocket.

### `UserService`
*   **Responsabilidade**: Registrar novos usuários na plataforma, validando duplicidade de e-mails.
*   **Quem chama**: Rotas de registro público ou admin.
*   **Quem utiliza**: Novos administradores da Cloud.

### `HeadscaleUserService`
*   **Responsabilidade**: Delegar chamadas de criação, listagem, remoção e renomeação de usuários para o REST Client do Headscale, registrando logs de auditoria.
*   **Quem chama**: Módulos futuros de provisionamento de usuários.
*   **Quem utiliza**: Orquestradores do Headscale.

### `HeadscalePreAuthKeyService`
*   **Responsabilidade**: Delegar criação, listagem e expiração de chaves de pré-autenticação para o cliente REST e registrar logs.
*   **Quem chama**: `HeadscaleProvisioningService` ou fluxos futuros de pareamento de nós.
*   **Quem utiliza**: Orquestração de autenticação automática de containers VPN.

### `HeadscaleNodeService`
*   **Responsabilidade**: Encapsular a listagem, remoção, renomeação e migração de usuários de nós VPN registrados no Headscale.
*   **Quem chama**: Componentes futuros de sincronização ou gerenciamento de máquinas.
*   **Quem utiliza**: Gerenciamento direto da topologia de rede.

### `HeadscaleProvisioningService`
*   **Responsabilidade**: Coordenar de forma sequencial a criação/verificação de usuários no Headscale e geração de PreAuthKeys.
*   **Quem chama**: Módulos futuros de inicialização de containers.
*   **Quem utiliza**: Provisionamento automatizado de novas conexões seguras.

### `HeadscaleHealthService`
*   **Responsabilidade**: Validar se a API do Headscale está acessível.
*   **Quem chama**: Telas administrativas e de monitoramento do sistema.
*   **Quem utiliza**: Status de saúde da Cloud.

---

## 6. Repositories

*   **`UserRepository`**: Realiza operações de banco da entidade `User` (busca por ID, busca por e-mail e criação).
*   **`EnvironmentRepository`**: Realiza operações de banco para a entidade `Environment` (criação, busca por ID, busca por hash do token, atualização de status online/last_ping).
*   **`PublishedContainerRepository`**: Realiza operações de banco para a entidade `PublishedContainer` (busca por ID, busca composta de ID de ambiente + ID local do container, criação e atualização de nome/status/número).
*   **`PublishedNodeRepository`**: Realiza operações de banco para a entidade `PublishedNode` (busca por container_id associado, criação e atualização de parâmetros Tailscale - installed, service_running, machine_id, node_key, tailscale_ip, online, last_sync).
*   **`AccessTokenRepository`**: Realiza operações de banco para a entidade `AccessToken` (busca de token ativo por hash SHA-256, criação e atualização de status - validade, ativo, revogado).

---

## 7. DTOs

### Módulo WebSocket (`app/realtime/protocol.py` e `app/realtime/dto/`)
*   `WebSocketMessage`: Define o protocolo de envio de solicitações (contém `request_id`, `origin`, `type`, `payload`).
*   `WebSocketResponse`: Define respostas bem sucedidas com metadados do `request_id` e dados de `payload`.
*   `WebSocketError`: Define payload de erro padrão no WebSocket.
*   `WebSocketErrorDetail`: Contém `code` e `message` explicativos de erros WebSocket.
*   `EventPublishDTO` (`app/realtime/dto/event.py`): Contém campos `event`, `resource` e `metadata` opcionais para publicação de eventos externos dos agentes.

### Módulo Environment Sync (`app/dtos/environment_sync.py`)
*   `EnvironmentSnapshotDTO`: O container principal do snapshot recebido pelo Agent, contendo detalhes do `environment` e a lista `published_containers`.
*   `EnvironmentDetailsDTO`: Informações do ambiente, como ID e data de registro.
*   `PublishedContainerSnapshotDTO`: Estrutura de container serializada com ID local, número do container, nome, status, além de referências aninhadas para dados do nó Tailscale e tokens de acesso locais.
*   `PublishedTailscaleNodeSnapshotDTO`: Informações do estado do Tailscale local do container.
*   `PublishedAccessTokenSnapshotDTO`: Informações de validade e hashes dos tokens sincronizados do container.

### Módulo Client Connection (`app/dto/client_connection.py`)
*   `ClientConnectionRequestDTO`: Recebe o token brutos enviado pelo cliente.
*   `ClientConnectionResponseDTO`: Payload de resposta indicando se foi autorizado, o código/mensagem de erro ou as instruções de conexão.
*   `ConnectionInstructionsDTO`: Contém os parâmetros reais para o cliente VPN conectar ao Headscale (`login_server`, `preauth_key`, `hostname`, `expires_at`).
*   `AuthorizedConnectionContext`: Dataclass contendo a árvore resolvida de entidades do banco de dados para a conexão.
*   `ValidationResult`: Representa o resultado de uma validação de acesso efetuada.

### Módulo Headscale Integration (`app/integrations/headscale/dto.py`)
*   `HeadscaleUserDTO` / `HeadscaleUserListDTO`: Representação JSON da resposta da API de usuários do Headscale.
*   `HeadscalePreAuthKeyDTO` / `HeadscalePreAuthKeyListDTO`: Representação JSON da resposta da API de chaves de pré-autenticação.
*   `HeadscaleNodeDTO` / `HeadscaleNodeListDTO`: Representação JSON da resposta de nós/máquinas na VPN.

---

## 8. Fluxo Completo do WebSocket

O ciclo de vida completo de uma comunicação via WebSocket ocorre conforme o fluxo:

```
[Agent]                                                [RealtimeManager]                          [Dispatcher]                [EventHandler / SyncService]
   │                                                           │                                        │                                   │
   │ 1. Inicia conexão WS com JWT                              │                                        │                                   │
   ├──────────────────────────────────────────────────────────>│                                        │                                   │
   │                                                           │ 2. Registra conexão ativa e            │                                   │
   │                                                           │    atualiza status online no banco     │                                   │
   │                                                           │                                        │                                   │
   │                                                           │ 3. Dispara tarefa de sincronização     │                                   │
   │                                                           │    trigger_environment_sync()          │                                   │
   │                                                           │                                        │                                   │
   │ 4. Recebe pedido "environment.sync"                       │                                        │                                   │
   │<──────────────────────────────────────────────────────────┤                                        │                                   │
   │                                                           │                                        │                                   │
   │ 5. Responde contendo Snapshot JSON                        │                                        │                                   │
   ├──────────────────────────────────────────────────────────>│                                        │                                   │
   │                                                           │ 6. Processa dados e grava              │                                   │
   │                                                           │    snapshot no banco de dados          │                                   │
   │                                                           │                                        │                                   │
   │                                                           │ 7. Aguarda loops de mensagens do Agent │                                   │
   │                                                           │                                        │                                   │
   │ 8. Envia mensagem "event.publish"                         │                                        │                                   │
   ├──────────────────────────────────────────────────────────>│───────────────────────────────────────>│                                   │
   │                                                           │                                        │ 9. Despacha mensagem              │
   │                                                           │                                        │    para handler registrado        │
   │                                                           │                                        │──────────────────────────────────>│
   │                                                           │                                        │                                   │ 10. Executa processamento
   │                                                           │                                        │                                   │     e responde ACK
   │                                                           │                                        │                                   │ 11. Dispara sync assíncrono
   │                                                           │                                        │                                   │     trigger_environment_sync()
```

---

## 9. Fluxo de Autenticação do Cliente

Atualmente, o fluxo implementado de autenticação para o cliente externo acessar um contêiner é puramente baseado em tokens estáticos cadastrados no banco de dados e gerenciado na Cloud:

1.  O cliente chama o endpoint `POST /client/connect` contendo o token no corpo JSON.
2.  A Cloud calcula o hash SHA-256 e localiza a entidade `AccessToken` correspondente no banco de dados.
3.  A partir deste token, o sistema carrega o container associado (`PublishedContainer`), o ambiente desse container (`Environment`) e as informações de rede do nó (`PublishedNode`).
4.  O sistema executa 11 validações estritas de estado sobre estas entidades carregadas.
5.  Se a validação falhar, o acesso é negado imediatamente e é enviado o código da falha (ex: `TOKEN_EXPIRED`, `CONTAINER_OFFLINE`, `TAILSCALE_SERVICE_STOPPED`).
6.  Se for bem-sucedido, o sistema autoriza o acesso. **Nota**: O fluxo de geração e entrega da chave de pré-autenticação real (`PreAuthKey`) do Headscale para o cliente conectar na VPN ainda está vazio/não integrado nesse builder.

---

## 10. Integração Headscale

### O que já existe
*   **Camada de Clientes**: Uma interface estrita (`IHeadscaleClient`) e sua implementação REST (`RestHeadscaleClient`) contendo chamadas HTTP robustas para todos os endpoints da API `/api/v1` do Headscale.
*   **Tratamento de Exceções**: Mapeamento completo e limpo de erros HTTP para exceções locais (`exceptions.py`), mantendo a independência de frameworks externos.
*   **Camada de Negócio e Serviços**: 5 serviços modulares divididos por domínios (`app/services/headscale/`) que encapsulam chamadas ao cliente, aplicam logging estruturado e isolam a Cloud do cliente HTTP.
*   **DTOs e Mappers**: Desacoplamento estruturado usando DTOs Pydantic dedicados e um Mapper (`mapper.py`) para tradução em entidades locais.

### Endpoints REST Utilizados
*   `POST /api/v1/user`: Criação de usuários.
*   `GET /api/v1/user`: Listagem de usuários existentes.
*   `DELETE /api/v1/user/{name}`: Exclusão de usuários.
*   `POST /api/v1/user/{name}/rename/{new_name}`: Renomeação de usuários.
*   `POST /api/v1/preauthkey`: Geração de chaves de pré-autenticação de rede.
*   `POST /api/v1/preauthkey/expire`: Expiração manual de chaves de pré-autenticação.
*   `GET /api/v1/preauthkey`: Listagem de chaves ativas filtradas por usuário.
*   `GET /api/v1/node`: Listagem global de nós ou filtrada por usuário.
*   `GET /api/v1/node/{id}`: Obtenção de detalhes de nó.
*   `DELETE /api/v1/node/{id}`: Exclusão de nó cadastrado.
*   `POST /api/v1/node/{id}/rename/{new_name}`: Renomeação de nós na rede.
*   `POST /api/v1/node/{id}/user`: Migração/transferência de dono de nó.

### O que ainda NÃO foi implementado
*   **Orquestração de Provisionamento em Conexões**: O endpoint `/client/connect` ainda não utiliza os serviços do Headscale para registrar dinamicamente novos nós ou emitir PreAuthKeys correspondentes aos tokens validados de forma automatizada.
*   **Sincronização no Banco de Entidades do Headscale**: Os nós cadastrados no Headscale e seus status reais não são ativamente sincronizados no banco de dados da Cloud de forma independente (apenas via snapshot enviado pelo Agent).

---

## 11. Pendências Arquiteturais

### Arquitetura Atual vs Arquitetura Desejada

#### Limitações do Modelo Atual
*   **Acoplamento Temporal do Sync**: O snapshot completo do ambiente é requisitado via WebSocket toda vez que o agente conecta. Se a rede for instável ou a quantidade de contêineres for muito alta, isso pode gerar alto tráfego e latência de processamento no banco.
*   **Validação Estática de Acesso**: O fluxo de autorização (`ClientConnectionService`) é puramente reativo a registros estáticos de banco, sem verificar a saúde da rede VPN em tempo real ou provisionar recursos sob demanda no Headscale.

#### Entidades Mal Representadas
*   `access_tokens`: Estão atrelados rigidamente a `published_containers`. Um usuário não consegue emitir um token de acesso para múltiplos contêineres de uma vez ou criar tokens para o ambiente completo.
*   `connections`: Registra apenas dados genéricos como `started_at`, sem registrar término da sessão, tráfego de dados, status ativo de túnel ou histórico de desconexão.

#### Possíveis Melhorias
*   **Sincronização Incremental**: O Agent poderia reportar apenas deltas de alteração de containers e nodes (ex: eventos específicos de criação/deleção/mudança de status) em vez de enviar o snapshot estruturado completo a cada trigger do WebSocket.
*   **Uso de cache nos Serviços**: Cachear o status de conectividade do Headscale no `HeadscaleHealthService` e a listagem de usuários do Headscale para otimizar tempo de carregamento de requisições.

#### Pontos de Acoplamento
*   O `RealtimeManager` instancia `SessionLocal` e interage diretamente com classes de serviço instanciando-as inline (`EnvironmentService`, `EnvironmentSyncService`), dificultando mocks limpos em testes em tempo real sem injeção de dependência adequada na raiz do websocket.

#### Tabelas que deverão ser Refatoradas Futuramente
*   `connections`: Precisará incluir campos adicionais (ex: `ended_at`, `bytes_transferred`, `session_status`) para suportar gerenciamento de sessões completas.
*   `access_tokens`: Deberá permitir relações N:N com contêineres ou flexibilizar o escopo do token (ex: escopo de ambiente ou escopo de nó).
